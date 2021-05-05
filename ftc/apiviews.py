from django.shortcuts import get_object_or_404
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ftc.models import Project, Sample

class ProjectsView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, *args, **kwargs):
        projects = Project.objects.values()
        return Response(projects)

class ProjectView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, *args, **kwargs):
        project = get_object_or_404(Project, pk=kwargs['pk'])
        samples = Sample.objects.values_list('id', flat=True)
        return Response({
            'id': project.id,
            'project_name': project.project_name,
            'creator': project.creator.username,
            'create_date': project.create_date,
            'project_description': project.project_description,
            'priority': project.priority,
            'closed': project.closed,
            'sample_set': samples,
        })
