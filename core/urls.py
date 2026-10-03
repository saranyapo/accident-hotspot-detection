from django.urls import path
from . import views

urlpatterns = [
    path("api/hotspots/", views.hotspot_json, name="hotspot_json"),
    path("api/geocode/", views.geocode_search, name="geocode_search"),
    path("api/route-risk/", views.route_risk_json, name="route_risk_json"),
    path("api/reports/submit/", views.submit_report, name="submit_report"),
    path("api/reports/approved/", views.approved_reports_json, name="approved_reports_json"),
    path("", views.map_view, name="map_view"),
]