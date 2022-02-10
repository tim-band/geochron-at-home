import os

def get_image_index(f):
    if f == 'reflstackflat':
        return -1
    elif f == 'stackflat':
        return 0
    elif f[0:6] == 'stack-':
        try:
            return int(f[6:])
        except:
            return None
    elif f[0:10] == 'reflstack-':
        try:
            return int(f[10:]) - 100
        except:
            return None

img_ext = { '.png' : 'P', '.jpeg': 'J', '.jpg': 'J' }

def parse_image_name(n):
    [ name, ext ] = os.path.splitext(n.lower())
    if ext not in img_ext:
        return None
    ft_type = 'S'
    if name[:4] == 'mica':
        name = name[4:]
        ft_type = 'I'
    v = get_image_index(name)
    if v == None:
        return None
    return {
        'format': img_ext[ext],
        'index': v,
        'ft_type': ft_type,
    }
