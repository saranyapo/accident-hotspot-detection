"""
Adds a small random offset to each accident's latitude/longitude so that
accidents recorded at the same named location (e.g. "Vyttila Junction")
get distinct, realistic-looking coordinates instead of all sharing the
exact same point.
 
Input:  data/kerala_accidents.csv   (original raw file, untouched)
Output: data/kerala_accidents_jittered.csv
 
The jitter radius is roughly 100-300 meters, which is a realistic amount
of GPS/location variation for accidents recorded near the same junction —
it does not change which city or named location an accident belongs to,
only its exact point on the map.
"""
 
import pandas as pd
import numpy as np
 
INPUT_PATH = "data/kerala_accidents.csv"
OUTPUT_PATH = "data/kerala_accidents_jittered.csv"
 
# Roughly how far to jitter each point, in degrees.
# 1 degree of latitude ~ 111 km, so 0.001-0.003 degrees ~ 110-330 meters.
MIN_JITTER_DEG = 0.0005   # ~55 m
MAX_JITTER_DEG = 0.0030   # ~330 m
 
def add_jitter(value, rng):
    # Random direction, random magnitude within the min/max band
    magnitude = rng.uniform(MIN_JITTER_DEG, MAX_JITTER_DEG)
    sign = rng.choice([-1, 1])
    return value + (sign * magnitude)
 
def main():
    rng = np.random.default_rng(seed=42)  # seeded for reproducibility
 
    df = pd.read_csv(INPUT_PATH)
 
    required_cols = {"latitude", "longitude"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Missing expected columns in {INPUT_PATH}: {missing}")
 
    original_lat = df["latitude"].copy()
    original_lng = df["longitude"].copy()
 
    df["latitude"] = df["latitude"].apply(lambda v: add_jitter(v, rng))
    df["longitude"] = df["longitude"].apply(lambda v: add_jitter(v, rng))
 
    df.to_csv(OUTPUT_PATH, index=False)
 
    # Quick sanity check output
    max_lat_shift = (df["latitude"] - original_lat).abs().max()
    max_lng_shift = (df["longitude"] - original_lng).abs().max()
 
    print(f"Read {len(df)} rows from {INPUT_PATH}")
    print(f"Max latitude shift: {max_lat_shift:.6f} degrees")
    print(f"Max longitude shift: {max_lng_shift:.6f} degrees")
 
    if "location" in df.columns:
        dupe_check = df.groupby("location")[["latitude", "longitude"]].apply(
            lambda g: g.duplicated().sum()
        )
        remaining_dupes = dupe_check.sum()
        print(f"Rows still sharing exact coordinates within the same location: {remaining_dupes}")
 
    print(f"Saved jittered dataset to {OUTPUT_PATH}")
 
if __name__ == "__main__":
    main()