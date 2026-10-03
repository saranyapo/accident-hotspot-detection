from django.contrib import admin
from django.utils.html import format_html
from .models import Accident, HotspotCluster, UserReport


class AccidentAdmin(admin.ModelAdmin):
    list_display = ('accident_id', 'city', 'state', 'date', 'accident_severity', 'custom_risk_score')
    list_filter = ('city', 'accident_severity', 'weather')
    search_fields = ('city', 'accident_id')


class HotspotClusterAdmin(admin.ModelAdmin):
    list_display = ('city', 'cluster_id', 'risk_level', 'avg_risk_score', 'accident_count', 'center_lat', 'center_lng')
    list_filter = ('city', 'risk_level')


class UserReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'issue_type', 'status', 'coverage_status', 'photo_preview', 'timestamp')
    list_filter = ('status', 'coverage_status', 'issue_type')
    search_fields = ('name', 'description')
    readonly_fields = ('timestamp', 'photo_preview')
    actions = ['approve_reports', 'reject_reports']

    def photo_preview(self, obj):
        if obj.photo:
            return format_html(
                '<a href="{0}" target="_blank"><img src="{0}" style="max-height: 50px; max-width: 80px; object-fit: cover; border-radius: 4px; border: 1px solid #ccc;" /></a>',
                obj.photo.url
            )
        return "No Photo"
    photo_preview.short_description = "Photo Preview"

    @admin.action(description="Approve selected reports")
    def approve_reports(self, request, queryset):
        updated = queryset.update(status='Approved')
        self.message_user(request, f"{updated} report(s) successfully marked as Approved.")

    @admin.action(description="Reject selected reports")
    def reject_reports(self, request, queryset):
        updated = queryset.update(status='Rejected')
        self.message_user(request, f"{updated} report(s) successfully marked as Rejected.")


admin.site.register(Accident, AccidentAdmin)
admin.site.register(HotspotCluster, HotspotClusterAdmin)
admin.site.register(UserReport, UserReportAdmin)