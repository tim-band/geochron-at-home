from django.conf.urls import include, re_path

from ftc.views import home, signmeup, report, getTableData,\
    get_grain_images, updateTFNResult, counting, saveWorkingGrain

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
]
