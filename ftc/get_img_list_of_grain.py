import os

def parse_image_name(f):
    import re
    if f.lower() == 'ReflStackFlat'.lower():
        k = -1
    elif f.lower() == 'StackFlat'.lower():
        k = 0
    else:
        m = re.search(r"^stack-(\d+)$", f, re.IGNORECASE)
        if m:
            k = int(m.group(1))
        else:
            k = None
    return k

def get_grain_images_list(grain_pool_path, owner, project_name, sample_name, sample_property, grain_nth, ft_type):
    # get lis of images
    img_ext = set(['.png', '.jpeg', '.jpg'])
    images = dict()
    grain_path = os.path.join(grain_pool_path, owner, project_name, \
                 sample_name, 'Grain%02d'%(grain_nth))
    if os.path.isdir(grain_path):
        for f in os.listdir(grain_path):
            head, ext = os.path.splitext(f)
            path = os.path.join(grain_path, f)
            if os.path.isfile(path) and ext in img_ext:
                k = None
            str2parse = head
            if ft_type == 'I' and head.lower().startswith('mica'):
                str2parse = head[4:]
            elif sample_property == 'D' and not head.lower().startswith('mica'):
                pass
            elif ft_type == 'S' and not head.lower().startswith('mica'):
                pass
            else:
                continue
            k = parse_image_name(str2parse)
            if k != None:
                url = os.path.join(grain_path, f)
                images[k] = '/static/' + url.split('/static/')[1]  #link from /static/...
                #return HttpResponse('I got: '+url[19:])
    images_list = []
    if len(images) > 0:
       extra_image = None
       if 0 in images:
           images_list.append(images.pop(0))
       if -1 in images:
           extra_image = images.pop(-1)
       for k in sorted(images):
           images_list.append(images[k])
       if extra_image:
           images_list.insert(0,extra_image)       #---jhe--- put the reflected image on top
           #images_list.append(extra_image)
#------------------------------------------
    return images_list
