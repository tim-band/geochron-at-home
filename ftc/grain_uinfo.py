from django.db.models import Count, Exists, F, OuterRef, Subquery, Q

from ftc.models import Project, Sample, Grain, Image, FissionTrackNumbering
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

def choose_working_grain(request, ft_type):
    """
    Chooses from the highest priority unclosed projects (breaking ties
    at random), and the highest priority uncompleted sample from that
    project (breaking ties at random).
    A sample is uncompleted if there are no complete (result > 0)
    FissionTrackNumbering objects of the correct type associated with it.
    """
    # Result objects not produced by guests
    backref_count = Count('results', filter=
        Q(results__result__gte=0)
        & ~Q(results__worker__username='guest')
    )
    # Result objects produced by this user
    has_backref_user = FissionTrackNumbering.objects.filter(
        grain=OuterRef('pk'),
        worker=request.user,
        ft_type=ft_type,
        result__gte=0
    )
    has_backref_image = Image.objects.filter(
        grain=OuterRef('pk'),
        ft_type=ft_type
    )
    # Grains without results from this user, and with more results needed
    # Ordered by priority of project then priority of sample
    # A random one of these top priority samples will be first
    available_to_count = Grain.objects.values('id').annotate(
        backref_count=backref_count
    ).filter(
        ~Q(Exists(has_backref_user)),
        Q(Exists(has_backref_image)),
        sample__in_project__closed=False,
        sample__completed=False,
        sample__min_contributor_num__gte=F('backref_count')
    ).order_by(
        '-sample__in_project__priority',
        '-sample__priority',
        '?'
    )
    s = str(available_to_count.query)
    chosen = available_to_count.first()
    if chosen is None:
        return None
    chosen_id = chosen['id']
    return Grain(pk=chosen_id)

def restore_grain_uinfo(username):
    grain_uinfo = {}
    ftns = FissionTrackNumbering.objects.filter(
        result=-1,
        worker__username=username,
    ).select_related()
    if len(ftns) == 0:
        return grain_uinfo, None
    ftn = ftns[0]
    grain_uinfo['project'] = ftn.grain.sample.in_project
    grain_uinfo['sample'] =  ftn.sample
    grain_uinfo['marker_latlngs'] = ftn.get_latlngs()
    grain_uinfo['grain_index'] =  ftn.grain.index
    grain_uinfo['ft_type'] = 'S'
    return grain_uinfo, ftn
