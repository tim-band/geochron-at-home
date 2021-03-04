from django.conf.urls import include, re_path
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path

from ftc.views import profile

#from django.contrib.auth.views import login, logout

admin.autodiscover()

urlpatterns = [
    # Examples:
    re_path(r'^accounts/logout/$', auth_views.LogoutView.as_view(), {'next_page': 'home'}, name="logout"),
    re_path(r'^accounts/profile/$', profile, name="profile"),
    re_path(r'^accounts/', include('allauth.urls')),
    # admin
    re_path(r'^admin/', admin.site.urls),
    path(r'ftc/', include('ftc.urls')),
]
