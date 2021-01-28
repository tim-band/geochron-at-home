from django.conf.urls import include, url
from django.contrib import admin
from django.contrib.auth import views as auth_views

from ftc.views import profile

#from django.contrib.auth.views import login, logout

admin.autodiscover()

urlpatterns = [
    # Examples:
    url(r'^accounts/logout/$', auth_views.LogoutView.as_view(), {'next_page': 'home'}, name="logout"),
    url(r'^accounts/profile/$', profile, name="profile"),
    url(r'^accounts/', include('allauth.urls')),
    # admin
    url(r'^admin/', admin.site.urls),
    url(r'^ftc/', include('ftc.urls')),
]
