from django.contrib.auth.models import User
from django.db.models import F
from django.db.models.aggregates import Max
from django.shortcuts import get_object_or_404
from rest_framework import exceptions
import json
from rest_framework import generics, serializers, status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, permission_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ftc.get_image_size import get_image_size_from_handle
from ftc.load_rois import get_rois
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
        fields = [
            'id', 'sample', 'index', 'image_width', 'image_height',
            'scale_x', 'scale_y', 'stage_x', 'stage_y', 'shift_x', 'shift_y'
        ]

    index = serializers.IntegerField(required=False, read_only=False)
    sample = serializers.PrimaryKeyRelatedField(required=False, read_only=True)
    image_width = serializers.IntegerField(required=False, read_only=False)
    image_height = serializers.IntegerField(required=False, read_only=False)

    def do_create(self, request, sample_id):
        sample = Sample.objects.get(id=sample_id)
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
        grain = self.save(
            index = index,
            sample = sample,
            image_width=rois['image_width'],
            image_height=rois['image_height'],
            scale_x=rois.get('scale_x'),
            scale_y=rois.get('scale_y'),
            stage_x=rois.get('stage_x'),
            stage_y=rois.get('stage_y'),
            shift_x=region_first['shift'][0] if region_first else 0,
            shift_y=region_first['shift'][1] if region_first else 0,
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

    def perform_update(self, serializer):
        serializer.do_update(self.request)

@api_view()
@permission_classes([IsAuthenticated])
def download_rois(request, pk):
    grain = Grain.objects.get(id=pk)
    return Response(get_rois(grain))

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
        info = parse_image_name(filename)
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
            info = parse_image_name(filename)
            kwargs.update(info)
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
