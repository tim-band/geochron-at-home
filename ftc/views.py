from django.shortcuts import render, get_object_or_404

# Create your views here.
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect

#Import models
from ftc.models import Project, Sample, FissionTrackNumbering

#
def home(request):
    return render(request, 'ftc/home.html', {})

# the view for /accounts/profile/
def profile(request):
    if request.user.is_authenticated:
        return render(request, 'ftc/profile.html', {})
    else:
        return redirect('account_login') # 'home'

def signmeup(request):
    if request.user.username == 'guest':
        # logout guest
        logout(request)
    return redirect('account_signup')
       
# Fission tracks measuring report
from django.contrib.auth.decorators import login_required, user_passes_test
"""
def user_is_staff(user):
    return user.is_authenticated and user.is_active and user.is_staff
"""

#@user_passes_test(user_is_staff)
@login_required
def report(request):
    if request.user.is_active and request.user.is_staff:
        #projects = get_object_or_404(Project, creator=request.user)
        try:
            if request.user.is_superuser:
                projects = Project.objects.all()
            else:
                projects = Project.objects.filter(creator=request.user)
        except (KeyError, Project.DoesNotExist):
            return HttpResponse("you have no project currrently. add one?")
        else:
#            return render(request, 'ftc/home.html', {'projects': projects})
            return render(request, 'ftc/report.html', {'projects': projects})
    else:
        return HttpResponse("Sorry, You don't have permission to access the requested page.")

import json
from django.core.serializers.json import DjangoJSONEncoder

@login_required
def getTableData(request):
    if request.is_ajax() and request.user.is_active and request.user.is_staff:
        try:
            # http://owtrsnc.blogspot.co.uk/2013/12/sending-ajax-data-json-to-django.html
            # http://jonblack.org/2012/06/22/django-ajax-class-based-views/
            # assuming request.body contains json data which is UTF-8 encoded
            json_str = request.body.decode(encoding='UTF-8')
            # turn the json bytestr into a python obj
            json_obj = json.loads(json_str)
            sample_list = json_obj['client_response']
            res = []
            if sample_list:
                for sample_id in sample_list:
                    fts = FissionTrackNumbering.objects.select_related('in_sample__in_project').filter(in_sample=sample_id)
                    for ft in fts:
                        if request.user.is_superuser or ft.in_sample.in_project.creator == request.user:
                            a = [ft.in_sample.in_project.project_name, ft.in_sample.sample_name, 
                                 ft.grain, ft.ft_type, ft.result, ft.worker.username, ft.create_date]
                            res.append(a)
            #--ok--projects = FissionTrackNumbering.objects.filter(in_sample__in=sample_list).values_list('in_sample', 'grain', 'result')
            myjson = json.dumps({ 'aaData' : res }, cls=DjangoJSONEncoder)
            #--ok--myjson = json.dumps({ 'aaData' : list(projects) }, cls=DjangoJSONEncoder)
        except (KeyError, Project.DoesNotExist):
            return HttpResponse("you have no project currrently. add one?")
        else:
            return HttpResponse(myjson, content_type='application/json')
    else:
        return HttpResponse("Sorry, You don't have permission to access the requested page.")

import os, random, itertools
from django.templatetags.static import static

from .get_img_list_of_grain  import get_grain_images_list
from .get_image_size import get_image_size, UnknownImageFormat
from .grain_uinfo import genearate_working_grain_uinfo, restore_grain_uinfo
from .load_rois import load_rois

@login_required
def get_grain_images(request):
    BASE_DIR = os.path.dirname(os.path.abspath(__file__)) # ftc/
    grain_pool_path = os.path.join(os.path.dirname(BASE_DIR), 'static/grain_pool')
    working_repos_path = os.path.join(BASE_DIR, "static/working_repos/")
    sep = '~'
    res = {}
    # img_ext = set(['.png', '.jpeg', '.jpg'])
    # at least number of contributions, here set to 1 at moment
    min_contributors_per_grain = 1
    flag_continue_old_counting = False
    if request.is_ajax() and request.user.is_active:
        uname = request.user.username
        grain_uinfo, working_f = restore_grain_uinfo(working_repos_path, uname)
        if len(grain_uinfo) == 0:
            grain_uinfo = genearate_working_grain_uinfo(request)
            working_f = None
        else:
            res['num_markers']  = grain_uinfo['num_markers']
            res['marker_latlngs'] = grain_uinfo['marker_latlngs']
        if len(grain_uinfo) !=0:
            the_project = grain_uinfo['project']
            the_sample = grain_uinfo['sample']
            the_grain = grain_uinfo['grain_index']
            ft_type = grain_uinfo['ft_type']
            if the_grain is None:
                the_grain = -1
            images_list = get_grain_images_list(grain_pool_path, the_project.creator.username, \
                                                the_project.project_name, the_sample.sample_name, \
                                                the_sample.sample_property, the_grain, ft_type)
            if (len(images_list) > 0):
                rois = load_rois(grain_pool_path, the_project.creator.username, \
                                                the_project.project_name, the_sample.sample_name, \
                                                the_sample.sample_property, the_grain, ft_type)
            else:
                rois = None
            if (len(images_list) > 0) and (rois is not None):
                try:
                    width, height = get_image_size(os.path.join(grain_pool_path, images_list[0]))
                except UnknownImageFormat:
                    width, height = 1, 1 
                res['proj_id'] = the_project.id
                res['sample_id'] = the_sample.id
                res['grain_num'] = the_grain
                res['ft_type'] = ft_type
                res['image_width'] = width
                res['image_height'] = height
                res['images'] = list(map(lambda i: static(os.path.join('grain_pool', i)), images_list))
                res['rois'] = rois
                #--- 
                myjson = json.dumps(res, cls=DjangoJSONEncoder)
                return HttpResponse(myjson, content_type='application/json')
            else:
                # report error: cannot find images for grain
                if working_f is not None:
                    os.remove(working_f)
                error_str = "[Project: %s, Sample: %s, Grain #: %d, FT_type: %s] has no images or has no ROIs\n" \
                          % (the_project.project_name, the_sample.sample_name, the_grain, ft_type) \
                          + "Refresh page to load another Grain."
                myjson = json.dumps({'reply' : 'error: ' + error_str}, cls=DjangoJSONEncoder)
                return HttpResponse(myjson, content_type='application/json')                
        else:
            message = 'Well done! You did all your jobs and take a break.'
            myjson = json.dumps({'reply' : message}, cls=DjangoJSONEncoder)
            return HttpResponse(myjson, content_type='application/json')


from django.contrib.auth.models import User
def counting(request, uname=None):
    #return HttpResponse("Hello, world. You're counting." + '--' + uname)
    if uname is None and request.user.is_authenticated:
       return render(request, 'ftc/counting.html', {})
    elif uname == 'guest':
        passwd = 'guestsitest'
        user = User.objects.get(username__exact='guest')
        user.set_password(passwd)
        user.save()
        user = authenticate(username='guest', password=passwd)
        login(request, user)
        return render(request, 'ftc/profile.html', {})
        #2016-sept-03: return render(request, 'ftc/counting.html', {})
        #return HttpResponse("Hello, world. You're counting." + '--' + uname)
    else:
        return redirect('home')

#@login_required
#def counting(request):
#    return render(request, 'ftc/counting.html', {})

    #return HttpResponse("Hello, world. You're counting.")
    #if guest:
    #    pass #request.user = 
    #if request.user.is_active:
    #    return render(request, 'ftc/counting.html', {})
    #else:
    #    redirect('home')

@login_required
def updateTFNResult(request):
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    working_repos_path = os.path.join(BASE_DIR, "static/working_repos/")
    #working_repos_path = "ftc/static/working_repos/"
    sep = '~'
    if request.is_ajax() and request.user.is_active:
        try:
            json_str = request.body.decode(encoding='UTF-8')
            json_obj = json.loads(json_str)
            res_dic = json_obj['counting_res']
            sample = Sample.objects.get(id=res_dic['sample_id'])
            latlng_json_str = json.dumps(res_dic['marker_latlngs'])
            fts = FissionTrackNumbering(in_sample=sample, 
                                        grain=res_dic['grain_num'], 
                                        ft_type=res_dic['ft_type'], 
                                        worker=request.user, 
                                        result=res_dic['track_num'],
                                        latlngs=latlng_json_str)
            fts.save()
            #remove intermedia result file if exists
            proj_id = res_dic['proj_id']
            sample_id = res_dic['sample_id']
            grain_num = res_dic['grain_num']
            ft_type = res_dic['ft_type']
            filename_intermedia_result = working_repos_path \
                                       + request.user.username + sep \
                                       + str(proj_id) + sep \
                                       + str(sample_id)  + sep \
                                       + str(grain_num) + sep \
                                       + ft_type + '.json'
            if os.path.isfile(filename_intermedia_result): os.remove(filename_intermedia_result)
            # if stack-mica pair, do the uncounted part
            # TODO 
        except (KeyError, Project.DoesNotExist):
            return HttpResponse("you have no project currrently.")
        else:
            myjson = json.dumps({ 'reply' : 'Done and thank you' }, cls=DjangoJSONEncoder)
            return HttpResponse(myjson, content_type='application/json')
    else:
        return HttpResponse("Sorry, You have to active your account first.")

import sys
import fnmatch
@login_required
def saveWorkingGrain(request):
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    working_repos_path = os.path.join(BASE_DIR, "static/working_repos/")
    #working_repos_path = "ftc/static/working_repos/"
    sep = '~'
    if request.is_ajax() and request.user.is_active:
        try:
            json_str = request.body.decode(encoding='UTF-8')
            res_json = json.loads(json_str)
            res = res_json['intermedia_res']
            proj_id = res['proj_id']
            sample_id = res['sample_id']
            grain_num = res['grain_num']
            ft_type = res['ft_type']
            #image_width = res['image_width']
            #image_height = res['image_height']
            num_markers = res['num_markers']
            marker_latlngs = res['marker_latlngs']
            filename_intermedia_result = working_repos_path \
                                       + request.user.username + sep \
                                       + str(proj_id) + sep \
                                       + str(sample_id)  + sep \
                                       + str(grain_num) + sep \
                                       + ft_type + '.json'
            for file in os.listdir(working_repos_path):
                if fnmatch.fnmatch(file, request.user.username + '*'):
                    os.remove(os.path.join(working_repos_path, file))
            with open(filename_intermedia_result,'w+') as f:
                json.dump(res, f)
        except Exception as err:
            return HttpResponse(sys.exc_info()[0])
        else:
            myjson = json.dumps({ 'reply' : 'Done and thank you' }, cls=DjangoJSONEncoder)
            return HttpResponse(myjson, content_type='application/json')
    else:
        return HttpResponse("Sorry, You have to active your account first.")

