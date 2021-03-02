from django.conf.urls import include, re_path
from django.urls import path

from ftc.views import home, signmeup, report, getTableData, \
    get_grain_images, updateTFNResult, counting, saveWorkingGrain, \
    get_image

urlpatterns = [
    # Ex: /ftc/
    re_path(r'^$', home, name='home'),
    re_path(r'signup', signmeup, name='signmeup'),
    re_path(r'^report/$', report, name='report'),
    re_path(r'^getTableData/$', getTableData, name='getTableData'),
    re_path(r'^get_grain_images/$', get_grain_images, name='get_grain_images'),
    re_path(r'^updateTFNResult/$', updateTFNResult, name='updateTFNResult'),
    re_path(r'^counting/(?P<uname>(guest))/$', counting, name='guest_counting'),
    re_path(r'^counting/$', counting, name='counting'),
    re_path(r'^saveWorkingGrain/$', saveWorkingGrain, name='saveWorkingGrain'),
    path('image/<str:project_name>/<str:sample_name>/<int:grain_nth>/<str:image_nth>/',
        get_image, name="get_image"),
]
