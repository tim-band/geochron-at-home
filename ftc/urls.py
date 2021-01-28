from django.conf.urls import include, url

from ftc.views import home, signmeup, report, getTableData,\
    get_grain_images, updateTFNResult, counting, saveWorkingGrain

urlpatterns = [
    # Ex: /ftc/
    url(r'^$', home, name='home'),
    url(r'signup', signmeup, name='signmeup'),
    url(r'^report/$', report, name='report'),
    url(r'^getTableData/$', getTableData, name='getTableData'),
    url(r'^get_grain_images/$', get_grain_images, name='get_grain_images'),
    url(r'^updateTFNResult/$', updateTFNResult, name='updateTFNResult'),
    url(r'^counting/(?P<uname>(guest))/$', counting, name='guest_counting'),
    url(r'^counting/$', counting, name='counting'),
    url(r'^saveWorkingGrain/$', saveWorkingGrain, name='saveWorkingGrain'),
]
