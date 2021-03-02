import os
import json
from ftc.models import Vertex, Region, Image, Grain

def load_rois(grain_pool_path, owner, project_name, sample_name, sample_property, grain_nth, ft_type):
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
        coords = item.vertex_set.all()
        latlng = list()
        # only 'Induced Fission Tracks' will shift coordinates
        # positive sx or sy mean move along the image positive axis directions
        if ft_type == 'I':
            for coord in coords:
                x = w - (float(coord.x) + item.shit_x)
                y = float(coord.y) + item.shift_x
                latlng.append([(h-y)/w, x/w])
        else:
            for coord in coords:
                x = float(coord.x)
                y = float(coord.y)
                latlng.append([(h-y)/w, x/w])
        if len(latlng) < 1:
            return None
        else:
            rois.append(latlng)
    return rois
