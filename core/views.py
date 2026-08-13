from django.http import JsonResponse
from django.shortcuts import render
from .models import Accident, HotspotCluster
from geopy.geocoders import Nominatim
import math
import requests

def haversine_distance(lat1, lng1, lat2, lng2):
    """Returns distance in km between two lat/lng points."""
    R = 6371  # Earth's radius in km
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlng / 2) ** 2)
    c = 2 * math.asin(math.sqrt(a))
    return R * c

def _get_osrm_routes(start_lat, start_lng, end_lat, end_lng):
    url = (
        f"http://router.project-osrm.org/route/v1/driving/"
        f"{start_lng},{start_lat};{end_lng},{end_lat}"
        f"?alternatives=true&overview=full&geometries=geojson"
    )
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return None

    if data.get("code") != "Ok" or not data.get("routes"):
        return None

    return data["routes"]


HOTSPOT_MATCH_RADIUS_KM = 1.5

def _match_hotspots_to_route(coords):
    """
    coords: list of [lng, lat] pairs from OSRM's geojson geometry.
    Returns matched hotspots (deduplicated) within HOTSPOT_MATCH_RADIUS_KM of any point.
    """
    all_hotspots = HotspotCluster.objects.all()
    matched = {}

    # Sample points if the route is very long, so we're not checking
    # hundreds of points against every hotspot
    sample_coords = coords[::3] if len(coords) > 300 else coords

    for lng, lat in sample_coords:
        for h in all_hotspots:
            if h.id in matched:
                continue
            dist = haversine_distance(lat, lng, h.center_lat, h.center_lng)
            if dist <= HOTSPOT_MATCH_RADIUS_KM:
                matched[h.id] = {
                    "id": h.id,
                    "city": h.city,
                    "area_name": h.area_name,
                    "risk_level": h.risk_level,
                    "avg_risk_score": round(h.avg_risk_score, 3),
                    "accident_count": h.accident_count,
                    "lat": h.center_lat,
                    "lng": h.center_lng,
                    "distance_km": round(dist, 2),
                }

    return list(matched.values())


def _geocode_place(place_name):
    """Geocode with Kerala context appended to reduce ambiguous matches
    (e.g. 'Alappuzha' alone can resolve to a district centroid instead of the town)."""
    geolocator = Nominatim(user_agent="accident_hotspot_app")
    try:
        location = geolocator.geocode(f"{place_name}, Kerala, India", timeout=5)
    except Exception:
        return None
    if not location:
        return None
    return {"lat": location.latitude, "lng": location.longitude}


def route_risk_json(request):
    start_name = request.GET.get("start", "").strip()
    end_name = request.GET.get("end", "").strip()

    if not start_name or not end_name:
        return JsonResponse({"error": "Please provide both start and destination."}, status=400)

    start_point = _geocode_place(start_name)
    if not start_point:
        return JsonResponse({"error": f"Start location '{start_name}' not found, please check spelling."}, status=404)

    end_point = _geocode_place(end_name)
    if not end_point:
        return JsonResponse({"error": f"Destination '{end_name}' not found, please check spelling."}, status=404)

    routes = _get_osrm_routes(start_point["lat"], start_point["lng"], end_point["lat"], end_point["lng"])
    if not routes:
        return JsonResponse({"error": "No route could be found between these locations. Please try again."}, status=502)

    results = []
    for route in routes:
        coords = route["geometry"]["coordinates"]  # [[lng, lat], ...]
        matched = _match_hotspots_to_route(coords)

        if matched:
            avg_risk = round(sum(h["avg_risk_score"] for h in matched) / len(matched), 3)
            total_risk = round(sum(h["avg_risk_score"] for h in matched), 3)
            high_count = sum(1 for h in matched if h["risk_level"] == "High")
        else:
            avg_risk = None
            total_risk = None
            high_count = 0

        results.append({
            "distance_km": round(route["distance"] / 1000, 2),
            "duration_min": round(route["duration"] / 60, 1),
            "polyline": [[c[1], c[0]] for c in coords],  # convert to [lat, lng] for Leaflet
            "matched_hotspots": matched,
            "match_count": len(matched),
            "high_risk_count": high_count,
            "avg_risk_score": avg_risk,
            "total_risk_score": total_risk,
            "no_data": len(matched) == 0,
        })

    scored_routes = [r for r in results if not r["no_data"]]
    if scored_routes:
        best_index = results.index(min(scored_routes, key=lambda r: r["total_risk_score"]))
    else:
        best_index = 0

    return JsonResponse({
        "start": {"name": start_name, **start_point},
        "end": {"name": end_name, **end_point},
        "routes": results,
        "recommended_index": best_index,
    })


def hotspot_json(request):
    clusters = HotspotCluster.objects.all()

    data = []

    for c in clusters:

        # Get accidents belonging to this specific city + cluster
        accidents = Accident.objects.filter(
            city=c.city,
            cluster_id=c.cluster_id
        )

        total = accidents.count()

        # Default values
        traffic_density = "Unknown"
        traffic_density_percentage = 0

        peak_hour_percentage = 0

        serious_percentage = 0

        weather = "Unknown"
        weather_percentage = 0

        average_casualties = 0

        if total > 0:

            # --------------------------------
            # 1. Traffic density
            # --------------------------------
            density_counts = {}

            for accident in accidents:
                density = accident.traffic_density

                if density:
                    density_counts[density] = density_counts.get(
                        density, 0
                    ) + 1

            if density_counts:
                traffic_density = max(
                    density_counts,
                    key=density_counts.get
                )

                traffic_density_percentage = round(
                    (density_counts[traffic_density] / total) * 100
                )

            # --------------------------------
            # 2. Peak-hour accidents
            # --------------------------------
            peak_count = accidents.filter(
                is_peak_hour=True
            ).count()

            peak_hour_percentage = round(
                (peak_count / total) * 100
            )

            # --------------------------------
            # 3. Serious accidents
            # Major + Fatal
            # --------------------------------
            serious_count = accidents.filter(
                accident_severity__in=["major", "fatal"]
            ).count()

            serious_percentage = round(
                (serious_count / total) * 100
            )

            # --------------------------------
            # 4. Most common weather
            # --------------------------------
            weather_counts = {}

            for accident in accidents:
                weather_value = accident.weather

                if weather_value:
                    weather_counts[weather_value] = (
                        weather_counts.get(weather_value, 0) + 1
                    )

            if weather_counts:
                weather = max(
                    weather_counts,
                    key=weather_counts.get
                )

                weather_percentage = round(
                    (weather_counts[weather] / total) * 100
                )

            # --------------------------------
            # 5. Average casualties
            # --------------------------------
            average_casualties = round(
                sum(
                    accident.casualties
                    for accident in accidents
                ) / total,
                2
            )
            # --------------------------------
            # Identify significant risk factors
            # --------------------------------
            significant_factors = []

            if traffic_density_percentage >= 60:
                significant_factors.append(
                    f"High traffic density ({traffic_density_percentage}% of accidents)"
                )

            if peak_hour_percentage >= 60:
                significant_factors.append(
                    f"Peak-hour concentration ({peak_hour_percentage}% of accidents)"
                )

            if serious_percentage >= 40:
                significant_factors.append(
                    f"Serious accidents ({serious_percentage}% were major or fatal)"
                )

            if weather_percentage >= 50:
                significant_factors.append(
                    f"{weather} weather ({weather_percentage}% of accidents)"
                )

            if average_casualties >= 1.5:
                significant_factors.append(
                    f"High casualty rate (average {average_casualties} casualties)"
                )

            # --------------------------------
            # Create hotspot response
            # --------------------------------
        data.append({
            "city": c.city,
            "cluster_id": c.cluster_id,
            "lat": c.center_lat,
            "lng": c.center_lng,
            "risk_level": c.risk_level,
            "avg_risk_score": round(c.avg_risk_score, 3),
            "accident_count": c.accident_count,
            "area_name": c.area_name,

            # Feature 5
            "risk_factors": {
                "traffic_density": traffic_density,
                "traffic_density_percentage": traffic_density_percentage,

                "peak_hour_percentage": peak_hour_percentage,

                "serious_accident_percentage": serious_percentage,

                "weather": weather,
                "weather_percentage": weather_percentage,

                "average_casualties": average_casualties,
                "significant_factors": significant_factors,
            }
        })

    return JsonResponse({"hotspots": data}, safe=False)


def map_view(request):
    return render(request, 'core/map.html')


def geocode_search(request):
    query = request.GET.get('q', '').strip()

    if not query:
        return JsonResponse(
            {'error': 'No location provided'},
            status=400
        )

    geolocator = Nominatim(
        user_agent="accident_hotspot_app"
    )

    try:
        location = geolocator.geocode(
            query,
            timeout=5
        )

        if location:
            return JsonResponse({
                'lat': location.latitude,
                'lng': location.longitude,
                'display_name': location.address
            })

        return JsonResponse(
            {'error': 'Location not found'},
            status=404
        )

    except Exception:
        return JsonResponse(
            {'error': 'Geocoding service unavailable'},
            status=503
        )