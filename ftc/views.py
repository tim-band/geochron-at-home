from django.shortcuts import render, get_object_or_404
from django.db import transaction
from django.db.models import Exists, OuterRef, Q, Subquery
from django.db.models.aggregates import Max
from django.forms import (ModelForm, CharField, Textarea, FileField,
    ClearableFileInput, ValidationError)
from django.views.decorators.csrf import csrf_protect
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.views.generic import DetailView
from django.urls import reverse
from django.http import (HttpResponse, HttpResponseRedirect,
    HttpResponseForbidden, HttpResponseNotFound)
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import redirect

from ftc.parse_image_name import parse_upload_name
from ftc.get_image_size import get_image_size_from_handle
from geochron.gah import parse_metadata_grain, parse_metadata_image
from geochron.settings import IMAGE_UPLOAD_SIZE_LIMIT

import base64
import io
import json
import sys

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


class GrainDetailUpdateView(CreatorOrSuperuserMixin, UpdateView):
    model = Grain
    template_name = "ftc/grain_update_meta.html"
    fields = [
        'index', 'image_width', 'image_height',
        'scale_x', 'scale_y', 'stage_x', 'stage_y', 'shift_x', 'shift_y'
    ]


class StackImageInput(ClearableFileInput):
    def value_from_datadict(self, data, files, name):
        return files.getlist(name)


def validate_file_image(f):
    if parse_upload_name(f.name) is None:
        raise ValidationError(
            'File %(fn)s is not an expected image or metadata name',
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
        fields = ['uploads']

    uploads = ImageStackField(
        widget=StackImageInput(attrs={'multiple': True}),
        validators=[validate_file_image])

    def set_rois(self, upload, info):
        try:
            rois_json = json_decoder.decode(upload.read())
            regions = rois_json['regions']
            region = regions[0]
            self.rois = {
                'shift_x': region['shift'][0] if region else 0,
                'shift_y': region['shift'][1] if region else 0,
                'image_width': rois_json['image_width'],
                'image_height': rois_json['image_height'],
                'scale_x': rois_json.get('scale_x'),
                'scale_y': rois_json.get('scale_y'),
                'stage_x': rois_json.get('stage_x'),
                'stage_y': rois_json.get('stage_y'),
                'regions': regions
            }
        except Exception as e:
            self.validationerrors.append(ValidationError(
                "Parsing for ROI file '%(fn)s' failed: %(message)s",
                params={'fn': upload.name, 'message': str(e)},
                code='rois-file-parse'
            ))

    def set_grain_meta(self, upload):
        try:
            m = parse_metadata_grain(upload)
            self.grain_meta = m
        except Exception as e:
            self.validationerrors.append(ValidationError(
                "Parsing for metadata file '%(fn)s' failed: %(message)s",
                params={'fn': upload.name, 'message': str(e)},
                code='metadata-file-parse'
            ))

    def set_image_data(self, info, data):
        ims = self.images[info['ft_type']]
        index = info['index']
        if index not in ims:
            ims[index] = {}
        ims[index].update(data)

    def add_meta(self, upload, info):
        try:
            m = parse_metadata_image(upload)
            self.set_image_data(info, {
                'index': info['index'],
                'ft_type': info['ft_type'],
                'light_path': m['light_path'],
                'focus': m['focus']
            })
        except Exception as e:
            self.validationerrors.append(ValidationError(
                "Parsing for metadata file '%(fn)s' failed: %(message)s",
                params={'fn': upload.name, 'message': str(e)},
                code='metadata-file-parse'
            ))

    def add_image(self, upload, info):
        data = upload.read()
        size = get_image_size_from_handle(io.BytesIO(data), len(data))
        if not size:
            self.validationerrors.append(
                ValidationError(
                    "File '%(fn)s' neither a Jpeg nor a PNG file",
                    params={'fn': upload.name},
                    code='unknown-file-format'
                )
            )
        else:
            if self.max_width < size[0]:
                self.max_width = size[0]
            if self.max_height < size[1]:
                self.max_height = size[1]
            self.set_image_data(info, {
                'data': data,
                'index': info['index'],
                'format': info['format'],
                'ft_type': info['ft_type']
            })

    def clean(self):
        self.images = {
            # Spontaneous Track image information keyed by index
            'S': {},
            # Induced Track image information keyed by index
            'I': {}
        }
        self.rois = None
        self.grain_meta = None
        self.validationerrors = []
        self.max_width = 0
        self.max_height = 0
        uploads = self.cleaned_data['uploads'] if 'uploads' in self.cleaned_data else []
        json_decoder = json.JSONDecoder(strict=False)
        for upload in uploads:
            v = parse_upload_name(upload.name)
            if v is None:
                self.validationerrors.append(ValidationError(
                    "File '%(fn)s' is not a recognized name",
                    params={'fn': upload.name},
                    code='unknown-file-name'
                ))
            else:
                if v['rois']:
                    if self.rois is None:
                        self.set_rois(upload, v)
                elif v['meta']:
                    self.add_meta(upload, v)
                    if self.grain_meta is None:
                        self.set_grain_meta(upload)
                else:
                    self.add_image(upload, v)
        if self.validationerrors:
            raise ValidationError(self.validationerrors)
        self.cleaned_data['images'] = self.images
        self.cleaned_data['rois'] = self.rois
        if self.grain_meta is not None:
            self.cleaned_data.update(self.grain_meta)
        else:
            if 0 < self.max_width:
                self.cleaned_data['image_width'] = self.max_width
            if 0 < self.max_height:
                self.cleaned_data['image_height'] = self.max_height
        return self.cleaned_data

    def next_grain_number(self, sample):
        """
        Set the grain number to the next available number
        """
        self.sample = sample
        max_index = sample.grain_set.aggregate(Max('index'))['index__max']
        if not max_index:
            max_index = 0
        self.grain_index = max_index + 1

    def explicit_grain(self, grain):
        """
        Set the grain explicitly
        """
        self.sample = None
        self.grain = grain
        self.grain_index = grain.index

    def delete_regions(self):
        regions = self.instance.region_set.delete()

    def save_region(self, vertices, commit=True):
        region = Region(grain=self.instance)
        if commit:
            region.save()
        for v in vertices:
            vertex = Vertex(region=region, x=v[0], y=v[1])
            if commit:
                vertex.save()

    def save_images(self):
        for (ft_type, ims) in self.cleaned_data['images'].items():
            for (index, f) in ims.items():
                Image.objects.update_or_create(
                    grain=self.instance,
                    index=index,
                    ft_type=ft_type,
                    defaults=f
                )

    def save(self, commit=True):
        self.instance.index = self.grain_index
        if self.sample is not None:
            self.instance.sample = self.sample
        for attr in ['image_width', 'image_height', 'scale_x', 'scale_y',
            'stage_x', 'stage_y', 'shift_x', 'shift_y']:
            if attr in self.cleaned_data:
                setattr(self.instance, attr, self.cleaned_data[attr])
        inst = super().save(commit)
        rois = self.cleaned_data['rois']
        if rois is not None:
            self.delete_regions()
            for region in rois['regions']:
                if 'vertices' in region:
                    self.save_region(region['vertices'], commit)
        self.save_images()
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
        if not form.is_valid():
            return self.form_invalid(form)
        form.next_grain_number(self.parent_object)
        rtn = self.form_valid(form)
        if 'rois' not in form.cleaned_data or form.cleaned_data['rois'] is None:
            width = form.cleaned_data['image_width']
            height = form.cleaned_data['image_height']
            margin_x = width / 20
            margin_y = height / 20
            form.save_region([
                [margin_x,margin_y],
                [width - margin_x, margin_y],
                [width - margin_x, height - margin_y],
                [margin_x, height - margin_y]
            ])
        return rtn

    def get_success_url(self):
        return reverse('grain', kwargs={'pk': self.object.pk})


class GrainImagesView(CreatorOrSuperuserMixin, UpdateView):
    model = Grain
    template_name = "ftc/grain_images.html"
    form_class = GrainForm
    #fields = ["index", "image_width", "image_height", "scale_x", "scale_y", "stage_x", "stage_y"]
    def post(self, request, *args, **kwargs):
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        form.explicit_grain(self.object)
        if not form.is_valid():
            return self.form_invalid(form)
        return self.form_valid(form)

    def get_success_url(self):
        return reverse('grain_images', kwargs={'pk': self.object.pk})

@csrf_protect
@user_passes_test(user_is_staff)
def grain_update_roi(request, pk):
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
            region = Region(grain=grain)
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

def get_grain_info(request, pk, **kwargs):
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
        'images_crystal': images_list,
        'images_mica': [],
        'rois': rois
    }
    if save:
        latlngs = json.loads(save.latlngs)
        info['marker_latlngs'] = latlngs
        info['num_markers'] = len(latlngs)
    return {
        'grain_info': json.dumps(info),
        'messages': [],
        **kwargs
    }


@login_required
def count_grain(request, pk):
    return render(
        request,
        'ftc/counting.html',
        get_grain_info(request, pk, submit_url=reverse('counting'))
    )


def count_my_grain_extra_links(user, current_id):
    current_grain = Grain.objects.get(id=current_id)
    sample = current_grain.sample
    project = sample.in_project
    index = current_grain.index
    done_query = Subquery(FissionTrackNumbering.objects.filter(
        worker=user,
        in_sample=sample,
        grain=OuterRef('index'),
        result__gte=0
    ))
    next_grain = Grain.objects.annotate(
        done=Exists(done_query)
    ).filter(
        sample__in_project__creator=user,
        sample__in_project=project,
        sample=sample,
        index__gt=index,
        done=False
    ).order_by(
        'index'
    ).first()
    prev_grain = Grain.objects.annotate(
        done=Exists(done_query)
    ).filter(
        sample__in_project__creator=user,
        sample__in_project=project,
        sample=sample,
        index__lt=index,
        done=False
    ).order_by(
        '-index'
    ).first()
    back = reverse('grain', args=[current_id])
    r = {
        'submit_url': back,
        'cancel_url': back
    }
    if next_grain != None:
        url = reverse('count_my', args=[next_grain.id])
        r['next_url'] = url
        r['submit_url'] = url
    if prev_grain != None:
        r['prev_url'] = reverse('count_my', args=[prev_grain.id])
    return r

class ImageDeleteView(CreatorOrSuperuserMixin, DeleteView):
    model = Image
    template_name = "ftc/image_delete.html"
    def get_success_url(self):
        return reverse('grain_images', args=[self.object.grain_id])

class CountMyGrainView(CreatorOrSuperuserMixin, DetailView):
    model = Grain
    template_name = "ftc/counting.html"
    def get_context_data(self, **kwargs):
        pk = self.kwargs['pk']
        ctx = super().get_context_data(**kwargs)
        ctx.update(get_grain_info(
            self.request,
            pk,
            **count_my_grain_extra_links(self.request.user, pk)
        ))
        return ctx

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
@transaction.atomic
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
            # Remove any previous or partial save state
            FissionTrackNumbering.objects.filter(
                in_sample=sample,
                grain=res_dic['grain_num'],
                worker=request.user,
            ).delete()
            fts = FissionTrackNumbering(in_sample=sample, 
                                        grain=res_dic['grain_num'], 
                                        ft_type=res_dic['ft_type'], 
                                        worker=request.user, 
                                        result=res_dic['track_num'],
                                        latlngs=latlng_json_str,
            )
            fts.save()
            project = Project.objects.get(id=res_dic['proj_id'])
        except (KeyError, Project.DoesNotExist):
            return HttpResponseNotFound("you have no project currrently.")
        else:
            myjson = json.dumps({ 'reply' : 'Done and thank you' }, cls=DjangoJSONEncoder)
            return HttpResponse(myjson, content_type='application/json')
    else:
        return HttpResponseForbidden("Sorry, You have to active your account first.")

@login_required
@transaction.atomic
def saveWorkingGrain(request):
    if request.user.is_active:
        with transaction.atomic():
            user = User.objects.get(username=request.user.username)
            json_str = request.body.decode(encoding='UTF-8')
            res_json = json.loads(json_str)
            res = res_json['intermedia_res']
            sample = Sample.objects.get(id=res['sample_id'])
            # Remove any previous or partial save state
            FissionTrackNumbering.objects.filter(
                in_sample=sample,
                grain=res['grain_num'],
                worker=user,
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
