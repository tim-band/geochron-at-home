from django.shortcuts import get_object_or_404
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

class AdminApiView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]

class ProjectsView(AdminApiView):
    def get(self, request):
        projects = Projects.objects.values_list('id', flat=True)
        return Response(projects)

class ProjectView(AdminApiView):
    def get(self, request):
        project = get_object_or_404(Project, pk=self.kwargs['pk'])
        samples = Sample.objects.values_list('id', flat=True)
        return Response({
            'id': project.id,
            'project_name': project.project_name,
            'creator': project.creator,
            'create_date': project.create_date,
            'project_description': project.project_description,
            'priority': project.priority,
            'closed': project.closed,
            'sample_set': samples,
        })
