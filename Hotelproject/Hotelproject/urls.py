"""
URL configuration for Hotelproject project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from hotel.api import (
    RoomViewSet, RoomCategoryViewSet, ReservationViewSet,
    PaymentViewSet, ServiceViewSet, ContactViewSet
)

# API Router
router = DefaultRouter()
router.register(r'api/rooms', RoomViewSet, basename='room')
router.register(r'api/categories', RoomCategoryViewSet, basename='category')
router.register(r'api/reservations', ReservationViewSet, basename='reservation')
router.register(r'api/payments', PaymentViewSet, basename='payment')
router.register(r'api/services', ServiceViewSet, basename='service')
router.register(r'api/contacts', ContactViewSet, basename='contact')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('hotel.urls')),
    path('', include(router.urls)),
    path('api-auth/', include('rest_framework.urls')),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
