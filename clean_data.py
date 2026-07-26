import pandas as pd

# Load the raw dataset
df = pd.read_csv("data/indian_roads_dataset.csv")

# Drop 'festival' (too many missing values) and 'risk_score' (we'll create our own later)
df = df.drop(columns=["festival", "risk_score"], errors="ignore")

# Display basic information
print("New shape:", df.shape)
print("\nRemaining columns:")
print(df.columns.tolist())

# Save the cleaned dataset as a new CSV file
df.to_csv("data/cleaned_accidents.csv", index=False)

print("\nSaved cleaned dataset to data/cleaned_accidents.csv")

# Verify that the cleaned file was saved correctly
print("\nFirst 5 rows of the cleaned dataset:")
check = pd.read_csv("data/cleaned_accidents.csv")
print(check.head())