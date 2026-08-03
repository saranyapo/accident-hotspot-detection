from django.core.management.base import BaseCommand
import pandas as pd
import numpy as np
from django.db import connection
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score

from core.models import HotspotCluster


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

            # Inverse-transform cluster centers back to real lat/lng/risk scale
            centers = scaler.inverse_transform(kmeans.cluster_centers_)

            # Compute per-cluster stats: center, avg risk, accident count
            cluster_stats = []
            for cluster_id in range(chosen_k):
                cluster_rows = city_df[city_df['cluster'] == cluster_id]
                avg_risk = cluster_rows['custom_risk_score'].mean()
                center_lat, center_lng, _ = centers[cluster_id]
                cluster_stats.append({
                    'city': city,
                    'cluster_id': cluster_id,
                    'center_lat': float(center_lat),
                    'center_lng': float(center_lng),
                    'avg_risk_score': float(avg_risk),
                    'accident_count': int(len(cluster_rows)),
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