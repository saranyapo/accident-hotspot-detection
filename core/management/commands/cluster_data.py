from django.core.management.base import BaseCommand
import pandas as pd
from django.db import connection
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler


class Command(BaseCommand):
    help = "Load accident data from MySQL and run K-Means clustering per city"

    def handle(self, *args, **options):
        # Step A: Load data from MySQL into pandas
        query = "SELECT accident_id, city, latitude, longitude, custom_risk_score FROM accidents"
        df = pd.read_sql(query, connection)
        self.stdout.write(f"Loaded {len(df)} rows from MySQL")

        # Step B: Cluster separately for each city
        all_results = []
        for city in df['city'].unique():
            city_df = df[df['city'] == city].copy()

            features = city_df[['latitude', 'longitude', 'custom_risk_score']]
            scaler = StandardScaler()
            scaled_features = scaler.fit_transform(features)

            # Elbow method: test k=2 to k=10, record inertia for each
            self.stdout.write(f"\n{city} — inertia by k:")
            inertias = []
            k_range = range(2, 11)
            for k in k_range:
                test_kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
                test_kmeans.fit(scaled_features)
                inertias.append(test_kmeans.inertia_)
                self.stdout.write(f"  k={k}: inertia={test_kmeans.inertia_:.2f}")

            # Calculate drop between consecutive k values to spot the elbow
            self.stdout.write(f"{city} — drop in inertia between steps:")
            for i in range(1, len(inertias)):
                drop = inertias[i-1] - inertias[i]
                self.stdout.write(f"  k={k_range[i-1]}->k={k_range[i]}: drop={drop:.2f}")

            # Final clustering using chosen k (update this after reviewing all cities)
            chosen_k = 5
            kmeans = KMeans(n_clusters=chosen_k, random_state=42, n_init=10)
            city_df['cluster'] = kmeans.fit_predict(scaled_features)

            self.stdout.write(f"{city}: {len(city_df)} rows, cluster sizes: {city_df['cluster'].value_counts().to_dict()}")

            all_results.append(city_df)

        # Step C: Combine all cities back into one DataFrame
        final_df = pd.concat(all_results, ignore_index=True)
        self.stdout.write(f"\nTotal rows after clustering: {len(final_df)}")
        self.stdout.write(str(final_df.head()))