from django.urls import path
from rest_framework_simplejwt import views as jwt_views

from ftc import apiviews
from ftc.views import (home, signmeup, report, getTableData,
    count_grain, updateFtnResult, counting, saveWorkingGrain,
    get_image, projects, ProjectCreateView,
    ProjectDetailView, ProjectUpdateView,
    SampleDetailView, SampleUpdateView, SampleCreateView,
    GrainDetailView, MicaDetailView, GrainCreateView,
    grain_update_roi, grain_update_shift,
    GrainDetailUpdateView, GrainImagesView,
    GrainAnalysesView, grainAnalystResult,
    ImageDeleteView, tutorial, saveTutorialResult,
    CountMyGrainView, CountMyGrainMicaView, getJsonResults,
    download_rois, download_roiss,
    getCsvResults, GrainDeleteView, tutorialPage, tutorialEnd,
    TutorialCreateView, TutorialUpdateView, TutorialListView,
    TutorialDeleteView, publicSample)
from ftc.apiviews import (ProjectListView, ProjectInfoView,
    SampleListView, SampleInfoView, ImageInfoView,
    SampleGrainListView, GrainInfoView, GrainImageListView,
    ImageListView, GrainListView, FissionTrackNumberingView,
    FissionTrackNumberingViewLatLngs,
    get_grain_rois, get_many_roiss, SampleGrainInfoView,
    get_grain_rois_user)

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
    path('grain/<pk>/delete', GrainDeleteView.as_view(), name='grain_delete'),
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
    path('grain/<pk>/analyst/', GrainAnalysesView.as_view(), name='analyses_page'),
    path('grain/<grain>/analyst/<analyst>/', grainAnalystResult, name='grain_analyst_result'),
    path('projects/', projects, name='projects'),
    path('create_project/', ProjectCreateView.as_view(), name='project_create'),
    path('getTableData/', getTableData, name='getTableData'),
    path('getJsonResults/', getJsonResults, name='getJsonResults'),
    path('getCsvResults/', getCsvResults, name='getCsvResults'),
    path('updateFtnResult/', updateFtnResult, name='updateFtnResult'),
    path('counting/guest/', counting, name='guest_counting', kwargs={ 'uname': 'guest' }),
    path('counting/', counting, name='counting'),
    path('count/<pk>/', count_grain, name='count'),
    path('count_my/<pk>/', CountMyGrainView.as_view(), name='count_my'),
    path('count_my_mica/<pk>/', CountMyGrainMicaView.as_view(), name='count_my_mica'),
    path('saveWorkingGrain/', saveWorkingGrain, name='saveWorkingGrain'),
    path('image/<pk>/', get_image, name="get_image"),
    path('image/<pk>/delete', ImageDeleteView.as_view(), name='image_delete'),
    path('tutorial/', tutorial, name='tutorial'),
    path('tutorial_result/', saveTutorialResult, name='tutorial_result'),
    path('rois/<pk>/', download_rois, name='download_grain_rois'),
    path('rois/', download_roiss, name='download_roiss'),
    path('tutorialpage/<pk>/', tutorialPage, name='tutorial_page'),
    path('tutorialend/', tutorialEnd, name='tutorial_end'),
    path('tutorialpagesof/<grain_id>/<user>/', TutorialListView.as_view(), name='tutorial_pages_of'),
    path('tutorialpage/<pk>/update/', TutorialUpdateView.as_view(), name='tutorial_update'),
    path('tutorialpage/<pk>/delete/', TutorialDeleteView.as_view(), name='tutorial_delete'),
    path('tutorialpage_create/', TutorialCreateView.as_view(), name='tutorial_create'),
    path('public/<sample>/<grain>/', publicSample, name='public_sample'),

    path('api/get-token', jwt_views.TokenObtainPairView.as_view(), name='get_jwt_token'),
    path('api/refresh-token', jwt_views.TokenRefreshView.as_view(), name='refresh_jwt_token'),
    path('api/project/', ProjectListView.as_view(), name='api_project_list'),
    path('api/project/<pk>/', ProjectInfoView.as_view(), name='api_project_info'),
    path('api/sample/', SampleListView.as_view(), name='api_sample_list'),
    path('api/sample/<pk>/', SampleInfoView.as_view(), name='api_sample_info'),
    path('api/sample/<sample>/grain/', SampleGrainListView.as_view(), name='api_sample_grain_list'),
    path('api/sample/<sample>/grain/<index>/', SampleGrainInfoView.as_view(), name='api_sample_grain_list'),
    path('api/grain/', GrainListView.as_view(), name='api_grain_list'),
    path('api/grain/<pk>/', GrainInfoView.as_view(), name='api_grain_info'),
    path('api/grain/<pk>/rois/', get_grain_rois, name='api_grain_rois'),
    path('api/grain/<pk>/rois/<user>/', get_grain_rois_user, name='api_grain_rois_user'),
    path('api/rois/', get_many_roiss, name='api_roiss'),
    path('api/grain/<grain>/image/', GrainImageListView.as_view(), name='api_grain_image_list'),
    path('api/image/', ImageListView.as_view(), name='api_image_list'),
    path('api/image/<pk>/', ImageInfoView.as_view(), name='api_image_info'),
    path('api/image/<pk>/data/', apiviews.get_image, name='api_image_data'),
    path('api/count/', FissionTrackNumberingView.as_view(), name='api_ftn_list'),
    path('api/countll/', FissionTrackNumberingViewLatLngs.as_view(), name='api_ftn_list'),
]
