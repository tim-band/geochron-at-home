from django.shortcuts import get_object_or_404
from rest_framework import generics, serializers, status
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ftc.models import Project, Sample, FissionTrackNumbering

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
