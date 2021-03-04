from django.conf.urls import include, re_path
from django.urls import path

from ftc.views import home, signmeup, report, getTableData, \
    get_grain_images, updateTFNResult, counting, saveWorkingGrain, \
    get_image

urlpatterns = [
    # Ex: /ftc/
    path('', home, name='home'),
    path('signup', signmeup, name='signmeup'),
    path('report/', report, name='report'),
    path('getTableData/', getTableData, name='getTableData'),
    path('get_grain_images/', get_grain_images, name='get_grain_images'),
    path('updateTFNResult/', updateTFNResult, name='updateTFNResult'),
    re_path(r'^counting/(?P<uname>(guest))/$', counting, name='guest_counting'),
    path('counting/', counting, name='counting'),
    path('saveWorkingGrain/', saveWorkingGrain, name='saveWorkingGrain'),
    path('image/<str:project_name>/<str:sample_name>/<int:grain_nth>/<str:ft_type>/<str:image_nth>/',
        get_image, name="get_image"),
]
