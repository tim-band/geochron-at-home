from django.conf.urls import patterns, include, url

from django.contrib import admin

#from django.contrib.auth.views import login, logout

admin.autodiscover()

urlpatterns = patterns('',
    # Examples:
    url(r'^accounts/logout/$', 'django.contrib.auth.views.logout', {'next_page': 'home'}, name="logout"),
    url(r'^accounts/profile/$', 'ftc.views.profile', name="profile"),
    url(r'^accounts/', include('allauth.urls')),
    # admin
    url(r'^zdgly/', include(admin.site.urls)),
    url(r'^ftc/', include('ftc.urls')),
)
