import os, sys, shutil
from optparse import OptionParser

#------------------------------------------------------------
def copygrain(src, dst, level=0):
    print('@level %d, destination: %s' % (level, dst))
    #level 0 see projects; level 1 see samples; level 2 see grains; level 3 see images
    folder_name = ['project', 'sample', 'grain']
    line_end = ['\n', '\n', '']
    img_ext = set(['.png', '.jpeg', '.jpg'])
    #print 'entering %s' % (src)    
    names = sorted(os.listdir(src))
    
    # populate DB
    folders = os.walk(src).next()[1]
    if level == 0:
        # create projects
        for name in folders:
            mystr = 'Project "%s" created by %s' % (name, uname)
            mystr = '*' + mystr.center(len(mystr)+6, ' ') + '*'
            print('*'*len(mystr))
            print(mystr)
            print('*'*len(mystr))
            p = Project(project_name=name, creator=user, project_description='project '+name, closed=False)
            p.save()
    if level == 2:
        # create sample
        total_grain = len(folders)
        head, sample = os.path.split(src)
        head, project = os.path.split(head)
        print('create sample "%s" with %d grains - %s' % (sample, total_grain, project))
        p = Project.objects.filter(project_name=project, creator=user)
        if len(p) == 1:
            p[0].sample_set.create(sample_name=sample, sample_property='T', total_grains=total_grain, completed=False)
        else:
            sys.exit('not unique for the combine keys, creator: %s and project_name: %s' % (uname, name)) 
    if level == 3:
        grain = os.path.split(src)[1]
        total_image = 0
        for n in names:
            if os.path.isfile(os.path.join(src, n)) and os.path.splitext(n)[1] in img_ext: 
                total_image+=1
        print('%s grain "%s" has %d images' % (' '*4, grain, total_image))
        
    # create folder structure
    if not os.path.isdir(dst):
        print('Create folder %s' % (dst))
        os.makedirs(dst)

    errors = []
    for name in names:
        srcname = os.path.join(src, name)
        dstname = os.path.join(dst, name)
        try:
            if os.path.isdir(srcname) and level < 4:
                copygrain(srcname, dstname, level=level+1)
            elif os.path.isfile(srcname) and level == 3 and (os.path.splitext(srcname)[1] in img_ext or os.path.split(srcname)[1]=="rois.json"):
                shutil.copy2(srcname, dstname)
        except (IOError, OSError) as why:
            errors.append((srcname, dstname, str(why)))
        # catch the Error from the recursive copygrain so that we can
        # continue with other files
        except shutil.Error as err:
            if len(errors)>0:
              errors.extend(err.args[0])
            else:
              errors.append(err.args[0])
    if len(errors)>0:
        raise Exception(errors)
#--------------------------------------------end of copygrain

usage = "usage: %prog -s SETTINGS | --settings=SETTINGS"
parser = OptionParser(usage)
parser.add_option('-s', '--settings', dest='settings', metavar='SETTINGS',
                  help="The Django settings module to use")
(options, args) = parser.parse_args()
if not options.settings:
    parser.error("You must specify a settings module. For examples, python standalone_django.py --settings=geochron.settings")

os.environ['DJANGO_SETTINGS_MODULE'] = options.settings

#----- start your code below -----
from django.contrib.auth.models import User
from ftc.models import Project, Sample

# get user id based on username
input_source_path = '/code/user_upload/'
grain_pool_path = '/code/static/grain_pool' #'irradiation/static/grain_pool'
uname = 'john'
u = User.objects.filter(username=uname)
if len(u) != 1:
    sys.exit('no user or too many users found')
user = u[0]

#----- walk through the project ------
input_source_path = os.path.normpath(input_source_path)
grain_pool_path = os.path.normpath(grain_pool_path)

src = os.path.join(input_source_path, uname)
dst = os.path.join(grain_pool_path, uname)

copygrain(src, dst)
print('finished' + '-'*72)


