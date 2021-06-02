import base64
from django.db.models.aggregates import Max
from django.shortcuts import get_object_or_404
import json
from rest_framework import generics, serializers, status
from rest_framework.authentication import TokenAuthentication
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ftc.get_image_size import get_image_size_from_handle
from ftc.models import Project, Sample, Grain, Image, FissionTrackNumbering
from ftc.parse_image_name import parse_image_name
from ftc.save_rois_regions import save_rois_regions


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ['id', 'project_name', 'creator', 'create_date',
            'project_description', 'priority', 'closed', 'sample_set']

    creator = serializers.PrimaryKeyRelatedField(required=False, read_only=True)


class ProjectListView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)


class ProjectInfoView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer


class SampleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sample
        fields = ['id', 'sample_name', 'in_project', 'sample_property',
            'total_grains', 'priority', 'min_contributor_num', 'completed']

    total_grains = serializers.IntegerField(required=False, read_only=True)
    completed = serializers.BooleanField(required=False, read_only=True)


class SampleListView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = SampleSerializer
    model = Sample

    def get_queryset(self):
        params = self.request.query_params
        qs = self.model.objects.all()
        if 'project' in params:
            project = params['project']
            if project.isnumeric():
                qs = qs.filter(in_project=project)
            else:
                qs = qs.filter(in_project__project_name__iexact=project)
        return qs.order_by('id')

    def perform_create(self, serializer):
        serializer.save(total_grains=0, completed=False)


class SampleInfoView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    queryset = Sample.objects.all()
    serializer_class = SampleSerializer


class GrainSerializer(serializers.ModelSerializer):
    class Meta:
        model = Grain
        fields = ['id', 'sample', 'index', 'image_width', 'image_height']

    index = serializers.IntegerField(required=False, read_only=False)
    sample = serializers.PrimaryKeyRelatedField(required=False, read_only=True)
    image_width = serializers.IntegerField(required=False, read_only=False)
    image_height = serializers.IntegerField(required=False, read_only=False)


class SampleGrainListView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = GrainSerializer
    model = Grain

    def get_queryset(self):
        qs = self.model.objects.filter(sample=self.kwargs['sample'])
        return qs.order_by('id')

    def perform_create(self, serializer):
        rois_b64 = serializer.initial_data['rois'].read()
        rois_json = base64.b64decode(rois_b64)
        rois = json.loads(rois_json)
        sample = Sample.objects.get(pk=self.kwargs['sample'])
        max_index = sample.grain_set.aggregate(Max('index'))['index__max'] or 0
        grain = serializer.save(
            index = max_index+1,
            sample = sample,
            image_width=rois['image_width'],
            image_height=rois['image_height']
        )
        save_rois_regions(rois, grain)


class GrainInfoView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    queryset = Grain.objects.all()
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


class GrainImageListView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = ImageSerializer
    model = Image

    def get_queryset(self):
        qs = self.model.objects.all()
        if 'grain' in self.kwargs and self.kwargs['grain'].isnumeric():
            qs = qs.filter(grain=self.kwargs['grain'])
        return qs.order_by('id')

    def perform_create(self, serializer):
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

class ImageInfoView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    queryset = Image.objects.all()
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
    permission_classes = [IsAuthenticated, IsAdminUser]
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
