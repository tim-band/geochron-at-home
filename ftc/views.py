from django.shortcuts import render, get_object_or_404
from django.db import transaction
from django.db.models import Q
from django.forms import ModelForm, CharField, Textarea
from django.views.generic.edit import CreateView, UpdateView
from django.views.generic import DetailView
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import redirect
import base64

from ftc.models import Project, Sample, FissionTrackNumbering, Image, Grain

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

def user_is_staff(user):
    return user.is_active and user.is_staff

#@user_passes_test(user_is_staff)
@login_required
def report(request):
    if request.user.is_active and request.user.is_staff:
        try:
            if request.user.is_superuser:
                projects = Project.objects.all()
            else:
                projects = Project.objects.filter(creator=request.user)
        except (KeyError, Project.DoesNotExist):
            return HttpResponse("you have no project currrently. add one?")
        else:
            return render(request, 'ftc/report.html', {'projects': projects})
    else:
        return HttpResponse("Sorry, You don't have permission to access the requested page.")


@user_passes_test(user_is_staff)
def projects(request):
    return render(request, "ftc/projects.html", {
        'projects': Project.objects.all()
    })


class StaffRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return user_is_staff(self.request.user)


class CreatorOrSuperuserMixin(UserPassesTestMixin):
    def test_func(self):
        return (
            self.request.user == self.object.get_creator()
            or self.request.user.is_superuser
        )


class ProjectDetailView(DetailView, StaffRequiredMixin):
    model = Project
    template_name = "ftc/project.html"


class ProjectForm(ModelForm):
    class Meta:
        model = Project
        fields = ['project_name', 'project_description', 'priority', 'closed']
    project_description = CharField(widget=Textarea)


class ProjectCreateView(CreateView, StaffRequiredMixin):
    model = Project
    form_class = ProjectForm


class ProjectUpdateView(UpdateView, CreatorOrSuperuserMixin):
    model = Project
    form_class = ProjectForm
    template_name = "ftc/project_update.html"


class SampleDetailView(DetailView, StaffRequiredMixin):
    model = Sample
    template_name = "ftc/sample.html"


class SampleForm(ModelForm):
    class Meta:
        model = Sample
        fields = ['sample_name', 'sample_property', 'priority', 'min_contributor_num', 'completed']


class SampleCreateView(CreateView, StaffRequiredMixin):
    model = Sample
    form_class = SampleForm


class SampleUpdateView(UpdateView, CreatorOrSuperuserMixin):
    model = Sample
    form_class = SampleForm
    template_name = "ftc/sample_update.html"


class GrainDetailView(DetailView, StaffRequiredMixin):
    model = Grain
    template_name = "ftc/grain.html"


class GrainForm(ModelForm):
    class Meta:
        model = Grain
        fields = ['index', 'image_width', 'image_height']


class GrainCreateView(CreateView, StaffRequiredMixin):
    model = Grain
    form_class = GrainForm


class GrainUpdateView(UpdateView, CreatorOrSuperuserMixin):
    model = Grain
    form_class = GrainForm
    template_name = "ftc/grain_update.html"


@user_passes_test(user_is_staff)
def images(request, project_name, sample_name, grain_index):
    grain = Grain.objects.get(
        sample__in_project__project_name=project_name,
        sample__sample_name=sample_name,
        index=grain_index,
    )
    images = Image.objects.filter(
        grain__sample__in_project__project_name=project_name,
        grain__sample__sample_name=sample_name,
        grain__index=grain_index,
    ).order_by('index')
    mimetype = {
        'J': 'image/jpeg',
        'P': 'image/png',
    }
    return render(request, "ftc/images.html", {
        'images': images,
        'project_name': project_name,
        'sample_name': sample_name,
        'grain_index': grain_index,
        'grain': grain,
    })


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
                    fts = FissionTrackNumbering.objects.select_related('in_sample__in_project').filter(
                        Q(in_sample=sample_id) & ~Q(result=-1)
                    )
                    for ft in fts:
                        if request.user.is_superuser or ft.in_sample.in_project.creator == request.user:
                            a = [ft.in_sample.in_project.project_name, ft.in_sample.sample_name, 
                                 ft.grain, ft.ft_type, ft.result, ft.worker.username, ft.create_date]
                            res.append(a)
            myjson = json.dumps({ 'aaData' : res }, cls=DjangoJSONEncoder)
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
def get_image(request, pk):
    image = get_object_or_404(Image, pk=pk)
    mime = image.format = 'P' and 'image/png' or 'image/jpeg'
    return HttpResponse(image.data, content_type=mime)

@login_required
def get_grain_images(request):
    BASE_DIR = os.path.dirname(os.path.abspath(__file__)) # ftc/
    grain_pool_path = os.path.join(os.path.dirname(BASE_DIR), 'static/grain_pool')
    sep = '~'
    res = {}
    # img_ext = set(['.png', '.jpeg', '.jpg'])
    # at least number of contributions, here set to 1 at moment
    min_contributors_per_grain = 1
    flag_continue_old_counting = False
    if request.is_ajax() and request.user.is_active:
        uname = request.user.username
        grain_uinfo, ftn = restore_grain_uinfo(uname)
        if len(grain_uinfo) == 0:
            grain_uinfo = genearate_working_grain_uinfo(request)
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
                    gs = Grain.objects.filter(index=the_grain,
                        sample__sample_name=the_sample.sample_name,
                        sample__in_project__project_name=the_project.project_name)
                    width = gs[0].image_width
                    height = gs[0].image_height
                except UnknownImageFormat:
                    width, height = 1, 1 
                res['proj_id'] = the_project.id
                res['sample_id'] = the_sample.id
                res['grain_num'] = the_grain
                res['ft_type'] = ft_type
                res['image_width'] = width
                res['image_height'] = height
                res['images'] = images_list
                res['rois'] = rois
                myjson = json.dumps(res, cls=DjangoJSONEncoder)
                return HttpResponse(myjson, content_type='application/json')
            else:
                # report error: cannot find images for grain
                if ftn is not None:
                    ftn.delete()
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
                                        latlngs=latlng_json_str,
            )
            fts.save()
            user = User.objects.get(username=request.user.username)
            project = Project.objects.get(id=res_dic['proj_id'])
            # Remove any partial save state
            FissionTrackNumbering.objects.filter(
                worker=user,
                result=-1,
            ).delete()
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
    if request.is_ajax() and request.user.is_active:
        with transaction.atomic():
            user = User.objects.get(username=request.user.username)
            # Remove any previous partial save state
            FissionTrackNumbering.objects.filter(
                worker=user,
                result=-1,
            ).delete()
            json_str = request.body.decode(encoding='UTF-8')
            res_json = json.loads(json_str)
            res = res_json['intermedia_res']
            sample = Sample.objects.get(id=res['sample_id'])
            ftn = FissionTrackNumbering(
                in_sample=sample,
                grain=res['grain_num'],
                ft_type='S',
                worker=user,
                result=-1,
                latlngs=res['marker_latlngs'],
            )
            ftn.save()
        myjson = json.dumps({ 'reply' : 'Done and thank you' }, cls=DjangoJSONEncoder)
        return HttpResponse(myjson, content_type='application/json')
    else:
        return HttpResponse("Sorry, You have to active your account first.")

