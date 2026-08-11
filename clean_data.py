import pandas as pd

# Load the Kerala dataset
df = pd.read_csv("data/kerala_accidents.csv")

print("Original shape:", df.shape)

# Add state because the new dataset contains only Kerala accidents
df["state"] = "Kerala"

# Normalize categorical values to lowercase
# This keeps them compatible with the existing feature_engineering.py mappings
categorical_columns = [
    "road_type",
    "weather",
    "traffic_density",
    "cause",
    "accident_severity",
    "day_of_week"
]

for column in categorical_columns:
    df[column] = df[column].str.lower()

# Keep only the columns needed by the project
required_columns = [
    "accident_id",
    "city",
    "state",
    "location",
    "latitude",
    "longitude",
    "date",
    "time",
    "hour",
    "day_of_week",
    "is_weekend",
    "road_type",
    "lanes",
    "traffic_signal",
    "weather",
    "visibility",
    "temperature",
    "traffic_density",
    "cause",
    "accident_severity",
    "vehicles_involved",
    "casualties",
    "is_peak_hour"
]

df = df[required_columns]

# Check for missing values
print("\nNull values:")
print(df.isnull().sum())

# Check for duplicate rows
print("\nDuplicate rows:", df.duplicated().sum())

# Display final shape and columns
print("\nCleaned shape:", df.shape)

print("\nFinal columns:")
print(df.columns.tolist())

# Save the cleaned dataset
df.to_csv("data/cleaned_accidents.csv", index=False)

print("\nSaved cleaned dataset to data/cleaned_accidents.csv")

# Verify the saved file
check = pd.read_csv("data/cleaned_accidents.csv")

print("\nFirst 5 rows of cleaned dataset:")
print(check.head())

print("\nCleaned dataset shape after reload:", check.shape)