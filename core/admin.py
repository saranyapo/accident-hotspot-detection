from django.contrib import admin
from .models import Accident, HotspotCluster

class AccidentAdmin(admin.ModelAdmin):
    list_display = ('accident_id', 'city', 'state', 'date', 'accident_severity', 'custom_risk_score')
    list_filter = ('city', 'accident_severity', 'weather')
    search_fields = ('city', 'accident_id')

class HotspotClusterAdmin(admin.ModelAdmin):
    list_display = ('city', 'cluster_id', 'risk_level', 'avg_risk_score', 'accident_count', 'center_lat', 'center_lng')
    list_filter = ('city', 'risk_level')

admin.site.register(Accident, AccidentAdmin)
admin.site.register(HotspotCluster, HotspotClusterAdmin)