import base64
from django.contrib.auth.models import User
from django.db.models.aggregates import Max
from django.shortcuts import get_object_or_404
from rest_framework import exceptions
import json
from rest_framework import generics, serializers, status
from rest_framework.authentication import TokenAuthentication
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ftc.get_image_size import get_image_size_from_handle
from ftc.models import Project, Sample, Grain, Image, FissionTrackNumbering
from ftc.parse_image_name import parse_image_name
from ftc.save_rois_regions import save_rois_regions


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


class SampleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sample
        fields = ['id', 'sample_name', 'in_project', 'sample_property',
            'total_grains', 'priority', 'min_contributor_num', 'completed']

    total_grains = serializers.IntegerField(required=False, read_only=True)
    completed = serializers.BooleanField(required=False, read_only=True)


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
        serializer.save(total_grains=0, completed=False)


class SampleInfoView(RetrieveUpdateDeleteView):
    model = Sample
    serializer_class = SampleSerializer


class GrainSerializer(serializers.ModelSerializer):
    class Meta:
        model = Grain
        fields = ['id', 'sample', 'index', 'image_width', 'image_height']

    index = serializers.IntegerField(required=False, read_only=False)
    sample = serializers.PrimaryKeyRelatedField(required=False, read_only=True)
    image_width = serializers.IntegerField(required=False, read_only=False)
    image_height = serializers.IntegerField(required=False, read_only=False)

    def do_create(self, request, sample_id):
        if (not request.user.is_superuser and
            self.validated_data['sample'].get_owner() != request.user):
            raise exceptions.PermissionDenied
        rois_b64 = self.initial_data['rois'].read()
        rois_json = base64.b64decode(rois_b64)
        rois = json.loads(rois_json)
        sample = Sample.objects.get(id=sample_id)
        index = self.validated_data.get('index')
        if index == None:
            max_index = sample.grain_set.aggregate(Max('index'))['index__max'] or 0
            index = max_index + 1
        grain = self.save(
            index = index,
            sample = sample,
            image_width=rois['image_width'],
            image_height=rois['image_height']
        )
        save_rois_regions(rois, grain)


class SampleGrainListView(ListCreateView):
    serializer_class = GrainSerializer
    model = Grain

    def get_queryset(self):
        qs = super().get_queryset()
        qs = qs.filter(sample=self.kwargs['sample'])
        return qs.order_by('id')

    def perform_create(self, serializer):
        serializer.do_create(self.request, self.kwargs['sample'])


class GrainListView(ListCreateView):
    serializer_class = GrainSerializer
    model = Grain

    def perform_create(self, serializer):
        serializer.do_create(self.request, self.initial_data['sample'])


class GrainInfoView(RetrieveUpdateDeleteView):
    model = Grain
    serializer_class = GrainSerializer


class ImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Image
        fields = ['id', 'grain', 'format', 'ft_type', 'index']
        extra_kwargs = {
            'name': { 'write_only': True }
        }

    format = serializers.CharField(required=False, read_only=False)
    index = serializers.IntegerField(required=False, read_only=False)
    ft_type = serializers.CharField(required=False, read_only=False)
    grain = serializers.PrimaryKeyRelatedField(required=False, read_only=True)


class GrainImageListView(ListCreateView):
    serializer_class = ImageSerializer
    model = Image

    def get_queryset(self):
        qs = super().get_queryset()
        if 'grain' in self.kwargs and self.kwargs['grain'].isnumeric():
            qs = qs.filter(grain=self.kwargs['grain'])
        return qs.order_by('id')

    def perform_create(self, serializer):
        if (not self.request.user.is_superuser and
            serializer.validated_data['grain'].get_owner() != self.request.user):
            raise exceptions.PermissionDenied
        filename = serializer.initial_data['data'].name
        info = parse_image_name(filename)
        data_b64 = serializer.initial_data['data'].read()
        data = base64.b64decode(data_b64)
        grain = Grain.objects.get(pk=self.kwargs['grain'])
        serializer.save(
            index=info['index'],
            grain=grain, 
            format=info['format'],
            ft_type=info['ft_type'],
            data=data
        )

class ImageInfoView(RetrieveUpdateDeleteView):
    model = Image
    serializer_class = ImageSerializer

    def perform_update(self, serializer):
        kwargs={}
        if 'data' in serializer.initial_data:
            filename = serializer.initial_data['data'].name
            info = parse_image_name(filename)
            data_b64 = serializer.initial_data['data'].read()
            kwargs.update(info)
            kwargs['data'] = base64.b64decode(data_b64)
        if 'grain' in self.kwargs and self.kwargs['grain'].isnumeric():
            kwargs['grain'] = Grain.objects.get(pk=self.kwargs['grain'])
        serializer.save(**kwargs)


class FissionTrackNumberingSerializer(serializers.ModelSerializer):
    class Meta:
        model = FissionTrackNumbering
        fields = ['id', 'in_sample', 'grain', 'ft_type',
            'worker', 'result', 'create_date', 'latlngs']


class FissionTrackNumberingView(generics.ListAPIView):
    serializer_class = FissionTrackNumberingSerializer
    model = FissionTrackNumbering

    def get_queryset(self):
        params = self.request.query_params
        qs = self.model.objects.all()
        if 'all' not in params:
            qs = qs.filter(result__gte=0)
        if 'sample' in params:
            qs = qs.filter(in_sample=params['in_sample'])
        if 'grain' in params:
            qs = qs.filter(grain=params['grain'])
        return qs.order_by('in_sample', 'grain')
