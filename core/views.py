from django.http import JsonResponse
from django.shortcuts import render
from .models import HotspotCluster
from geopy.geocoders import Nominatim

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


def map_view(request):
    return render(request, 'core/map.html')


def geocode_search(request):
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({'error': 'No location provided'}, status=400)

    geolocator = Nominatim(user_agent="accident_hotspot_app")
    try:
        location = geolocator.geocode(query, timeout=5)
        if location:
            return JsonResponse({
                'lat': location.latitude,
                'lng': location.longitude,
                'display_name': location.address
            })
        return JsonResponse({'error': 'Location not found'}, status=404)
    except Exception:
        return JsonResponse({'error': 'Geocoding service unavailable'}, status=503)