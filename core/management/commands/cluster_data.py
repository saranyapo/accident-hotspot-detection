from django.core.management.base import BaseCommand
import pandas as pd
import numpy as np
import time

from django.db import connection
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score
from geopy.geocoders import Nominatim

from core.models import Accident, HotspotCluster


geolocator = Nominatim(
    user_agent="accident_hotspot_project"
)

def get_area_name(latitude, longitude):
    try:
        location = geolocator.reverse(
            (latitude, longitude),
            exactly_one=True,
            language="en"
        )

        if not location:
            return "Unknown Area"

        address = location.raw.get("address", {})

        area_name = (
            address.get("suburb")
            or address.get("neighbourhood")
            or address.get("city_district")
            or address.get("town")
            or address.get("city")
            or "Unknown Area"
        )

        return area_name

    except Exception as e:
        print("Geocoding error:", e)
        return "Unknown Area"

def is_water_location(latitude, longitude):
    try:
        location = geolocator.reverse(
            (latitude, longitude),
            exactly_one=True,
            language="en"
        )

        if not location:
            return False

        address = location.raw.get("address", {})

        water_keys = [
            "water",
            "sea",
            "ocean",
            "bay",
            "strait",
            "reservoir",
            "lake",
            "river",
            "canal",
            "harbour",
            "dock",
            "marina"
        ]

        for key in water_keys:
            if key in address:
                return True

        display_name = location.raw.get(
            "display_name", ""
        ).lower()

        water_words = [
            "arabian sea",
            "sea",
            "ocean",
            "bay",
            "lake",
            "river",
            "reservoir",
            "canal",
            "harbour",
            "harbor",
            "water",
            "creek"
        ]

        for word in water_words:
            if word in display_name:
                return True

        return False

    except Exception as e:
        print("Water validation error:", e)
        return False

def find_land_medoid(cluster_rows, original_lat, original_lng):
    """
    Find the nearest actual accident point in the same cluster.
    Only validate a limited number of closest candidates.
    """

    candidates = []

    for _, row in cluster_rows.iterrows():

        latitude = float(row["latitude"])
        longitude = float(row["longitude"])

        distance = np.sqrt(
            (latitude - original_lat) ** 2 +
            (longitude - original_lng) ** 2
        )

        candidates.append(
            (distance, latitude, longitude)
        )

    # Sort by distance from the original medoid
    candidates.sort(key=lambda x: x[0])

    # Check only the 10 closest actual accident points
    # instead of every point in the cluster
    for distance, latitude, longitude in candidates[:10]:

        if not is_water_location(
            latitude,
            longitude
        ):
            return latitude, longitude

        # Small delay between Nominatim requests
        time.sleep(1)

    # If none of the checked points is confirmed as land,
    # keep the original medoid
    return original_lat, original_lng

class Command(BaseCommand):
    help = "Load accident data from MySQL, run K-Means clustering per city, and save hotspot clusters"

    def handle(self, *args, **options):
        # Step A: Load data from MySQL into pandas
        query = "SELECT accident_id, city, latitude, longitude, custom_risk_score FROM accidents"
        df = pd.read_sql(query, connection)
        self.stdout.write(f"Loaded {len(df)} rows from MySQL")

        # Step B: Cluster separately for each city
        all_results = []
        all_cluster_stats = []

        for city in df['city'].unique():
            city_df = df[df['city'] == city].copy()

            features = city_df[['latitude', 'longitude', 'custom_risk_score']]
            scaler = StandardScaler()
            scaled_features = scaler.fit_transform(features)

            # --- Elbow method + silhouette score: test k=2 to k=10 ---
            self.stdout.write(f"\n{city} — inertia & silhouette by k:")
            inertias = []
            k_range = range(2, 11)
            for k in k_range:
                test_kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
                test_kmeans.fit(scaled_features)
                inertias.append(test_kmeans.inertia_)
                sil_score = silhouette_score(scaled_features, test_kmeans.labels_)
                self.stdout.write(
                    f"  k={k}: inertia={test_kmeans.inertia_:.2f}, silhouette={sil_score:.3f}"
                )

            # Drop between consecutive k values, to spot the elbow visually
            self.stdout.write(f"{city} — drop in inertia between steps:")
            for i in range(1, len(inertias)):
                drop = inertias[i - 1] - inertias[i]
                self.stdout.write(f"  k={k_range[i-1]}->k={k_range[i]}: drop={drop:.2f}")

            # --- Final clustering using chosen k ---
            # (update chosen_k after reviewing inertia/silhouette output above)
            chosen_k = 5
            kmeans = KMeans(n_clusters=chosen_k, random_state=42, n_init=10)
            city_df['cluster'] = kmeans.fit_predict(scaled_features)

            # Save cluster assignment for each accident
            for _, row in city_df.iterrows():
                Accident.objects.filter(
                    accident_id=int(row['accident_id'])
                ).update(
                    cluster_id=int(row['cluster'])
                )

            # Compute per-cluster stats: medoid (real accident point closest to
            # the cluster center), avg risk, accident count
            cluster_stats = []
            for cluster_id in range(chosen_k):
                cluster_mask = city_df['cluster'].values == cluster_id
                cluster_rows = city_df[cluster_mask]
                avg_risk = cluster_rows['custom_risk_score'].mean()

                # Find the real data point closest to this cluster's center
                # (in scaled feature space) — this becomes our medoid
                cluster_positions = np.where(cluster_mask)[0]
                cluster_scaled_points = scaled_features[cluster_positions]
                cluster_center_scaled = kmeans.cluster_centers_[cluster_id]

                distances = np.linalg.norm(
                    cluster_scaled_points - cluster_center_scaled, axis=1
                )
                medoid_position = cluster_positions[np.argmin(distances)]
                medoid_row = city_df.iloc[medoid_position]

                center_lat = float(medoid_row['latitude'])
                center_lng = float(medoid_row['longitude'])

                # -------------------------------------------------
                # Feature 7: Validate hotspot location
                # -------------------------------------------------

                if is_water_location(center_lat, center_lng):

                    self.stdout.write(
                        self.style.WARNING(
                            f"{city} cluster {cluster_id}: "
                            f"Medoid appears to be in WATER "
                            f"({center_lat}, {center_lng})"
                        )
                    )

                    # Find nearest actual accident point on land
                    center_lat, center_lng = find_land_medoid(
                        cluster_rows,
                        center_lat,
                        center_lng
                    )

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"{city} cluster {cluster_id}: "
                            f"Corrected to LAND point "
                            f"({center_lat}, {center_lng})"
                        )
                    )

                else:

                    self.stdout.write(
                        f"{city} cluster {cluster_id}: "
                        f"Medoid is on LAND"
                    )


                # Find approximate area name using the medoid coordinates
                area_name = get_area_name(
                    center_lat,
                    center_lng
                )

                # Small delay between Nominatim requests
                time.sleep(1)


                cluster_stats.append({
                    'city': city,
                    'cluster_id': cluster_id,
                    'center_lat': center_lat,
                    'center_lng': center_lng,
                    'avg_risk_score': float(avg_risk),
                    'accident_count': int(len(cluster_rows)),
                    'area_name': area_name,
                })

            # Bucket avg risk into Low / Medium / High using tertiles within this city
            risk_values = [c['avg_risk_score'] for c in cluster_stats]
            low_cut, high_cut = np.percentile(risk_values, [33, 66])
            for c in cluster_stats:
                if c['avg_risk_score'] <= low_cut:
                    c['risk_level'] = 'Low'
                elif c['avg_risk_score'] <= high_cut:
                    c['risk_level'] = 'Medium'
                else:
                    c['risk_level'] = 'High'

            all_cluster_stats.extend(cluster_stats)

            self.stdout.write(
                f"{city}: {len(city_df)} rows, "
                f"cluster sizes: {city_df['cluster'].value_counts().to_dict()}"
            )

            all_results.append(city_df)

        # Step C: Combine all cities back into one DataFrame (per-accident cluster labels)
        final_df = pd.concat(all_results, ignore_index=True)
        self.stdout.write(f"\nTotal rows after clustering: {len(final_df)}")
        self.stdout.write(str(final_df.head()))

        # Step D: Save hotspot summary (centers + risk levels) into HotspotCluster table
        HotspotCluster.objects.all().delete()
        HotspotCluster.objects.bulk_create([
            HotspotCluster(**stats) for stats in all_cluster_stats
        ])
        self.stdout.write(
            self.style.SUCCESS(
                f"\nSaved {len(all_cluster_stats)} hotspot clusters to HotspotCluster table"
            )
        )