from django.shortcuts import render, get_object_or_404
from django.db import transaction
from django.db.models import Q
from django.db.models.aggregates import Max
from django.forms import (ModelForm, CharField, Textarea, FileField,
    ClearableFileInput, ValidationError)
from django.views.decorators.csrf import csrf_protect
from django.views.generic.edit import CreateView, UpdateView
from django.views.generic import DetailView
from django.urls import reverse
from django.http import (HttpResponse, HttpResponseRedirect,
    HttpResponseForbidden, HttpResponseNotFound)
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import redirect

from ftc.parse_image_name import parse_image_name
from ftc.get_image_size import get_image_size_from_handle
from geochron.settings import IMAGE_UPLOAD_SIZE_LIMIT

import base64
import io
import json

from ftc.models import (Project, Sample, FissionTrackNumbering, Image, Grain,
    TutorialResult, Region, Vertex)

#
def home(request):
    return render(request, 'ftc/home.html', {})

# the view for /accounts/profile/
def profile(request):
    if request.user.is_authenticated:
        return render(request, 'ftc/profile.html', {
            'tutorial_completed': tutorialCompleted(request)
        })
    else:
        return redirect('account_login') # 'home'

def signmeup(request):
    if request.user.username == 'guest':
        # logout guest
        logout(request)
    return redirect('account_signup')

def tutorial(request):
    return render(request, 'ftc/tutorial.html')

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
            return HttpResponse("you have no project currrently. add one?", status=204)
        else:
            return render(request, 'ftc/report.html', {'projects': projects})
    else:
        return HttpResponse("Sorry, You don't have permission to access the requested page.",
            status=403)


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
        self.object = self.model.objects.get(pk=self.kwargs['pk'])
        return (
            self.request.user == self.object.get_owner()
            or self.request.user.is_superuser
        )


class ParentCreatorOrSuperuserMixin(UserPassesTestMixin):
    """
    Allows the user to view if s/he is superuser or the creator
    of the parent class with pk=kwargs['pk'].
    Also sets self.parent to this object, and provides it as a
    context variable 'parent'.
    Set parent=ModelClass in the derived class, and ensure
    that this mixin is placed before the CreateView class
    in the base classes list of your derived class.
    """
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['parent'] = self.parent_object
        return ctx

    def test_func(self):
        self.parent_object = self.parent.objects.get(pk=self.kwargs['pk'])
        return (
            self.request.user == self.parent_object.get_owner()
            or self.request.user.is_superuser
        )


class ProjectDetailView(StaffRequiredMixin, DetailView):
    model = Project
    template_name = "ftc/project.html"


class ProjectForm(ModelForm):
    class Meta:
        model = Project
        fields = ['project_name', 'project_description', 'priority', 'closed']
    project_description = CharField(widget=Textarea)


class ProjectCreateView(StaffRequiredMixin, CreateView):
    model = Project
    form_class = ProjectForm
    template_name = "ftc/project_create.html"

    def form_valid(self, form):
        form.instance.creator = self.request.user
        return super().form_valid(form)


class ProjectUpdateView(CreatorOrSuperuserMixin, UpdateView):
    model = Project
    form_class = ProjectForm
    template_name = "ftc/project_update.html"


class SampleDetailView(CreatorOrSuperuserMixin, DetailView):
    model = Sample
    template_name = "ftc/sample.html"


class SampleCreateView(ParentCreatorOrSuperuserMixin, CreateView):
    model = Sample
    parent = Project
    template_name = "ftc/sample_create.html"
    fields = ['sample_name', 'sample_property', 'priority', 'min_contributor_num', 'completed']

    def form_valid(self, form):
        form.instance.total_grains = 0
        form.instance.in_project = self.parent_object
        return super().form_valid(form)


class SampleUpdateView(CreatorOrSuperuserMixin, UpdateView):
    model = Sample
    template_name = "ftc/sample_update.html"
    fields = ['sample_name', 'sample_property', 'priority', 'min_contributor_num', 'completed']


class GrainDetailView(StaffRequiredMixin, DetailView):
    model = Grain
    template_name = "ftc/grain.html"


class CrystalImageInput(ClearableFileInput):
    def value_from_datadict(self, data, files, name):
        return files.getlist(name)


def validate_file_image(f):
    if not parse_image_name(f.name):
        raise ValidationError(
            'File %(fn)s is not called image<nn> or refl-image',
            params={'fn': f.name},
            code='bad-image-file-name'
        )
    if IMAGE_UPLOAD_SIZE_LIMIT < f.size:
        raise ValidationError(
            "File '%(fn)s' is too large",
            params={'fn': f.name},
            code='file-too-large'
        )


class ImageStackField(FileField):
    def clean(self, data, initial):
        s = super()
        return [s.clean(d, initial) for d in data]


class GrainForm(ModelForm):
    class Meta:
        model = Grain
        fields = ['images']

    images = ImageStackField(
        widget=CrystalImageInput(attrs={'multiple': True}),
        validators=[validate_file_image])

    def clean(self):
        files = []
        errors = []
        images = 'images' in self.cleaned_data and self.cleaned_data['images'] or []
        for f in images:
            v = parse_image_name(f.name)
            data = f.read()
            size = get_image_size_from_handle(io.BytesIO(data), len(data))
            if size:
                files.append({
                    'name': f.name,
                    'data': data,
                    'width': size[0],
                    'height': size[1],
                    'index': v['index'],
                    'format': v['format']
                })
            else:
                errors.append(
                    ValidationError(
                        "File '%(fn)s' neither a Jpeg nor a PNG",
                        params={'fn': f.name},
                        code='unknown-file-format'
                    )
                )
        if errors:
            raise ValidationError(errors)
        self.cleaned_data['files'] = files
        return self.cleaned_data

    def save(self, commit=True):
        max_index = self.sample.grain_set.aggregate(Max('index'))['index__max']
        if not max_index:
            max_index = 0
        self.instance.index = max_index + 1
        max_w = 0
        max_h = 0
        for f in self.cleaned_data['files']:
            w = f['width']
            if max_w < w:
                max_w = w
            h = f['height']
            if max_h < h:
                max_h = h
        self.instance.image_width = max_w
        self.instance.image_height = max_h
        self.instance.sample = self.sample
        region = Region(grain=self.instance, shift_x=0, shift_y=0)
        x_margin = int(max_w / 20)
        y_margin = int(max_h / 20)
        v0 = Vertex(region=region, x=x_margin, y=y_margin)
        v1 = Vertex(region=region, x=x_margin, y=max_h-y_margin)
        v2 = Vertex(region=region, x=max_w-x_margin, y=max_h-y_margin)
        v3 = Vertex(region=region, x=max_w-x_margin, y=y_margin)
        inst = super().save(commit)
        if commit:
            region.save()
            v0.save()
            v1.save()
            v2.save()
            v3.save()
        return inst


class GrainCreateView(ParentCreatorOrSuperuserMixin, CreateView):
    model = Grain
    parent = Sample
    form_class = GrainForm
    template_name = "ftc/grain_create.html"

    def post(self, request, *args, **kwargs):
        self.object = None
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        form.sample = self.parent_object
        if not form.is_valid():
            return self.form_invalid(form)
        rtn = self.form_valid(form)
        with transaction.atomic():
            for f in form.cleaned_data['files']:
                image = Image(
                    grain=self.object,
                    format=f['format'],
                    ft_type='S',
                    index=f['index'],
                    data=f['data']
                ).save()
        return rtn

    def get_success_url(self):
        return reverse('grain', kwargs={'pk': self.object.pk})


@csrf_protect
@user_passes_test(user_is_staff)
def grain_update(request, pk):
    grain = Grain.objects.get(pk=pk)
    if not request.user.is_superuser and not request.user == grain.sample.in_project.creator:
        return HttpResponse("Grain update forbidden", status=403)
    regions = {}
    for k,v in request.POST.items():
        ps = k.rsplit("_", 3)
        if (len(ps) == 4
            and ps[0] == "vertex"
            and ps[1].isnumeric()
            and ps[2].isnumeric()
            and ps[3] in ['x','y']):
            region_number = int(ps[1])
            if region_number not in regions:
                regions[region_number] = {}
            region = regions[region_number]
            vertex_number = int(ps[2])
            if vertex_number not in region:
                region[vertex_number] = {}
            vertex = region[vertex_number]
            if ps[3] not in vertex:
                vertex[ps[3]] = {}
            vertex[ps[3]] = v

    w = grain.image_width
    h = grain.image_height
    with transaction.atomic():
        Region.objects.filter(grain=grain).delete()
        for _, vertices in sorted(regions.items()):
            region = Region(grain=grain, shift_x=0, shift_y=0)
            region.save()
            for _, v in sorted(vertices.items()):
                x = float(v['x']) * w
                y = h - float(v['y']) * w
                vertex = Vertex(region=region, x=x, y=y)
                vertex.save()

    return redirect('grain', pk=pk)


@login_required
def getTableData(request):
    if request.user.is_active and request.user.is_staff:
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
from .grain_uinfo import choose_working_grain, restore_grain_uinfo
from .load_rois import load_rois

@login_required
def get_image(request, pk):
    image = get_object_or_404(Image, pk=pk)
    mime = image.format = 'P' and 'image/png' or 'image/jpeg'
    return HttpResponse(image.data, content_type=mime)

def redirect_to_count(request):
    res = {}
    grain = None
    if request.user.is_active:
        partial_save = FissionTrackNumbering.objects.filter(
            result=-1,
            worker=request.user
        ).first()
        if partial_save != None:
            grain = Grain.objects.filter(
                sample=partial_save.in_sample,
                index=partial_save.grain
            ).first()
    if grain == None:
        grain = choose_working_grain(request)
    if grain != None:
        return HttpResponseRedirect(reverse('count', args=[grain.pk]))
    return HttpResponseRedirect(reverse('count', args=['done']))

def get_grain_info(request, pk):
    if pk == 'done':
        return {
            'grain_info': 'null',
            'messages': ['All grains complete, congratulations!']
        }
    grain = Grain.objects.get(pk=pk)
    save = FissionTrackNumbering.objects.filter(
        worker=request.user,
        grain=grain.index,
        in_sample=grain.sample
    ).order_by('result').first()
    the_project = grain.sample.in_project
    the_sample = grain.sample
    the_grain = grain.index
    ft_type = 'S' # should be grain.sample.sample_property
    images_list = get_grain_images_list(
        the_project.project_name,
        the_sample.sample_name,
        the_sample.sample_property,
        the_grain,
        ft_type
    )
    rois = None
    if len(images_list) > 0:
        rois = load_rois(
            the_project.project_name,
            the_sample.sample_name,
            the_sample.sample_property,
            the_grain,
            ft_type
        )
    if rois is None:
        return {
            'grain_info': 'null',
            'messages': [
                "[Project: {0}, Sample: {1}, Grain #: {2}, FT_type: {3}] has no images or has no ROIs\n".format(
                        the_project.project_name, the_sample.sample_name, the_grain, ft_type
                ) + "Refresh page to load another Grain."]
        }
    try:
        gs = Grain.objects.filter(index=the_grain,
            sample__sample_name=the_sample.sample_name,
            sample__in_project__project_name=the_project.project_name)
        width = gs[0].image_width
        height = gs[0].image_height
    except UnknownImageFormat:
        width, height = 1, 1
    info = {
        'proj_id': the_project.id,
        'sample_id': the_sample.id,
        'grain_num': the_grain,
        'ft_type': ft_type,
        'image_width': width,
        'image_height': height,
        'scale_x': grain.scale_x,
        'images': images_list,
        'rois': rois
    }
    if save:
        latlngs = json.loads(save.latlngs)
        info['marker_latlngs'] = latlngs
        info['num_markers'] = len(latlngs)
    return { 'grain_info': json.dumps(info), 'messages': [] }


@login_required
def count_grain(request, pk):
    return render(request, 'ftc/counting.html', get_grain_info(request, pk))


from django.contrib.auth.models import User
def tutorialCompleted(request):
    if request.user.username == 'guest':
        return TutorialResult.objects.filter(session=request.session.session_key).exists()
    if request.user.is_authenticated:
        return TutorialResult.objects.filter(user=request.user).exists()
    return False


def counting(request, uname=None):
    if request.user.is_authenticated:
        if tutorialCompleted(request):
            return redirect_to_count(request)
        return render(request, 'ftc/profile.html', {
            'tutorial_completed': False
        })
    elif uname == 'guest':
        passwd = 'guestsitest'
        user = User.objects.get(username__exact='guest')
        user.set_password(passwd)
        user.save()
        user = authenticate(username='guest', password=passwd)
        login(request, user)
    return render(request, 'ftc/profile.html', {
        'tutorial_completed': tutorialCompleted(request)
    })


@login_required
def updateTFNResult(request):
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    sep = '~'
    if request.user.is_active:
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
                in_sample=sample,
                grain=res_dic['grain_num'],
                worker=user,
                result=-1,
            ).delete()
        except (KeyError, Project.DoesNotExist):
            return HttpResponseNotFound("you have no project currrently.")
        else:
            myjson = json.dumps({ 'reply' : 'Done and thank you' }, cls=DjangoJSONEncoder)
            return HttpResponse(myjson, content_type='application/json')
    else:
        return HttpResponseForbidden("Sorry, You have to active your account first.")

import sys
import fnmatch
@login_required
def saveWorkingGrain(request):
    if request.user.is_active:
        with transaction.atomic():
            user = User.objects.get(username=request.user.username)
            json_str = request.body.decode(encoding='UTF-8')
            res_json = json.loads(json_str)
            res = res_json['intermedia_res']
            sample = Sample.objects.get(id=res['sample_id'])
            # Remove any previous partial save state
            FissionTrackNumbering.objects.filter(
                in_sample=sample,
                grain=res['grain_num'],
                worker=user,
                result=-1,
            ).delete()
            # Save the new state
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

@login_required
def saveTutorialResult(request):
    if request.user.is_active:
        tr = TutorialResult(
            user=request.user,
            session=request.session.session_key
        )
        tr.save()
        return HttpResponse("OK")
