import os
import json
from ftc.models import Grain, Region, Vertex

def load_rois(project_name, sample_name, sample_property, grain_nth, ft_type):
    grains = Grain.objects.filter(
        index=grain_nth,
        sample__sample_name=sample_name,
        sample__in_project__project_name=project_name
    )
    grain = grains[0]

    w = grain.image_width
    h = grain.image_height

    rois = list()
    for index, item in enumerate(grain.region_set.all()):
        coords = item.vertex_set.order_by('id')
        latlng = list()
        # only 'Induced Fission Tracks' will shift coordinates
        # positive sx or sy mean move along the image positive axis directions
        """if ft_type == 'I':
            for coord in coords:
                x = w - (float(coord.x) + item.shift_x)
                y = float(coord.y) + item.shift_y
                latlng.append([(h-y)/w, x/w])"""
        for coord in coords:
            x = float(coord.x)
            y = float(coord.y)
            latlng.append([(h-y)/w, x/w])
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
    return {
        "image_width": grain.image_width,
        "image_height": grain.image_height,
        "scale_x": grain.scale_x,
        "scale_y": grain.scale_y,
        "stage_x": grain.stage_x,
        "stage_y": grain.stage_y,
        "regions": rjs
    }
