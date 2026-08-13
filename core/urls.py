from django.urls import path
from . import views

urlpatterns = [
    path("api/hotspots/", views.hotspot_json, name="hotspot_json"),
    path("api/geocode/", views.geocode_search, name="geocode_search"),
    path("api/route-risk/", views.route_risk_json, name="route_risk_json"),
    path("", views.map_view, name="map_view"),
]