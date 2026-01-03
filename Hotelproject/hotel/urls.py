from django.urls import path
from . import views
from django.urls import include
from django.contrib import admin
urlpatterns = [
    path('', views.guest_home, name='guest_home'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
]

