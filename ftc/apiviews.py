from django.contrib.auth.models import User
from django.core.exceptions import (
    ObjectDoesNotExist, MultipleObjectsReturned
)
from django.db.models.aggregates import Max
from django.forms import ValidationError
from django.shortcuts import get_object_or_404
import json
import logging
import numbers
from rest_framework import exceptions
from rest_framework import generics, serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import exception_handler

from ftc.load_rois import get_rois, get_rois_user, get_roiss
from ftc.models import (
    Project, Sample, Grain, Image, FissionTrackNumbering,
    Transform2D, GrainPoint, GrainPointCategory, ContainedTrack,
    Region, Vertex
)
from ftc.parse_image_name import parse_upload_name
from ftc.save_rois_regions import save_rois_regions
from ftc import views


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
        if type(data) is int or data.isnumeric():
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


def get_sample_queryset(id_or_name, request):
        samples = models_owned(Sample, request)
        if id_or_name.isnumeric():
            return samples.filter(pk=id_or_name)
        return samples.filter(sample_name__iexact=id_or_name)


class SampleInfoView(RetrieveUpdateDeleteView):
    model = Sample
    serializer_class = SampleSerializer

    def get_object(self):
        assert('pk' in self.kwargs)
        qs = get_sample_queryset(self.kwargs['pk'], self.request)
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
        qs = get_sample_queryset(sample_id, request)
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
def get_image(request, pk):
    return views.get_image(request, pk)


@api_view()
@permission_classes([IsAuthenticated])
def get_grain_rois(request, pk):
    grain = Grain.objects.get(id=pk)
    return Response(get_rois(grain))


@api_view()
@permission_classes([IsAuthenticated])
def get_grain_rois_user(request, pk, user):
    grain = Grain.objects.get(id=pk)
    if user.isnumeric():
        user_obj = User.objects.get(pk=int(user))
    else:
        user_obj = User.objects.get(username=user)
    return Response(get_rois_user(grain, user_obj))


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


class FissionTrackNumberingSerializerBase(serializers.ModelSerializer):
    class UserRelatedField(serializers.RelatedField):
        def get_queryset(self):
            return super().get_queryset()
        def to_representation(self, obj):
            out = {}
            for a in ['id', 'username', 'email']:
                out[a] = getattr(obj, a)
            return out
        def to_internal_value(self, data):
            return User.objects.get(username=data)

    class GrainField(serializers.RelatedField):
        default_error_messages = {
            'grain_format': 'grain format is <sample-name-or-id>/<index> or <id>; {data} does not match'
        }
        def get_queryset(self):
            return super().get_queryset()
        def to_internal_value(self, data):
            parts = data.split('/')
            gs = Grain.objects
            if len(parts) == 1 and data.isnumeric():
                return gs.get(pk=data)
            if len(parts) != 2 or not parts[1].isnumeric():
                self.fail('grain_format', data=data)
            [sample, index] = parts
            index = int(index)
            if sample.isnumeric():
                gs = gs.filter(sample__pk=sample)
            else:
                gs = gs.filter(sample__sample_name=sample)
            return gs.get(index=index)
        def to_representation(self, value):
            return value.pk

    class ResultSizeDefault:
        """
        A default value that gets the number of points specified
        """
        requires_context = True
        def __call__(self, serializer_field):
            grainpoints = serializer_field.parent.initial_data.getlist('grainpoints')
            return len(grainpoints)

    worker = UserRelatedField()
    result = serializers.IntegerField(default=ResultSizeDefault())
    grain = GrainField()
    contained_tracks = serializers.SerializerMethodField()
    regions = serializers.SerializerMethodField()

    def get_contained_tracks(self, obj):
        return [
            { k: v for (k, v) in gp.items() if k not in ['id', 'result_id'] }
            for gp in obj.containedtrack_set.values()
        ]

    def get_regions(self, obj):
        region_qs = obj.region_set.all()
        if not region_qs.exists():
            return None
        return [
            [[vertex.x, vertex.y]
            for vertex in region.vertex_set.all()]
            for region in region_qs
        ]

    def run_validation(self, data=...):
        ret = super().run_validation(data)
        gps_json = data.get("grainpoints", "[]")
        gps = json.loads(gps_json)
        ret["grainpoints"] = gps
        ret["result"] = data.get("result", len(gps))
        ret["contained_tracks"] = self.validate_contained_tracks(data)
        ret["regions"] = self.validate_regions(data.get("regions", None))
        return ret

    def validate_regions(self, regions):
        if regions is None:
            return None
        if type(regions) is str:
            regions = json.loads(regions)
        elif type(regions) is list:
            regions = [json.loads(r) for r in regions]
        if type(regions) is not list:
            raise ValidationError("regions should be a list or null")
        regions_out = []
        for reg in regions:
            if type(reg) is dict and 'vertices' in reg:
                reg = reg['vertices']
            if type(reg) is not list or len(reg) == 0:
                raise ValidationError('Each region should be an object with a "vertices" key or a nonempty list')
            for v in reg:
                if not(type(v) is list and len(v) == 2 and isinstance(v[0], numbers.Number) and isinstance(v[1], numbers.Number)):
                    raise ValidationError("Each vertex should be a list of two numbers")
            regions_out.append(reg)
        return regions_out

    def validate_contained_tracks(self, data):
        ct_keys = ["x1_pixels", "y1_pixels", "z1_level", "x2_pixels", "y2_pixels", "z2_level"]
        ct_key_set = set(ct_keys)

        cts = data.get("contained_tracks", "[]")
        cts_obj = json.loads(cts)
        result = []
        if type(cts_obj) is not list:
            # empty dicts are OK to help Pieter's script work
            if not cts_obj:
                logging.getLogger(__name__).warning("Empty thing")
                return result
            raise ValidationError("contained_tracks needs to be an array")
        for cti, ct_obj in enumerate(cts_obj):
            if type(ct_obj) is list:
                if len(ct_obj) != 6:
                    raise ValidationError(
                        "contained_tracks element {0} has {1} elements; should have 6".format(cti, len(ct_obj))
                    )
                result.append({
                    k: ct_obj[i] for i, k in enumerate(ct_keys)
                })
            elif type(ct_obj) is dict:
                actual_keys = set(ct_obj.keys())
                missing = ct_key_set - actual_keys
                if missing:
                    raise ValidationError(
                        "contained_tracks element {0} lacks keys: {1}".format(cti, missing)
                    )
                unexpected = actual_keys - ct_key_set
                if unexpected:
                    raise ValidationError(
                        "contained_tracks element {0} has unexpected keys: {1}".format(cti, unexpected)
                    )
                result.append(ct_obj)
            else:
                raise ValidationError(
                    "contained_tracks element {0} should be dict or list, but is {1}".format(cti, type(ct_obj))
                )
        return result

    def create(self, validated_data):
        points = validated_data.pop('grainpoints')
        contained_tracks = validated_data.pop('contained_tracks')
        regions = validated_data.pop('regions') or []
        worker = validated_data['worker']
        delete_params = {
            "grain": validated_data['grain'],
            "worker": worker
        }
        if worker.username == "guest":
            delete_params["analyst"] = validated_data.get("analyst", None)
        ftn = FissionTrackNumbering.objects.filter(
            **delete_params
        ).delete()
        ftn = FissionTrackNumbering.objects.create(**validated_data)
        for point in points:
            point["category"] = GrainPointCategory.objects.get(
                name=point.get("category", "track")
            )
            GrainPoint.objects.create(result=ftn, **point)
        for ct in contained_tracks:
            ContainedTrack.objects.create(result=ftn, **ct)
        for reg in regions:
            region = Region.objects.create(grain=ftn.grain, result=ftn)
            for v in reg:
                Vertex.objects.create(region=region, x=v[0], y=v[1])
        return ftn


class FissionTrackNumberingSerializerLatLngs(FissionTrackNumberingSerializerBase):
    """
    FissionTrackNumberingSerializer that reports result points as LatLngs
    """
    class Meta:
        model = FissionTrackNumbering
        fields = ['id', 'grain', 'ft_type', 'worker', 'analyst', 'regions',
            'result', 'create_date', 'latlngs', 'contained_tracks',]

    latlngs = serializers.CharField(read_only=True)


class FissionTrackNumberingSerializerGps(FissionTrackNumberingSerializerBase):
    """
    FissionTrackNumberingSerializer that reports result points as GrainPoints
    """
    class Meta:
        model = FissionTrackNumbering
        fields = ['id', 'grain', 'ft_type', 'worker', 'analyst', 'regions',
            'result', 'create_date', 'contained_tracks', 'grainpoints']

    grainpoints = serializers.SerializerMethodField()

    def get_grainpoints(self, obj):
        return [
            { k: v for (k, v) in gp.items() if k not in ['id', 'result_id'] }
            for gp in obj.grainpoint_set.values()
        ]

class FissionTrackNumberingView(generics.ListCreateAPIView):
    serializer_class = FissionTrackNumberingSerializerGps
    model = FissionTrackNumbering

    def get_queryset(self):
        params = self.request.query_params
        qs = self.model.objects.all()
        if 'all' not in params:
            qs = qs.filter(result__gte=0)
        if 'sample' in params:
            sample = params['sample']
            if sample.isnumeric():
                qs = qs.filter(grain__sample=sample)
            else:
                qs = qs.filter(grain__sample__sample_name=sample)
        if 'grain' in params:
            qs = qs.filter(grain__index=params['grain'])
        if 'user' in params:
            qs = qs.filter(worker__username=params['user'])
        return qs.order_by('grain__sample', 'grain__index').select_related('worker')


class FissionTrackNumberingViewLatLngs(FissionTrackNumberingView):
    serializer_class = FissionTrackNumberingSerializerLatLngs
