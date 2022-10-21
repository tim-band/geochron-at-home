from django.conf.urls import include
from django.urls import path
from rest_framework_simplejwt import views as jwt_views

from ftc.views import (home, signmeup, report, getTableData,
    count_grain, updateTFNResult, counting, saveWorkingGrain,
    get_image, projects, ProjectCreateView,
    ProjectDetailView, ProjectUpdateView,
    SampleDetailView, SampleUpdateView, SampleCreateView,
    GrainDetailView, MicaDetailView, GrainCreateView,
    grain_update_roi, grain_update_shift,
    GrainDetailUpdateView, GrainImagesView,
    ImageDeleteView, tutorial, saveTutorialResult, CountMyGrainView)
from ftc.apiviews import (ProjectListView, ProjectInfoView,
    SampleListView, SampleInfoView, ImageInfoView,
    SampleGrainListView, GrainInfoView, GrainImageListView,
    ImageListView, GrainListView, FissionTrackNumberingView,
    download_rois)

urlpatterns = [
    path('', home, name='home'),
    path('signup', signmeup, name='signmeup'),
    path('report/', report, name='report'),
    path('project/<pk>/', ProjectDetailView.as_view(), name='project'),
    path('project/<pk>/update', ProjectUpdateView.as_view(), name='project_update'),
    path('project/<pk>/create_sample', SampleCreateView.as_view(), name='sample_create'),
    path('sample/<pk>/', SampleDetailView.as_view(), name='sample'),
    path('sample/<pk>/update', SampleUpdateView.as_view(), name='sample_update'),
    # Small form that lets you upload grain images, metadata or rois.json to create a new grain
    path('sample/<pk>/create_grain', GrainCreateView.as_view(), name='grain_create'),
    # Z-stack microscope view of grain (with option to adjust ROI)
    path('grain/<pk>/', GrainDetailView.as_view(), name='grain'),
    # Z-stack microscope view of mica (with option to adjust shift)
    path('grain/<pk>/mica', MicaDetailView.as_view(), name='mica'),
    # Form for updating grain
    path('grain/<pk>/update_meta', GrainDetailUpdateView.as_view(), name='grain_update_meta'),
    # Post endpoint for updating the ROI
    path('grain/<pk>/update_roi', grain_update_roi, name='grain_update_roi'),
    # Post endpoint for updating the Mica
    path('grain/<pk>/update_shift', grain_update_shift, name='grain_update_shift'),
    # Table of metadata + table of images + upload form to upload metadata, grain images or rois.json
    path('grain/<pk>/images', GrainImagesView.as_view(), name='grain_images'),
    path('projects/', projects, name='projects'),
    path('create_project/', ProjectCreateView.as_view(), name='project_create'),
    path('getTableData/', getTableData, name='getTableData'),
    path('updateTFNResult/', updateTFNResult, name='updateTFNResult'),
    path('counting/guest/', counting, name='guest_counting', kwargs={ 'uname': 'guest' }),
    path('counting/', counting, name='counting'),
    path('count/<pk>/', count_grain, name='count'),
    path('count_my/<pk>/', CountMyGrainView.as_view(), name='count_my'),
    path('saveWorkingGrain/', saveWorkingGrain, name='saveWorkingGrain'),
    path('image/<pk>/', get_image, name="get_image"),
    path('image/<pk>/delete', ImageDeleteView.as_view(), name='image_delete'),
    path('tutorial/', tutorial, name='tutorial'),
    path('tutorial_result/', saveTutorialResult, name='tutorialResult'),

    path('api/get-token', jwt_views.TokenObtainPairView.as_view(), name='get_jwt_token'),
    path('api/refresh-token', jwt_views.TokenRefreshView.as_view(), name='refresh_jwt_token'),
    path('api/project/', ProjectListView.as_view(), name='api_project_list'),
    path('api/project/<pk>/', ProjectInfoView.as_view(), name='api_project_info'),
    path('api/sample/', SampleListView.as_view(), name='api_sample_list'),
    path('api/sample/<pk>/', SampleInfoView.as_view(), name='api_sample_info'),
    path('api/sample/<sample>/grain/', SampleGrainListView.as_view(), name='api_sample_grain_list'),
    path('api/grain/', GrainListView.as_view(), name='api_grain_list'),
    path('api/grain/<pk>/', GrainInfoView.as_view(), name='api_grain_info'),
    path('api/grain/<pk>/rois/', download_rois, name='api_grain_rois'),
    path('api/grain/<grain>/image/', GrainImageListView.as_view(), name='api_grain_image_list'),
    path('api/image/', ImageListView.as_view(), name='api_image_list'),
    path('api/image/<pk>/', ImageInfoView.as_view(), name='api_image_info'),
    path('api/count/', FissionTrackNumberingView.as_view(), name='api_ftn_list'),
]
