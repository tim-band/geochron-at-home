from typing import Any, Dict
from django.shortcuts import render, get_object_or_404
from django.db import transaction
from django.db.models import Exists, OuterRef, Q, Subquery, Prefetch
from django.db.models.aggregates import Max
from django.forms import (ModelForm, CharField, Textarea, FileField,
    ClearableFileInput, ValidationError)
from django.views.decorators.csrf import csrf_protect
from django.views.generic import DetailView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.views.generic.list import ListView
from django.urls import reverse
from django.http import (HttpResponse, HttpResponseRedirect,
    HttpResponseForbidden)
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import redirect

from ftc.apiviews import request_roiss
from ftc.get_image_size import get_image_size_from_handle
from ftc.load_rois import get_rois
from ftc.models import (Project, Sample, FissionTrackNumbering, Image, Grain,
    TutorialResult, Region, Vertex, GrainPointCategory,
    TutorialPage)
from ftc.parse_image_name import parse_upload_name
from geochron.gah import parse_metadata_grain, parse_metadata_image
from geochron.settings import IMAGE_UPLOAD_SIZE_LIMIT

import csv
import io
import json

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
    # old style tutorial
    #return render(request, 'ftc/tutorial.html')
    tp = TutorialPage.objects.filter(active=True).order_by('sequence_number', 'pk').first()
    return redirect('tutorial_page', tp.pk)

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
        form.instance.in_project = self.parent_object
        return super().form_valid(form)


class SampleUpdateView(CreatorOrSuperuserMixin, UpdateView):
    model = Sample
    template_name = "ftc/sample_update.html"
    fields = [
        'sample_name',
        'sample_property',
        'priority',
        'min_contributor_num',
        'completed',
        'public'
    ]


def json_array(arr):
    return '[' + ','.join(arr) + ']'


class GrainDetailView(StaffRequiredMixin, DetailView):
    model = Grain
    template_name = "ftc/grain.html"
    ft_type = 'S'
    def json_latlng(self, lat, lng):
        return '[{0},{1}]'.format(lat, lng)
    def get_shift(self):
        return [0, 0]
    def get_regions_json(self, w, h):
        return json_array([
            json_array([
                self.json_latlng((h - vertex.y) / w, vertex.x / w)
                for vertex in region.vertex_set.order_by('id').iterator()
            ])
            for region in self.object.region_set.order_by('id').iterator()
        ])
    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx['images'] = self.object.image_set.filter(ft_type=self.ft_type).order_by('index')
        ctx['ft_type'] = self.ft_type
        w = self.object.image_width
        h = self.object.image_height
        ctx['regions'] = self.get_regions_json(w, h)
        shift = self.get_shift()
        ctx['shift_x'] = shift[0]
        ctx['shift_y'] = shift[1]
        return ctx

class MicaDetailView(GrainDetailView):
    ft_type = 'I'
    def json_latlng(self, lat, lng):
        m = self.mica_matrix
        if m:
            x = lng - 0.5
            y = lat - 0.5
            lng = 0.5 + x * m.x0 + y * m.y0
            lat = 0.5 + x * m.x1 + y * m.y1
        else:
            lng = 1 - lng
        return '[{0},{1}]'.format(lat, lng)
    def get_context_data(self, *args, **kwargs):
        self.mica_matrix = self.object.mica_transform_matrix
        return super().get_context_data(*args, **kwargs)
    def get_shift(self):
        return [self.object.shift_x, self.object.shift_y]


class GrainDetailUpdateView(CreatorOrSuperuserMixin, UpdateView):
    model = Grain
    template_name = "ftc/grain_update_meta.html"
    fields = [
        'index', 'image_width', 'image_height',
        'scale_x', 'scale_y', 'stage_x', 'stage_y', 'shift_x', 'shift_y',
        'mica_stage_x', 'mica_stage_y'
    ]


class StackImageInput(ClearableFileInput):
    allow_multiple_selected = True
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
        json_decoder = json.JSONDecoder(strict=False)
        try:
            data = upload.read()
            rois_json = json_decoder.decode(data.decode('utf-8'))
            regions = rois_json['regions']
            region = regions[0]
            self.rois = {
                'shift_x': region['shift'][0] if region else None,
                'shift_y': region['shift'][1] if region else None,
                'image_width': rois_json['image_width'],
                'image_height': rois_json['image_height'],
                'scale_x': rois_json.get('scale_x'),
                'scale_y': rois_json.get('scale_y'),
                'stage_x': rois_json.get('stage_x'),
                'stage_y': rois_json.get('stage_y'),
                'mica_stage_x': rois_json.get('mica_stage_x'),
                'mica_stage_y': rois_json.get('mica_stage_y'),
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
                        upload.seek(0)
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
        if self.rois is not None:
            for (k,v) in self.rois.items():
                if v is not None:
                    self.cleaned_data[k] = v
        if 'grain_index' in self.data:
            index = self.data['grain_index']
            if type(index) is list and 0 < len(index):
                index = index[0]
            try:
                self.grain_index = int(index)
            except Exception:
                pass
        return self.cleaned_data

    def next_grain_number(self, sample):
        """
        Set the grain number to the next available number
        """
        self.sample = sample
        if hasattr(self, 'grain_index'):
            return
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
        Region.objects.filter(grain=self.instance).delete()

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
                [margin_x, margin_y],
                [width - margin_x, margin_y],
                [width - margin_x, height - margin_y],
                [margin_x, height - margin_y]
            ])
        return rtn

    def get_success_url(self):
        return reverse('grain_images', kwargs={'pk': self.object.pk})

class GrainDeleteView(CreatorOrSuperuserMixin, DeleteView):
    model = Grain
    template_name = "ftc/grain_delete.html"
    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx['image_count'] = self.object.image_set.count()
        ctx['region_count'] = self.object.region_set.count()
        ctx['result_count'] = self.object.results.count()
        ctx['referrer'] = self.request.META.get(
            "HTTP_REFERER",
            reverse('sample', args=[self.object.sample.id])
        )
        return ctx
    def get_success_url(self):
        return reverse('sample', args=[self.object.sample.id])

class GrainImagesView(CreatorOrSuperuserMixin, UpdateView):
    model = Grain
    template_name = "ftc/grain_images.html"
    form_class = GrainForm
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
def tutorialPage(request, pk):
    tp = TutorialPage.objects.get(pk=pk)
    next = TutorialPage.objects.filter(
        Q(sequence_number__gt=tp.sequence_number) | (
            Q(sequence_number=tp.sequence_number) & Q(pk__gt=tp.pk)
        ),
        active=True
    ).order_by('sequence_number', 'pk').first()
    prev = TutorialPage.objects.filter(
        Q(sequence_number__lt=tp.sequence_number) | (
            Q(sequence_number=tp.sequence_number) & Q(pk__lt=tp.pk)
        ),
        active=True
    ).order_by('-sequence_number', '-pk').first()
    # The user is always the owner, because the user's own
    # count is where the tutorial data comes from.
    ctx = get_grain_info(
        tp.marks.grain.get_owner().id,
        tp.marks.grain.pk,
        'S',
        object=tp,
        next_page=next,
        prev_page=prev
    )
    addGrainPointCategories(ctx)
    return render(request, 'ftc/tutorial_page.html', ctx)

@csrf_protect
def tutorialEnd(request):
    return render(request, 'ftc/tutorial_end.html')

@csrf_protect
def publicSample(request, sample, grain):
    g = Grain.objects.get(sample=sample, index=grain)
    user = g.sample.in_project.creator
    if not g.sample.public:
        # it's not public, but the creator is allowed to see it
        if not request.user.is_authenticated or user != request.user:
            raise PermissionDenied('This sample is not public')
    ft_type = 'S'
    result_query = Subquery(FissionTrackNumbering.objects.filter(
        worker=user,
        grain=OuterRef('id'),
        ft_type=ft_type,
        result__gte=0
    ))
    samples = Grain.objects.annotate(
        result_exists=Exists(result_query)
    ).filter(
        sample=sample,
        result_exists=True
    )
    next = samples.filter(
        index__gt=grain
    ).order_by('index').first()
    prev = samples.filter(
        index__lt=grain
    ).order_by('-index').first()
    ctx = get_grain_info(
        user,
        g.pk,
        ft_type,
        next_page=next,
        prev_page=prev
    )
    return render(request, 'ftc/public.html', ctx)

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

@csrf_protect
@user_passes_test(user_is_staff)
def grain_update_shift(request, pk):
    grain = Grain.objects.get(pk=pk)
    if not request.user.is_superuser and not request.user == grain.sample.in_project.creator:
        return HttpResponse("Grain update forbidden", status=403)
    grain.shift_x = int(request.POST['x'])
    grain.shift_y = int(request.POST['y'])
    grain.save()
    return redirect('mica', pk=pk)

@login_required
@user_passes_test(user_is_staff)
def getTableData(request):
    # http://owtrsnc.blogspot.co.uk/2013/12/sending-ajax-data-json-to-django.html
    # http://jonblack.org/2012/06/22/django-ajax-class-based-views/
    # assuming request.body contains json data which is UTF-8 encoded
    json_str = request.body.decode(encoding='UTF-8')
    # turn the json bytestr into a python obj
    json_obj = json.loads(json_str)
    sample_list = json_obj['client_response']
    res = []
    ftq = FissionTrackNumbering.objects.filter(result__gte=0)
    if not request.user.is_superuser:
        ftq = ftq.filter(grain__sample__in_project__creator=request.user)
    for sample_id in sample_list:
        fts = ftq.filter(
            grain__sample=sample_id
        ).select_related(
            'grain__sample__in_project'
        )
        for ft in fts:
            a = [
                ft.grain.sample.in_project.project_name,
                ft.grain.sample.sample_name,
                ft.grain.index,
                ft.ft_type,
                ft.result,
                ft.worker.username,
                ft.create_date,
                ft.roi_area_micron2(),
            ]
            res.append(a)
    return HttpResponse(
        json.dumps({ 'aaData' : res }, cls=DjangoJSONEncoder),
        content_type='application/json'
    )

def json_grain_result(grain):
    res = []
    for result in grain.results.all():
        res.append({
            'ft_type': result.ft_type,
            'result': result.result,
            'create_date': result.create_date,
            'worker': {
                'id': result.worker.id
            },
            'latlngs': result.get_latlngs()
        })
    j = {
        'grain': grain.id,
        'sample': grain.sample.id,
        'sample_name': grain.sample.sample_name,
        'project_name': grain.sample.in_project.project_name,
        'results': res,
        'area_pixels': grain.roi_area_pixels(),
        'area_mm2': grain.roi_area_mm2()
    }
    for field in [
        'id', 'index', 'image_width', 'image_height',
        'scale_x', 'scale_y', 'stage_x', 'stage_y',
        'mica_stage_x', 'mica_stage_y', 'shift_x', 'shift_y',
    ]:
        j[field] = getattr(grain, field)
    return j

def getGrainsWithResults(request):
    gq = Grain.objects.filter(
        results__result__gte=0
    ).prefetch_related(
        Prefetch(
            lookup='results',
            queryset=FissionTrackNumbering.objects.filter(
                result__gte=0
            )
        ),
        'results__worker',
        'sample',
        'sample__in_project',
        'region_set',
        'region_set__vertex_set'
    )
    if 'samples[]' in request.GET:
        gq = gq.filter(
            sample__in=request.GET.getlist('samples[]')
        )
    if not request.user.is_superuser:
        gq = gq.filter(
            sample__in_project__creator=request.user.id
        )
    grains = {}
    for g in gq:
        if g.id not in grains:
            grains[g.id] = g
    return grains

@login_required
@user_passes_test(user_is_staff)
def download_rois(request, pk):
    grain = Grain.objects.get(id=pk)
    return HttpResponse(
        json.dumps(get_rois(grain)),
        content_type='application/json'
    )

@login_required
@user_passes_test(user_is_staff)
def download_roiss(request):
    return HttpResponse(
        json.dumps(request_roiss(request)),
        content_type='application/json'
    )

@login_required
@user_passes_test(user_is_staff)
def getJsonResults(request):
    grains = getGrainsWithResults(request)
    result = [json_grain_result(g) for g in grains.values()]
    return HttpResponse(
        json.dumps(result, cls=DjangoJSONEncoder),
        content_type='application/json'
    )

@login_required
@user_passes_test(user_is_staff)
def getCsvResults(request):
    grains = getGrainsWithResults(request)
    response = HttpResponse(
        content_type='text/csv',
        headers={
            'Content-Disposition': 'attachment; filename="results.csv"'
        }
    )
    writer = csv.writer(response)
    writer.writerow([
        'project_name',
        'sample_name',
        'index',
        'ft_type',
        'user_id',
        'create_date',
        'count',
        'area_pixels',
        'area_mm2'
    ])
    for grain in grains.values():
        for result in grain.results.all():
            writer.writerow([
                grain.sample.in_project.project_name,
                grain.sample.sample_name,
                grain.index,
                result.ft_type,
                result.worker.pk,
                result.create_date,
                result.result,
                grain.roi_area_pixels(),
                grain.roi_area_mm2()
            ])
    return response


from .grain_uinfo import choose_working_grain
from .load_rois import load_rois

def get_grain_images_list(grain, ft_type):
    images = grain.image_set.filter(
        ft_type=ft_type
    ).order_by('index')
    return list(map(lambda x: reverse('get_image', args=[x.pk]), images))

def get_image(request, pk):
    image = get_object_or_404(Image, pk=pk)
    if not request.user.is_authenticated and not image.grain.sample.public:
        raise PermissionDenied('not a public image')
    mime = image.format = 'P' and 'image/png' or 'image/jpeg'
    return HttpResponse(image.data, content_type=mime)

def redirect_to_count(request):
    ft_type = 'S'  # At the moment we're only choosing minerals randomly
    grain = None
    if request.user.is_active:
        partial_save = FissionTrackNumbering.objects.filter(
            result=-1,
            ft_type=ft_type,
            worker=request.user
        ).first()
        if partial_save != None:
            grain = Grain.objects.filter(
                sample=partial_save.grain.sample,
                index=partial_save.grain.index
            ).first()
    if grain == None:
        grain = choose_working_grain(request, ft_type)
    if grain != None:
        return HttpResponseRedirect(reverse('count', args=[grain.pk]))
    return HttpResponseRedirect(reverse('count', args=['done']))

def add_grain_info_markers(info, grain, ft_type, worker):
    objects = FissionTrackNumbering.objects.filter(
        grain=grain,
        ft_type=ft_type
    )
    if worker is not None:
        objects = objects.filter(worker=worker)
    save = objects.order_by('result').first()
    if save:
        info['marker_latlngs'] = save.get_latlngs_within_roi()
        info['points'] = save.points()

def get_grain_info(user, pk, ft_type, **kwargs):
    if pk == 'done':
        return {
            'grain_info': 'null',
            'sample_id': None,
            'messages': ['All grains complete, congratulations!']
        }
    grain = Grain.objects.get(pk=pk)
    the_sample = grain.sample
    the_grain = grain.index
    ft_type = ft_type
    images_list = get_grain_images_list(grain, ft_type)
    matrix = grain.mica_transform_matrix if ft_type == 'I' else None
    rois = load_rois(grain, ft_type, matrix)
    if rois is None:
        return {
            'grain_info': 'null',
            'sample_id': the_sample.id,
            'messages': [
                "[Project: {0}, Sample: {1}, Grain #: {2}, FT_type: {3}] has no images or has no ROIs\n".format(
                        grain.sample.in_project.project_name,
                        the_sample.sample_name,
                        the_grain,
                        ft_type
                )]
        }
    info = {
        'sample_id': the_sample.id,
        'grain_num': the_grain,
        'ft_type': ft_type,
        'image_width': grain.image_width,
        'image_height': grain.image_height,
        'scale_x': grain.scale_x,
        'images': images_list,
        'rois': rois
    }
    add_grain_info_markers(info, grain, ft_type, user)
    return {
        'grain_info': json.dumps(info),
        'sample_id': the_sample.id,
        'messages': [],
        'track_count': len(info.get('marker_latlngs', [])),
        **kwargs
    }


@login_required
def count_grain(request, pk):
    return render(
        request,
        'ftc/counting.html',
        get_grain_info(request.user, pk, 'S', submit_url=reverse('counting'))
    )


def count_my_grain_extra_links(user, current_id, ft_type):
    current_grain = Grain.objects.get(id=current_id)
    sample = current_grain.sample
    project = sample.in_project
    index = current_grain.index
    done_query = Subquery(FissionTrackNumbering.objects.filter(
        worker=user,
        grain=OuterRef('id'),
        ft_type=ft_type,
        result__gte=0
    ))
    has_backref_image = Image.objects.filter(
        grain=OuterRef('pk'),
        ft_type=ft_type
    )
    next_grain = Grain.objects.annotate(
        done=Exists(done_query)
    ).filter(
        Q(Exists(has_backref_image)),
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
        Q(Exists(has_backref_image)),
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
    view_name = 'count_my_mica' if ft_type == 'I' else 'count_my'
    if next_grain != None:
        url = reverse(view_name, args=[next_grain.id])
        r['next_url'] = url
        r['submit_url'] = url
    if prev_grain != None:
        r['prev_url'] = reverse(view_name, args=[prev_grain.id])
    return r

class ImageDeleteView(CreatorOrSuperuserMixin, DeleteView):
    model = Image
    template_name = "ftc/image_delete.html"
    def get_success_url(self):
        return reverse('grain_images', args=[self.object.grain_id])

def addGrainPointCategories(ctx):
    ctx.update({ 'categories': [
        { 'name': gpc.name, 'description': gpc.description }
        for gpc in GrainPointCategory.objects.all()
    ]})

class CountMyGrainView(CreatorOrSuperuserMixin, DetailView):
    ft_type = 'S'
    model = Grain
    template_name = "ftc/counting.html"
    def get_context_data(self, **kwargs):
        pk = self.kwargs['pk']
        ctx = super().get_context_data(**kwargs)
        ctx.update(get_grain_info(
            self.request.user,
            pk,
            self.ft_type,
            **count_my_grain_extra_links(self.request.user, pk, self.ft_type)
        ))
        addGrainPointCategories(ctx)
        return ctx

class CountMyGrainMicaView(CountMyGrainView):
    ft_type = 'I'

from django.contrib.auth.models import User
def tutorialCompleted(request):
    if not TutorialPage.objects.filter(active=True).exists():
        return True
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


def addGrainPoints(ftn, res_dic):
    if 'points' in res_dic:
        ftn.addGrainPointsFromGrainPoints(res_dic['points'])
    else:
        ftn.addGrainPointsFromLatlngs(res_dic['marker_latlngs'])


def grainPointCount(res_dic):
    if 'points' in res_dic:
        return len(res_dic['points'])
    return len(res_dic['marker_latlngs'])


@login_required
@transaction.atomic
def updateFtnResult(request):
    if request.user.is_active:
        json_str = request.body.decode(encoding='UTF-8')
        res_dic = json.loads(json_str)
        grain = Grain.objects.get(
            sample__id=res_dic['sample_id'],
            index=res_dic['grain_num']
        )
        ft_type = res_dic['ft_type']
        fts = None
        if request.user.username != 'guest':
            has_backref_tutorial_page = TutorialPage.objects.filter(
                marks=OuterRef('pk')
            )
            # Remove any previous or partial save state that does not
            # have an attached TutorialPage
            FissionTrackNumbering.objects.filter(
                ~Q(Exists(has_backref_tutorial_page)),
                grain=grain,
                worker=request.user,
                ft_type=ft_type
            ).delete()
            # Remove all but one remaining previous or partial save states
            ftss = FissionTrackNumbering.objects.filter(
                grain=grain,
                worker=request.user,
                ft_type=ft_type
            )
            count = ftss.count()
            if 1 < count:
                ftss.limit(count - 1).delete()
            if 0 < count:
                fts = ftss.first()
        result = grainPointCount(res_dic)
        if fts is None:
            fts = FissionTrackNumbering(
                grain=grain,
                ft_type=ft_type,
                worker=request.user,
                result=result,
            )
        else:
            fts.result = result
        fts.save()
        addGrainPoints(fts, res_dic)
        myjson = json.dumps({ 'reply' : 'Done and thank you' }, cls=DjangoJSONEncoder)
        return HttpResponse(myjson, content_type='application/json')
    else:
        return HttpResponseForbidden("Sorry, you have to active your account first.")

@login_required
@transaction.atomic
def saveWorkingGrain(request):
    if request.user.is_active:
        with transaction.atomic():
            user = User.objects.get(username=request.user.username)
            json_str = request.body.decode(encoding='UTF-8')
            res = json.loads(json_str)
            grain = Grain.objects.get(sample__id=res['sample_id'], index=res['grain_num'])
            ft_type = res['ft_type']
            if user.username != 'guest':
                # Remove any previous or partial save state
                FissionTrackNumbering.objects.filter(
                    grain=grain,
                    worker=user,
                    ft_type=ft_type
                ).delete()
            # Save the new state
            ftn = FissionTrackNumbering(
                grain=grain,
                ft_type=ft_type,
                worker=user,
                result=-1,
            )
            ftn.save()
            addGrainPoints(ftn, res)
        myjson = json.dumps({ 'reply' : 'Done and thank you' }, cls=DjangoJSONEncoder)
        return HttpResponse(myjson, content_type='application/json')
    else:
        return HttpResponse("Sorry, you have to active your account first.")

@login_required
def saveTutorialResult(request):
    if request.user.is_active:
        tr = TutorialResult(
            user=request.user,
            session=request.session.session_key
        )
        tr.save()
        return HttpResponse("OK")

class TutorialForm(ModelForm):
    class Meta:
        model = TutorialPage
        fields = ['marks', 'category', 'page_type', 'limit', 'message', 'active', 'sequence_number']
    message = CharField(widget=Textarea)
    def __init__(self, initial, **kwargs):
        super().__init__(initial=initial, **kwargs)

def add_request_parameter(initial_out, request, key):
    v = request.GET.get(key, None)
    if v is None:
        return
    if type(v) is list:
        if len(v) == 0:
            return
        v = v[0]
    initial_out[key] = v

class TutorialCreateView(StaffRequiredMixin, CreateView):
    model = TutorialPage
    form_class = TutorialForm
    template_name = "ftc/tutorial_create.html"
    def get_initial(self):
        initial = {}
        add_request_parameter(initial, self.request, 'marks')
        return initial
    def get_success_url(self):
        return reverse('tutorial_pages_of', kwargs={
            'grain_id': self.object.marks.grain.pk,
            'user': self.object.marks.grain.sample.in_project.creator
        })

class TutorialUpdateView(StaffRequiredMixin, UpdateView):
    model = TutorialPage
    form_class = TutorialForm
    template_name = "ftc/tutorial_update.html"
    def get_success_url(self):
        return reverse('tutorial_pages_of', kwargs={
            'grain_id': self.object.marks.grain.pk,
            'user': self.object.marks.grain.sample.in_project.creator
        })

class TutorialListView(StaffRequiredMixin, ListView):
    model = TutorialPage
    template_name = "ftc/tutorial_list.html"
    def get_queryset(self):
        return TutorialPage.objects.filter(
            marks__worker__username=self.kwargs['user'],
            marks__grain=self.kwargs['grain_id']
        ).order_by(
            '-active',
            'sequence_number'
        )
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(marks=FissionTrackNumbering.objects.filter(
            worker__username=self.kwargs['user'],
            grain=self.kwargs['grain_id']
        ))
        return ctx

class TutorialDeleteView(StaffRequiredMixin, DeleteView):
    model = TutorialPage
    template_name = "ftc/tutorial_update.html"
    def get_success_url(self):
        return reverse('tutorial_pages_of', kwargs={
            'grain_id': self.object.marks.grain.pk,
            'user': self.object.marks.grain.sample.in_project.creator
        })
