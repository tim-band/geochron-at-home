from django.db.models import Count, Exists, F, OuterRef, Subquery

from ftc.models import Project, Sample, Grain, FissionTrackNumbering
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

def generate_working_grain_uinfo(request):
    """
    Chooses from the highest priority unclosed projects (breaking ties
    at random), and the highest priority uncompleted sample from that
    project (breaking ties at random).
    """
    # Result objects not produced by guests
    count_backrefs = Subquery(FissionTrackNumbering.objects.filter(
        in_sample=OuterRef('sample'),
        grain=OuterRef('index')
    ).exclude(
        worker__username='guest'
    ).values('id'))
    # Result objects produced by this user
    count_backref_user = Subquery(FissionTrackNumbering.objects.filter(
        worker=request.user,
        in_sample=OuterRef('sample'),
        grain=OuterRef('index')
    ).values('id'))
    # Grains without results from this user, and with more results needed
    # Ordered by priority of project then priority of sample
    # A random one of these top priority samples will be first
    grain = Grain.objects.annotate(
        counts=Count(count_backrefs)
    ).annotate(
        done=Exists(count_backref_user)
    ).filter(
        done=False,
        sample__in_project__closed=False,
        sample__completed=False,
        sample__min_contributor_num__gte=F('counts')
    ).order_by(
        '-sample__in_project__priority',
        '-sample__priority',
        '?'
    ).first()
    if grain == None:
        return {}
    return {
        'project': grain.sample.in_project,
        'sample': grain.sample,
        'grain_index': grain.index,
        'ft_type': 'S' # should be grain.sample.sample_property
    }

def restore_grain_uinfo(username):
    grain_uinfo = {}
    ftns = FissionTrackNumbering.objects.filter(
        result=-1,
        worker__username=username,
    ).select_related()
    if len(ftns) == 0:
        return grain_uinfo, None
    ftn = ftns[0]
    latlngs = json.loads(ftn.latlngs)
    grain_uinfo['project'] = ftn.in_sample.in_project
    grain_uinfo['sample'] =  ftn.in_sample
    grain_uinfo['num_markers'] = len(latlngs)
    grain_uinfo['marker_latlngs'] = latlngs
    grain_uinfo['grain_index'] =  ftn.grain
    grain_uinfo['ft_type'] = 'S'
    return grain_uinfo, ftn
