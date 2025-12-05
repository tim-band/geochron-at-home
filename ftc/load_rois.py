from django.contrib.auth.models import User
from ftc.models import Grain, RegionOfInterest

def load_rois_from_regions(grain: Grain, ft_type: str, matrix, regions: RegionOfInterest):
    w = grain.image_width
    h = grain.image_height
    shift_x = 0
    shift_y = 0
    if ft_type == 'I':
        if grain.shift_x:
            shift_x = grain.shift_x / w
        if grain.shift_y:
            shift_y = grain.shift_y / w
    rois = list()
    for _index, item in enumerate(regions.queryset()):
        vertices = item.vertex_set.order_by('id')
        latlng = list()
        # only 'Induced Fission Tracks' will shift coordinates
        # positive sx or sy mean move along the image positive axis directions
        #TODO: combine this logic with similar in ftc.views.MicaDetailView
        for vertex in vertices:
            lat = (h - vertex.y) / w
            lng = vertex.x / w
            if ft_type == 'I':
                if matrix:
                    x = lng - 0.5
                    y = lat - 0.5
                    lng = 0.5 + x * matrix.x0 + y * matrix.y0
                    lat = 0.5 + x * matrix.x1 + y * matrix.y1
                else:
                    lng = 1 - lng
            latlng.append([lat + shift_y, lng + shift_x])
        if len(latlng) < 1:
            return None
        else:
            rois.append(latlng)
    return rois

def indent(spaces, text):
    lines = text.split('\n')
    return spaces + ('\n' + spaces).join(lines)

def rois_vertex(vertex):
    return [vertex.x, vertex.y]

def rois_region(region, grain):
    vertices = region.vertex_set.order_by('id')
    return {
        "shift": [grain.shift_x, grain.shift_y],
        "vertices": list(map(rois_vertex, vertices))
    }

def transform2d_as_matrix(transform):
    if not transform:
        return None
    return [
        [ transform.x0, transform.y0, transform.t0 ],
        [ transform.x1, transform.y1, transform.t1 ]
    ]

def get_rois_from_regions(grain: Grain, regions: RegionOfInterest):
    return {
        "grain_id": grain.id,
        "image_width": grain.image_width,
        "image_height": grain.image_height,
        "scale_x": grain.scale_x,
        "scale_y": grain.scale_y,
        "stage_x": grain.stage_x,
        "stage_y": grain.stage_y,
        "mica_stage_x": grain.mica_stage_x,
        "mica_stage_y": grain.mica_stage_y,
        "regions": list([
            rois_region(region, grain)
            for region in regions.queryset()
        ]),
        "mica_transform_matrix": transform2d_as_matrix(
            grain.mica_transform_matrix
        )
    }

def get_rois(grain: Grain):
    """
    Returns a python object that represents ROIs (and other
    metadata) about the Grain.

    Only the generic ROI, not any user's.
    """
    return get_rois_from_regions(grain, grain.get_regions_generic())

def get_rois_user(grain: Grain, user: User):
    """
    Returns a python object that represents ROIs (and other
    metadata) about the Grain.

    The ROI is the specified user's.
    """
    return get_rois_from_regions(grain, grain.get_regions_specific(user))

def get_roiss(grains):
    return list([
        get_rois(grain) for grain in grains
    ])
