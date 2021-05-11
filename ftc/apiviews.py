from django.shortcuts import get_object_or_404
from rest_framework import generics, serializers, status
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ftc.models import Project, Sample

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
