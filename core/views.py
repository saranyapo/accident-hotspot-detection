import os
import math
import requests
from django.http import JsonResponse
from django.shortcuts import render
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_POST, require_GET
from .models import Accident, HotspotCluster, UserReport
from geopy.geocoders import Nominatim


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


HOTSPOT_MATCH_RADIUS_KM = 0.3  # ~300m — "essentially on the route"


def _point_to_segment_distance_km(lat, lng, lat1, lng1, lat2, lng2):
    """
    Perpendicular distance in km from point (lat, lng) to the line
    segment between (lat1, lng1) and (lat2, lng2) — not just to the
    two endpoints. Projects onto a local flat km-plane centered on the
    segment's midpoint (fine for short segments like route steps),
    clamps the projection to the segment so points near a sharp turn
    don't get an artificially short distance.
    """
    # Local flat-earth approximation: convert lat/lng degrees to km
    # using the segment midpoint's latitude for the longitude scale
    lat_mid = (lat1 + lat2) / 2
    km_per_deg_lat = 111.32
    km_per_deg_lng = 111.32 * math.cos(math.radians(lat_mid))

    # Segment endpoints and point, in local km coordinates (x=lng, y=lat)
    x1, y1 = lng1 * km_per_deg_lng, lat1 * km_per_deg_lat
    x2, y2 = lng2 * km_per_deg_lng, lat2 * km_per_deg_lat
    px, py = lng * km_per_deg_lng, lat * km_per_deg_lat

    dx, dy = x2 - x1, y2 - y1
    seg_len_sq = dx * dx + dy * dy

    if seg_len_sq == 0:
        # Degenerate segment (both points identical) — just point distance
        return haversine_distance(lat, lng, lat1, lng1)

    # Project point onto the segment, clamped to [0, 1]
    t = ((px - x1) * dx + (py - y1) * dy) / seg_len_sq
    t = max(0.0, min(1.0, t))

    closest_x = x1 + t * dx
    closest_y = y1 + t * dy

    return math.hypot(px - closest_x, py - closest_y)


def _match_hotspots_to_route(coords):
    """
    coords: list of [lng, lat] pairs from OSRM's geojson geometry.
    Returns matched hotspots (deduplicated) within HOTSPOT_MATCH_RADIUS_KM
    of the route's actual line (nearest segment), not just its vertices.
    """
    all_hotspots = HotspotCluster.objects.all()
    matched = {}

    for h in all_hotspots:
        best_dist = None

        for i in range(len(coords) - 1):
            lng1, lat1 = coords[i]
            lng2, lat2 = coords[i + 1]

            dist = _point_to_segment_distance_km(
                h.center_lat, h.center_lng, lat1, lng1, lat2, lng2
            )

            if best_dist is None or dist < best_dist:
                best_dist = dist

            # Early exit: can't get closer than "on the route"
            if best_dist == 0:
                break

        if best_dist is not None and best_dist <= HOTSPOT_MATCH_RADIUS_KM:
            matched[h.id] = {
                "id": h.id,
                "city": h.city,
                "area_name": h.area_name,
                "risk_level": h.risk_level,
                "avg_risk_score": round(h.avg_risk_score, 3),
                "accident_count": h.accident_count,
                "lat": h.center_lat,
                "lng": h.center_lng,
                "distance_km": round(best_dist, 3),
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


# =====================================================================
# Community Reporting Feature APIs
# =====================================================================

COVERAGE_RADIUS_KM = 50.0  # Same threshold as map check


@require_POST
def submit_report(request):
    """
    Handles submission of community hazard reports by public users.
    Validates input fields, computes dataset coverage status, and saves
    the report with status='Pending' for admin review.
    """
    name = request.POST.get("name", "").strip()
    email = request.POST.get("email", "").strip()
    lat_str = request.POST.get("latitude", "").strip()
    lng_str = request.POST.get("longitude", "").strip()
    issue_type = request.POST.get("issue_type", "").strip()
    description = request.POST.get("description", "").strip()
    photo = request.FILES.get("photo")

    # 1. Validate Name
    if not name:
        return JsonResponse({"error": "Please provide your name."}, status=400)
    if len(name) > 100:
        return JsonResponse({"error": "Name cannot exceed 100 characters."}, status=400)

    # 2. Validate Email
    if not email:
        return JsonResponse({"error": "Please provide an email address."}, status=400)
    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({"error": "Please provide a valid email address."}, status=400)

    # 3. Validate Coordinates
    if not lat_str or not lng_str:
        return JsonResponse({"error": "Please select a location on the map or via search."}, status=400)
    try:
        latitude = float(lat_str)
        longitude = float(lng_str)
    except ValueError:
        return JsonResponse({"error": "Invalid coordinates provided."}, status=400)

    if not (-90.0 <= latitude <= 90.0) or not (-180.0 <= longitude <= 180.0):
        return JsonResponse({"error": "Coordinates are out of valid geographic range."}, status=400)

    # 4. Validate Issue Type
    valid_issue_types = dict(UserReport.ISSUE_TYPES)
    if issue_type not in valid_issue_types:
        return JsonResponse({"error": "Please select a valid issue type."}, status=400)

    # 5. Validate Description
    if not description:
        return JsonResponse({"error": "Please provide a description of the road issue."}, status=400)
    if len(description) > 1000:
        return JsonResponse({"error": "Description cannot exceed 1000 characters."}, status=400)

    # 6. Validate Optional Photo
    if photo:
        # Check file size (max 5 MB)
        if photo.size > 5 * 1024 * 1024:
            return JsonResponse({"error": "Photo file size cannot exceed 5 MB."}, status=400)

        # Check file extension and mime type
        ext = os.path.splitext(photo.name)[1].lower()
        allowed_extensions = ['.jpg', '.jpeg', '.png']
        allowed_types = ['image/jpeg', 'image/png', 'image/jpg']
        if ext not in allowed_extensions or (photo.content_type and photo.content_type.lower() not in allowed_types):
            return JsonResponse({"error": "Only JPG and PNG images are allowed."}, status=400)

    # 7. Compute Coverage Status based on nearest HotspotCluster
    is_in_coverage = False
    all_clusters = HotspotCluster.objects.all()
    for cluster in all_clusters:
        dist = haversine_distance(latitude, longitude, cluster.center_lat, cluster.center_lng)
        if dist <= COVERAGE_RADIUS_KM:
            is_in_coverage = True
            break

    coverage_status = "InCoverage" if is_in_coverage else "OutOfCoverage"

    # 8. Save report to database
    report = UserReport.objects.create(
        name=name,
        email=email,
        latitude=latitude,
        longitude=longitude,
        issue_type=issue_type,
        description=description,
        photo=photo,
        status="Pending",
        coverage_status=coverage_status,
    )

    return JsonResponse({
        "success": True,
        "message": "Report submitted, pending admin approval.",
        "report_id": report.id
    })


@require_GET
def approved_reports_json(request):
    """
    Returns only Approved community hazard reports for the Leaflet map overlay.
    Public view: NEVER includes user email for privacy.
    """
    approved_reports = UserReport.objects.filter(status="Approved").order_by("-timestamp")
    reports_data = []

    for r in approved_reports:
        # Date format: e.g. "14 Aug 2026"
        formatted_date = f"{r.timestamp.day} {r.timestamp.strftime('%b %Y')}"

        reports_data.append({
            "id": r.id,
            "lat": r.latitude,
            "lng": r.longitude,
            "issue_type": r.get_issue_type_display(),
            "description": r.description,
            "reported_by": r.name,
            "date": formatted_date,
            "photo_url": r.photo.url if r.photo else None,
            "coverage_status": r.coverage_status,
        })

    return JsonResponse({"reports": reports_data})