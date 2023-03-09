import os
import json
from ftc.models import Grain, Region, Vertex

def load_rois(grain, ft_type, matrix):
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
    for index, item in enumerate(grain.region_set.all()):
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
                    lng = 0.5 + x * m.x0 + y * m.y0
                    lat = 0.5 + x * m.x1 + y * m.y1
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
    vertices = Vertex.objects.filter(region=region).order_by('id')
    return {
        "shift": [grain.shift_x, grain.shift_y],
        "vertices": map(rois_vertex, vertices)
    }

def get_rois(grain):
    """
    Returns a python object that represents ROIs (and other
    metadata) about the Grain.
    """
    regions = Region.objects.filter(grain=grain)
    rjs = map(lambda region : rois_region(region, grain), regions)
    r = {
        "image_width": grain.image_width,
        "image_height": grain.image_height,
        "scale_x": grain.scale_x,
        "scale_y": grain.scale_y,
        "stage_x": grain.stage_x,
        "stage_y": grain.stage_y,
        "mica_stage_x": grain.mica_stage_x,
        "mica_stage_y": grain.mica_stage_y,
        "regions": rjs,
        "mica_transform_matrix": None
    }
    transform = grain.mica_transform_matrix
    if transform:
        r["mica_transform_matrix"] = [
            [ transform.x0, transform.y0, transform.t0 ],
            [ transform.x1, transform.y1, transform.t1 ]
        ]
    return r
