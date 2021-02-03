import os
import json

def load_rois(grain_pool_path, owner, project_name, sample_name, sample_property, grain_nth, ft_type):
    path = os.path.join(grain_pool_path, owner, project_name, \
                 sample_name, 'Grain%02d'%(grain_nth), 'rois.json')
    return load_rois_from_path(path, ft_type)

def load_rois_from_path(path, ft_type):
    with open(path,'r') as inf:
        data = json.load(inf)

    w = data['image_width']
    h = data['image_height']

    rois = list()
    for index, item in enumerate(data['regions']):
        coords = item['vertices']
        shift = item['shift']
        latlng = list()
        # only 'Induced Fission Tracks' will shift coordinates
        # positive sx or sy mean move along the image positive axis directions
        if ft_type == 'I':
            for coord in coords:
                x = w - (float(coord[0]) + shift[0])
                y = float(coord[1]) + shift[1]
                latlng.append([(h-y)/w, x/w])
        else:
            for coord in coords:
                x = float(coord[0])
                y = float(coord[1])
                latlng.append([(h-y)/w, x/w])
        if len(latlng) < 1:
            return None
        else:
            rois.append(latlng)
    return rois

if __name__ == "__main__":
    path="/Data/webapp/geochron/ftc/static/grain_pool/john/test_proj01/lu324-6-fct/Grain01/rois.json"
    path='/Data/webapp/geochron/ftc/static/grain_pool/john/Thermo2016_no_micas/1X/Grain13/rois.json'
    ft_type = 'S'
    print load_rois_from_path(path, ft_type)
