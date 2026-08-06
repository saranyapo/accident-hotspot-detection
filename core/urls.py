from django.urls import path
from . import views

urlpatterns = [
    path("api/hotspots/", views.hotspot_json, name="hotspot_json"),
    path("", views.map_view, name="map_view"),
]