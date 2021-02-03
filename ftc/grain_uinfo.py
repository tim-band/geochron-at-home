from ftc.models import Project, Sample, FissionTrackNumbering
import os, random, itertools, json

def sorted_rand_T(qeuryset):
    # random choose for same priority and create time query set
    # larger priority value and newer project first
    PTQ = [(q.priority, q.create_date, q) for q in qeuryset]
    res = [Q for (P,T,Q) in sorted(PTQ, key=lambda pair: (pair[0], pair[1], random.random()) )]
    res.reverse()
    return res

def sorted_rand(qeuryset):
    # random choose for same priority query set
    P_Q = [(q.priority, q) for q in qeuryset]
    res = [Q for (P,Q) in sorted(P_Q, key=lambda pair: (pair[0], random.random()) )]
    res.reverse()
    return res

def genearate_working_grain_uinfo(request):
    all_closed = False
    grain_uinfo = {}
    num_loop = 0
    # num_loop: 0 => sample close; 1 => project close; 2 => all closed
    #min_contributors_per_grain = 1    
    for num_loop in range(3):
        projs = Project.objects.filter(closed=False).order_by('-priority', 'create_date')
        if len(projs) >= 1:
            for the_project in sorted_rand_T(projs):  # changed jhe 2014-10-26
                samples = the_project.sample_set.filter(completed=False).order_by('-priority')
                if len(samples) == 0:
                    # update project state to closed
                    the_project.closed = True
                    the_project.save()
                    continue #for next project
                else:
                    for the_sample in sorted_rand(samples):  # changed jhe 2014-10-26
                        total_grain = the_sample.total_grains
                        all_grains = set()
                        user_finished_grains = set() #a
                        for i in range(total_grain):
                            #all_grains.add((i+1, 'I')) # Induced # changed jhe 2015-02-10
                            if the_sample.sample_property != 'D':
                                all_grains.add((i+1, 'S')) # Spontaneous
                        grains = the_sample.fissiontracknumbering_set.all()
                        g_count = dict()
                        for g in grains:
                            key = (g.grain, g.ft_type)
                            if key in g_count:
                                g_count[key] += 1
                            else:
                                g_count[key] = 1
                            if g.worker == request.user: #a
                                user_finished_grains.add(key) #a
                        if len(g_count) != 0:
                            for k, v in g_count.iteritems():
                                #min_contributors_per_grain: jhe add on 2017-12-11, guest exceptional
                                if v >= the_sample.min_contributor_num and request.user.username != 'guest': 
                                    all_grains.remove(k)
                        if len(all_grains) == 0:
                            # update sample to completed state
                            the_sample.completed = True
                            the_sample.save()
                            continue #for next sample
                        # jhe add on 2017-12-11, guest exceptional
                        if request.user.username == 'guest':
                            remain_grains = all_grains
                        else:
                            remain_grains = all_grains.difference(user_finished_grains) #a
                        if len(remain_grains) > 0: #a
                            the_grain, ft_type = random.sample(remain_grains, 1)[0]
                            grain_uinfo['project'] = the_project
                            grain_uinfo['sample'] = the_sample
                            grain_uinfo['grain_index'] = the_grain
                            grain_uinfo['ft_type'] = ft_type
                            return grain_uinfo
            #out of project and has no grain found
    #end num_loop loop
    # if still len(projs) > 0, means this user has nothing left, but not all project closed
    return grain_uinfo

def restore_grain_uinfo(working_repos_path, username):
    grain_uinfo = {}
    path = None
    files = [f for f in os.listdir(working_repos_path)]
    for f in files:
        path = os.path.join(working_repos_path, f)
        if os.path.isfile(path) and f.startswith(username) and f.endswith('.json'):
            with open(path,'r') as inf:
                data = json.load(inf)
            try:
              project_id = data['proj_id']
              sample_id = data['sample_id']
              the_project = Project.objects.get(pk=project_id)
              the_sample = Sample.objects.get(pk=sample_id)
            except:
              # in case project and/or sample is deleted in database
              os.remove(path)
              break
            grain_uinfo['project'] = the_project
            grain_uinfo['sample'] = the_sample
            grain_uinfo['num_markers'] = data['num_markers']
            grain_uinfo['marker_latlngs'] = data['marker_latlngs']
            grain_uinfo['grain_index'] = data['grain_num']
            grain_uinfo['ft_type'] = data['ft_type']
            break
    return grain_uinfo, path
