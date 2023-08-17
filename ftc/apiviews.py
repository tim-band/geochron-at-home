from django.contrib.auth.models import User
from django.core.exceptions import (
    ObjectDoesNotExist, MultipleObjectsReturned
)
from django.db.models.aggregates import Max
from django.shortcuts import get_object_or_404
import json
import logging
from rest_framework import exceptions
from rest_framework import generics, serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import exception_handler

from ftc.load_rois import get_rois, get_roiss
from ftc.models import Project, Sample, Grain, Image, FissionTrackNumbering, Transform2D
from ftc.parse_image_name import parse_upload_name
from ftc.save_rois_regions import save_rois_regions


def explicit_exception_handler(exc, context):
    if isinstance(exc, exceptions.ValidationError):
        logging.info(exc)
        return Response(
            { 'failed_validations': exc.detail },
            status=400
        )
    return exception_handler(exc, context)


def models_owned(model_class, request):
    qs = model_class.objects.all()
    user = request.user
    if user:
        if user.is_superuser:
            return qs
        return model_class.filter_owned_by(qs, user)
    return qs.none()


class RetrieveUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return models_owned(self.model, self.request)


class ListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return models_owned(self.model, self.request)


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ['id', 'project_name', 'creator', 'create_date',
            'project_description', 'priority', 'closed', 'sample_set']

    creator = serializers.SlugRelatedField(
        required=False,
        read_only=True,
        slug_field='username',
    )


class ProjectListView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    model = Project
    serializer_class = ProjectSerializer

    def get_queryset(self):
        params = self.request.query_params
        qs = Project.objects.all()
        if 'project' in params:
            project = params['project']
            if project.isnumeric():
                qs = qs.filter(in_project=project)
            else:
                qs = qs.filter(in_project__project_name__iexact=project)
        return qs.order_by('id')

    def perform_create(self, serializer):
        user = self.request.user
        if not user.is_staff:
            raise exceptions.PermissionDenied
        if 'user' in self.request.data:
            user = User.objects.get(username=self.request.data['user'])
        serializer.save(creator=user)


class ProjectInfoView(RetrieveUpdateDeleteView):
    model = Project
    serializer_class = ProjectSerializer


class ProjectField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        return Project.objects.all()

    def to_internal_value(self, data):
        if data.isnumeric():
            return super().to_internal_value(data)
        try:
            return self.get_queryset().get(project_name__iexact=data)
        except ObjectDoesNotExist:
            self.fail('does_not_exist', name=data)
        except MultipleObjectsReturned:
            self.fail('multiple_projects_match', name=data)
        except (TypeError, ValueError):
            self.fail('incorrect_type', data_type=type(data).__name__)


class SampleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sample
        fields = ['id', 'sample_name', 'in_project', 'sample_property',
            'priority', 'min_contributor_num', 'completed']

    completed = serializers.BooleanField(required=False, read_only=True)
    in_project = ProjectField()


class SampleListView(ListCreateView):
    serializer_class = SampleSerializer
    model = Sample

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if 'in_project' in params:
            project = params['in_project']
            if project.isnumeric():
                qs = qs.filter(in_project=project)
            else:
                qs = qs.filter(in_project__project_name__iexact=project)
        return qs.order_by('id')

    def perform_create(self, serializer):
        if (not self.request.user.is_superuser and
            serializer.validated_data['in_project'].get_owner() != self.request.user):
            raise exceptions.PermissionDenied
        serializer.save(completed=False)


def get_sample_queryset(id_or_name):
        if id_or_name.isnumeric():
            return Sample.objects.filter(pk=id_or_name)
        return Sample.objects.filter(sample_name__iexact=id_or_name)


class SampleInfoView(RetrieveUpdateDeleteView):
    model = Sample
    serializer_class = SampleSerializer

    def get_object(self):
        assert('pk' in self.kwargs)
        qs = get_sample_queryset(self.kwargs['pk'])
        obj = get_object_or_404(qs)
        self.check_object_permissions(self.request, obj)
        return obj


class GrainSerializer(serializers.ModelSerializer):
    class Meta:
        model = Grain
        fields = [
            'id', 'sample', 'index', 'image_width', 'image_height',
            'scale_x', 'scale_y', 'stage_x', 'stage_y', 'shift_x', 'shift_y',
            'mica_stage_x', 'mica_stage_y'
        ]

    index = serializers.IntegerField(required=False, read_only=False)
    sample = serializers.PrimaryKeyRelatedField(required=False, read_only=True)
    image_width = serializers.IntegerField(required=False, read_only=False)
    image_height = serializers.IntegerField(required=False, read_only=False)

    def do_create(self, request, sample_id):
        qs = get_sample_queryset(sample_id)
        sample = get_object_or_404(qs)
        if (not request.user.is_superuser and
            sample.get_owner() != request.user):
            raise exceptions.PermissionDenied
        data = self.initial_data['rois'].read()
        rois_json = data.decode('utf-8')
        rois = json.loads(rois_json)
        index = self.validated_data.get('index')
        if index == None:
            max_index = sample.grain_set.aggregate(Max('index'))['index__max'] or 0
            index = max_index + 1
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
        grain = self.save(
            index = index,
            sample = sample,
            image_width=rois['image_width'],
            image_height=rois['image_height'],
            scale_x=rois.get('scale_x'),
            scale_y=rois.get('scale_y'),
            stage_x=rois.get('stage_x'),
            stage_y=rois.get('stage_y'),
            mica_stage_x=rois.get('mica_stage_x'),
            mica_stage_y=rois.get('mica_stage_y'),
            shift_x=region_first['shift'][0] if region_first else 0,
            shift_y=region_first['shift'][1] if region_first else 0,
            mica_transform_matrix=transform
        )
        save_rois_regions(rois, grain)

    def do_update(self, request):
        kwargs = {}
        # Check the grain is not going to be passed to another user
        sample_id = self.initial_data.get('sample')
        if sample_id != None:
            sample = Sample.objects.get(pk=sample_id)
            kwargs['sample'] = sample
            if not request.user.is_superuser and sample.get_owner() != request.user:
                raise exceptions.PermissionDenied
        self.save(**kwargs)


class SampleGrainListView(ListCreateView):
    serializer_class = GrainSerializer
    model = Grain

    def get_queryset(self):
        qs = Grain.objects.all()
        sample = self.kwargs.get('sample')
        if sample.isnumeric():
            qs = qs.filter(sample=sample)
        else:
            qs = qs.filter(sample__sample_name=sample)
        return qs.order_by('id')

    def perform_create(self, serializer):
        serializer.do_create(self.request, self.kwargs['sample'])


class SampleGrainInfoView(RetrieveUpdateDeleteView):
    model = Grain
    serializer_class = GrainSerializer

    def get_object(self):
        qs = Grain.objects.filter(
            sample__sample_name__iexact=self.kwargs['sample'],
            index=self.kwargs['index']
        )
        obj = get_object_or_404(qs)
        self.check_object_permissions(self.request, obj)
        return obj


class GrainListView(ListCreateView):
    serializer_class = GrainSerializer
    model = Grain

    def perform_create(self, serializer):
        serializer.do_create(self.request, self.initial_data['sample'])


class GrainInfoView(RetrieveUpdateDeleteView):
    model = Grain
    serializer_class = GrainSerializer

    def perform_update(self, serializer):
        serializer.do_update(self.request)


@api_view()
@permission_classes([IsAuthenticated])
def get_grain_rois(request, pk):
    grain = Grain.objects.get(id=pk)
    return Response(get_rois(grain))

def request_roiss(request):
    gq = Grain.objects.all()
    if 'grains[]' in request.GET:
        gq = gq.filter(
            id__in=request.GET.getlist('grains[]')
        )
    if 'samples[]' in request.GET:
        gq = gq.filter(
            sample__in=request.GET.getlist('samples[]')
        )
    if 'projects[]' in request.GET:
        gq = gq.filter(
            sample__in_project__in=request.GET.getlist('projects[]')
        )
    return get_roiss(gq.prefetch_related(
        'sample__in_project',
        'region_set__vertex_set',
        'mica_transform_matrix'
    ))

@api_view()
@permission_classes([IsAuthenticated])
def get_many_roiss(request):
    return Response(request_roiss(request))

class ImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Image
        fields = [
            'id', 'grain', 'format', 'ft_type', 'index', 'light_path', 'focus'
        ]
        extra_kwargs = {
            'name': { 'write_only': True }
        }

    format = serializers.CharField(required=False, read_only=False)
    index = serializers.IntegerField(required=False, read_only=False)
    ft_type = serializers.CharField(required=False, read_only=False)
    grain = serializers.PrimaryKeyRelatedField(required=False, read_only=True)

    def do_create(self, request, grain_id):
        grain = Grain.objects.get(pk=grain_id)
        if (not request.user.is_superuser and
            grain.get_owner() != request.user):
            raise exceptions.PermissionDenied
        filename = self.initial_data['data'].name
        info = parse_upload_name(filename)
        data = self.initial_data['data'].read()
        self.save(
            index=info['index'],
            grain=grain, 
            format=info['format'],
            ft_type=info['ft_type'],
            data=data
        )


class GrainImageListView(ListCreateView):
    serializer_class = ImageSerializer
    model = Image

    def get_queryset(self):
        qs = super().get_queryset()
        if 'grain' in self.kwargs and self.kwargs['grain'].isnumeric():
            qs = qs.filter(grain=self.kwargs['grain'])
        return qs.order_by('id')

    def perform_create(self, serializer):
        serializer.do_create(self.request, self.kwargs['grain'])


class ImageListView(ListCreateView):
    serializer_class = ImageSerializer
    model = Image

    def perform_create(self, serializer):
        serializer.do_create(self.request, self.initial_data['grain'])


class ImageInfoView(RetrieveUpdateDeleteView):
    model = Image
    serializer_class = ImageSerializer

    def perform_update(self, serializer):
        kwargs={}
        if 'grain' in serializer.initial_data:
            grain = Grain.objects.get(pk=serializer.initial_data['grain'])
            kwargs['grain'] = grain
            if (not self.request.user.is_superuser
                    and grain.get_owner() != self.request.user):
                raise exceptions.PermissionDenied
        if 'data' in serializer.initial_data:
            filename = serializer.initial_data['data'].name
            info = parse_upload_name(filename)
            kwargs['ft_type'] = info['ft_type']
            kwargs['index'] = info['index']
            kwargs['format'] = info['format']
            kwargs['data'] = serializer.initial_data['data'].read().decode('utf-8')
        serializer.save(**kwargs)


class FissionTrackNumberingSerializer(serializers.ModelSerializer):
    class UserRelatedField(serializers.RelatedField):
        def to_representation(self, obj):
            out = {}
            for a in ['id', 'username', 'email']:
                out[a] = getattr(obj, a)
            return out

    worker = UserRelatedField(read_only=True)

    class Meta:
        model = FissionTrackNumbering
        fields = ['id', 'grain', 'ft_type', 'worker',
            'result', 'create_date', 'latlngs']


class FissionTrackNumberingView(generics.ListAPIView):
    serializer_class = FissionTrackNumberingSerializer
    model = FissionTrackNumbering

    def get_queryset(self):
        params = self.request.query_params
        qs = self.model.objects.all()
        if 'all' not in params:
            qs = qs.filter(result__gte=0)
        if 'sample' in params:
            qs = qs.filter(grain__sample=params['in_sample'])
        if 'grain' in params:
            qs = qs.filter(grain__index=params['grain'])
        return qs.order_by('grain__sample', 'grain__index').select_related('worker')
