import pandas as pd

df = pd.read_csv("data/cleaned_accidents.csv")
print(df[['accident_severity','traffic_density','weather','hour','is_peak_hour']].dtypes)
print(df['accident_severity'].unique())
print(df['traffic_density'].unique())
print(df['weather'].unique())
print(df['is_peak_hour'].unique())