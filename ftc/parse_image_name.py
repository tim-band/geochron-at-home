import os

def get_image_index(f):
    if f.lower() == 'reflstackflat':
        return -1
    elif f.lower() == 'stackflat':
        return 0
    elif f[0:6].lower() == 'stack-':
        try:
            return int(f[6:])
        except:
            return None

img_ext = { '.png' : 'P', '.jpeg': 'J', '.jpg': 'J' }

def parse_image_name(n):
    name_ext = os.path.splitext(n)
    ext = name_ext[1]
    if ext not in img_ext:
        return None
    v = get_image_index(name_ext[0])
    if v == None:
        return None
    return {
        'format': img_ext[ext],
        'index': v,
        'ft_type': 'S', # 'I' for mica
    }
