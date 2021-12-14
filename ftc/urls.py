from django.conf.urls import include
from django.urls import path
from rest_framework_simplejwt import views as jwt_views

from ftc.views import (home, signmeup, report, getTableData,
    get_grain_images, updateTFNResult, counting, saveWorkingGrain,
    get_image, projects, ProjectCreateView,
    ProjectDetailView, ProjectUpdateView,
    SampleDetailView, SampleUpdateView, SampleCreateView,
    GrainDetailView, GrainCreateView, grain_update,
    tutorial)
from ftc.apiviews import (ProjectListView, ProjectInfoView,
    SampleListView, SampleInfoView, ImageInfoView,
    SampleGrainListView, GrainInfoView, GrainImageListView,
    ImageListView, GrainListView, FissionTrackNumberingView)

urlpatterns = [
    path('', home, name='home'),
    path('signup', signmeup, name='signmeup'),
    path('report/', report, name='report'),
    path('project/<pk>/', ProjectDetailView.as_view(), name='project'),
    path('project/<pk>/update', ProjectUpdateView.as_view(), name='project_update'),
    path('project/<pk>/create_sample', SampleCreateView.as_view(), name='sample_create'),
    path('sample/<pk>/', SampleDetailView.as_view(), name='sample'),
    path('sample/<pk>/update', SampleUpdateView.as_view(), name='sample_update'),
    path('sample/<pk>/create_grain', GrainCreateView.as_view(), name='grain_create'),
    path('grain/<pk>/', GrainDetailView.as_view(), name='grain'),
    path('grain/<pk>/update', grain_update, name='grain_update'),
    path('projects/', projects, name='projects'),
    path('create_project/', ProjectCreateView.as_view(), name='project_create'),
    path('getTableData/', getTableData, name='getTableData'),
    path('get_grain_images/', get_grain_images, name='get_grain_images'),
    path('updateTFNResult/', updateTFNResult, name='updateTFNResult'),
    path('counting/guest/', counting, name='guest_counting', kwargs={ 'uname': 'guest' }),
    path('counting/', counting, name='counting'),
    path('saveWorkingGrain/', saveWorkingGrain, name='saveWorkingGrain'),
    path('image/<pk>/', get_image, name="get_image"),
    path('tutorial', tutorial, name='tutorial'),

    path('api/get-token', jwt_views.TokenObtainPairView.as_view(), name='get_jwt_token'),
    path('api/refresh-token', jwt_views.TokenRefreshView.as_view(), name='refresh_jwt_token'),
    path('api/project/', ProjectListView.as_view(), name='api_project_list'),
    path('api/project/<pk>/', ProjectInfoView.as_view(), name='api_project_info'),
    path('api/sample/', SampleListView.as_view(), name='api_sample_list'),
    path('api/sample/<pk>/', SampleInfoView.as_view(), name='api_sample_info'),
    path('api/sample/<sample>/grain/', SampleGrainListView.as_view(), name='api_sample_grain_list'),
    path('api/grain/', GrainListView.as_view(), name='api_grain_list'),
    path('api/grain/<pk>/', GrainInfoView.as_view(), name='api_grain_info'),
    path('api/grain/<grain>/image/', GrainImageListView.as_view(), name='api_grain_image_list'),
    path('api/image/', ImageListView.as_view(), name='api_image_list'),
    path('api/image/<pk>/', ImageInfoView.as_view(), name='api_image_info'),
    path('api/count/', FissionTrackNumberingView.as_view(), name='api_ftn_list'),
]
