from django.conf.urls import include, re_path
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path

from ftc.views import profile

#from django.contrib.auth.views import login, logout

admin.autodiscover()

urlpatterns = [
    # Examples:
    path('accounts/logout/', auth_views.LogoutView.as_view(), {'next_page': 'home'}, name="logout"),
    path('accounts/profile/', profile, name="profile"),
    path('accounts/', include('allauth.urls')),
    # admin
    path('admin/', admin.site.urls),
    path('ftc/', include('ftc.urls')),
]
