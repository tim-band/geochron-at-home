from django.conf.urls import patterns, include, url

urlpatterns = patterns('',
    # Ex: /ftc/
    url(r'^$', 'ftc.views.home', name='home'),
    url(r'signup', 'ftc.views.signmeup', name='signmeup'),
    url(r'^report/$', 'ftc.views.report', name='report'),
    url(r'^getTableData/$', 'ftc.views.getTableData', name='getTableData'),
    url(r'^get_grain_images/$', 'ftc.views.get_grain_images', name='get_grain_images'),
    url(r'^updateTFNResult/$', 'ftc.views.updateTFNResult', name='updateTFNResult'),
    url(r'^counting/(?P<uname>(guest))/$', 'ftc.views.counting', name='guest_counting'),
    url(r'^counting/$', 'ftc.views.counting', name='counting'),
#   url(r'^counting/$', 'ftc.views.counting', name='counting'),
    url(r'^saveWorkingGrain/$', 'ftc.views.saveWorkingGrain', name='saveWorkingGrain'),
)
