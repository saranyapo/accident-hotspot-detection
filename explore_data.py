import pandas as pd

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)

df = pd.read_csv("data/indian_roads_dataset.csv")

print("SHAPE:", df.shape)

print("\n--- HEAD ---")
print(df.head())

print("\n--- INFO ---")
df.info()

print("\n--- NULL COUNTS ---")
print(df.isnull().sum().sort_values(ascending=False))

print("\n--- DUPLICATE ROWS ---")
print(df.duplicated().sum())