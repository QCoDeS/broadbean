"""Root URL configuration for waveform_designer standalone application."""

from django.urls import path, include
from django.contrib import admin

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("broadbean.designer.urls", namespace="waveform_designer")),
]
