from django.urls import path
from . import views

urlpatterns = [
    path("api/hotspots/", views.hotspot_json, name="hotspot_json"),
]