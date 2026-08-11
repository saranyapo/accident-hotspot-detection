import pandas as pd

df = pd.read_csv("data/kerala_accidents.csv")

categorical_columns = [
    "city",
    "location",
    "road_type",
    "weather",
    "traffic_density",
    "cause",
    "accident_severity",
    "day_of_week"
]

for column in categorical_columns:
    print(f"\n{'=' * 50}")
    print(f"{column}")
    print(f"{'=' * 50}")
    print(df[column].value_counts())