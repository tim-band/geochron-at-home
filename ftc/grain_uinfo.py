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
    # Only include grains with images
    has_backref_image = Q(Exists(Image.objects.filter(
        grain=OuterRef('pk'),
        ft_type=ft_type
    )))
    # Grains with images, in non-completed samples in open projects
    basic_query = Grain.objects.annotate(
        backref_count=backref_count
    ).filter(
        has_backref_image,
        sample__in_project__closed=False,
        sample__completed=False,
        sample__public=True,
    )
    if request.user.username == 'guest':
        available_to_count = basic_query.order_by(
            '?'
        )
    else:
        # Result objects produced by this user
        has_backref_user = FissionTrackNumbering.objects.filter(
            grain=OuterRef('pk'),
            worker=request.user,
            ft_type=ft_type,
            result__gte=0
        )
        # Only grains that don't have enough (non-guest) results anyway.
        # Choosing at random from those projects at the highest priority
        # and within that those samples at the highest priority.
        available_to_count = basic_query.filter(
            ~Q(Exists(has_backref_user)),
            sample__min_contributor_num__gte=F('backref_count'),
        ).order_by(
            '-sample__in_project__priority',
            '-sample__priority',
            '?'
        )
    chosen = available_to_count.values('id').first()
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
