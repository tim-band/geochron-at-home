import os, sys, shutil
from optparse import OptionParser
from django.db import transaction
from ftc.parse_image_name import parse_upload_name
from ftc.save_rois_regions import save_rois_regions
import json


def copyimages(src, grain):
    for n in sorted(os.listdir(src)):
        v = parse_upload_name(n)
        srcname = os.path.join(src, n)
        if os.path.isfile(srcname) and v != None and v['is_image']:
            with open(srcname, mode='rb') as f:
                Image(
                    grain=grain,
                    format=v['format'],
                    ft_type=v['ft_type'],
                    index=v['index'],
                    data=f.read()
                ).save()


def creategrain(src, sample, grain_nth):
    p = os.path.join(src, 'rois.json')
    if not os.path.isfile(p):
        sys.exit('no such grain file {0}; exiting'.format(p))
    with open(p, mode='r') as j:
        print(p)
        rois = json.load(j)
    region_first = rois['regions'][0]
    transform = None
    rois_transform = rois.get('mica_transform')
    if rois_transform and type(rois_transform) is list and len(rois_transform) == 2:
        transform = Transform2D(
            x0=rois_transform[0][0],
            y0=rois_transform[0][1],
            t0=rois_transform[0][2],
            x1=rois_transform[1][0],
            y1=rois_transform[1][1],
            t1=rois_transform[1][2]
        )
        transform.save()
    g = Grain(
        sample=sample,
        index=grain_nth,
        image_width=rois['image_width'],
        image_height=rois['image_height'],
        scale_x=rois.get('scale_x'),
        scale_y=rois.get('scale_y'),
        stage_x=rois.get('stage_x'),
        stage_y=rois.get('stage_y'),
        mica_stage_x=rois.get('stage_x'),
        mica_stage_y=rois.get('stage_y'),
        shift_x=region_first['shift'][0] if region_first else 0,
        shift_y=region_first['shift'][1] if region_first else 0,
        mica_transform_matrix=transform
    )
    g.save()
    save_rois_regions(rois, g)
    return g


def copygrains(src, sample):
    # create sample
    folders = next(os.walk(src))[1]
    names = sorted(os.listdir(src))
    for name in names:
        try:
            grain_nth = int(name[5:])
        except:
            grain_nth = None
        srcname = os.path.join(src, name)
        if os.path.isdir(srcname) and name[0:5] == 'Grain':
            grain = creategrain(srcname, sample, grain_nth)
            copyimages(srcname, grain)
    sample.save()


def copysamples(src, project):
    names = sorted(os.listdir(src))
    for name in names:
        srcname = os.path.join(src, name)
        if os.path.isdir(srcname):
            sample = project.sample_set.create(sample_name=name,
                sample_property='T', completed=False)
            copygrains(srcname, sample)


@transaction.atomic
def copyprojects(src):
    folders = next(os.walk(src))[1]
    # create projects
    for name in folders:
        mystr = 'Project "%s" created by %s' % (name, uname)
        mystr = '*' + mystr.center(len(mystr)+6, ' ') + '*'
        print('*'*len(mystr))
        print(mystr)
        print('*'*len(mystr))
        p = Project(project_name=name, creator=user, project_description='project '+name, closed=False)
        p.save()
        srcname = os.path.join(src, name)
        copysamples(srcname, p)


usage = "usage: %prog -s SETTINGS | --settings=SETTINGS"
parser = OptionParser(usage)
parser.add_option('-s', '--settings', dest='settings', metavar='SETTINGS',
                  help="The Django settings module to use")
parser.add_option('-i', '--input', dest='input', metavar='INPUT_DIRECTORY',
        help='The directory that contains the new files')
(options, args) = parser.parse_args()
if not options.settings:
    parser.error("You must specify a settings module. For examples, python standalone_django.py --settings=geochron.settings")

os.environ['DJANGO_SETTINGS_MODULE'] = options.settings

import django
django.setup()

from django.contrib.auth.models import User
from ftc.models import Project, Sample, Grain, Image, Transform2D

# get user id based on username
input_source_path = options.input or '/code/user_upload/'
uname = 'john'
u = User.objects.filter(username=uname)
if len(u) != 1:
    sys.exit('no user or too many users found')
user = u[0]

#----- walk through the project ------
input_source_path = os.path.normpath(input_source_path)
src = os.path.join(input_source_path, uname)

copyprojects(src)
print('finished' + '-'*72)


