from django.conf.urls import include
from django.urls import path

from ftc.views import home, signmeup, report, getTableData, \
    get_grain_images, updateTFNResult, counting, saveWorkingGrain, \
    get_image, projects, \
    ProjectDetailView, ProjectUpdateView, \
    SampleDetailView, SampleUpdateView, SampleCreateView, \
    GrainDetailView, GrainCreateView, grain_update

urlpatterns = [
    # Ex: /ftc/
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
    path('getTableData/', getTableData, name='getTableData'),
    path('get_grain_images/', get_grain_images, name='get_grain_images'),
    path('updateTFNResult/', updateTFNResult, name='updateTFNResult'),
    path('counting/guest/', counting, name='guest_counting', kwargs={ 'uname': 'guest' }),
    path('counting/', counting, name='counting'),
    path('saveWorkingGrain/', saveWorkingGrain, name='saveWorkingGrain'),
    path('image/<pk>/', get_image, name="get_image"),
]
