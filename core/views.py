from django.http import JsonResponse
from django.shortcuts import render
from .models import Accident, HotspotCluster
from geopy.geocoders import Nominatim


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
            "center_lat": c.center_lat,
            "center_lng": c.center_lng,
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