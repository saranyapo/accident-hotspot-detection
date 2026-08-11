import pandas as pd

df = pd.read_csv("data/kerala_accidents.csv")  # adjust filename

print("Shape:", df.shape)
print("\nColumns:", list(df.columns))
print("\nDtypes:\n", df.dtypes)
print("\nNull counts:\n", df.isnull().sum())
print("\nDuplicate rows:", df.duplicated().sum())
print("\nHead:\n", df.head())