from django.http import JsonResponse
from .models import HotspotCluster

def hotspot_json(request):
    clusters = HotspotCluster.objects.all()

    data = [
        {
            "city": c.city,
            "cluster_id": c.cluster_id,
            "lat": c.center_lat,
            "lng": c.center_lng,
            "risk_level": c.risk_level,
            "avg_risk_score": round(c.avg_risk_score, 3),
            "accident_count": c.accident_count,
        }
        for c in clusters
    ]

    return JsonResponse({"hotspots": data}, safe=False)