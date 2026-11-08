"""Root URL configuration for waveform_designer standalone application."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("broadbean.designer.urls", namespace="waveform_designer")),
]
