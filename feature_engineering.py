import pandas as pd

df = pd.read_csv("data/cleaned_accidents.csv")

# 1. Severity -> numeric weight (fatal = highest risk)
severity_map = {'minor': 1, 'major': 2, 'fatal': 3}
df['severity_score'] = df['accident_severity'].map(severity_map)

# 2. Casualties -> normalize 0-1 (already numeric)
df['casualties_norm'] = df['casualties'] / df['casualties'].max()

# 3. Traffic density -> numeric weight
density_map = {'low': 1, 'medium': 2, 'high': 3}
df['density_score'] = df['traffic_density'].map(density_map)

# 4. Weather -> numeric weight (fog riskiest due to visibility, then rain)
weather_map = {'clear': 1, 'rain': 2, 'fog': 3}
df['weather_score'] = df['weather'].map(weather_map)

# 5. Time of day -> use existing hour + is_peak_hour
def time_risk(row):
    if row['hour'] >= 22 or row['hour'] <= 5:
        return 3   # night - highest risk
    elif row['is_peak_hour'] == 1:
        return 2   # peak hour traffic
    else:
        return 1   # normal daytime
df['time_score'] = df.apply(time_risk, axis=1)

# 6. Normalize the remaining (non-already-normalized) components to 0-1
for col in ['severity_score', 'density_score', 'weather_score', 'time_score']:
    df[col + '_norm'] = df[col] / df[col].max()

# 7. Combine into final weighted custom risk score
df['custom_risk_score'] = (
    0.35 * df['severity_score_norm'] +
    0.25 * df['casualties_norm'] +
    0.15 * df['density_score_norm'] +
    0.15 * df['weather_score_norm'] +
    0.10 * df['time_score_norm']
)

# 8. Save back into cleaned dataset
df.to_csv("data/cleaned_accidents.csv", index=False)

# 9. Verify - this prints the summary stats and sample rows to your terminal
print(df['custom_risk_score'].describe())
print(df[['accident_severity', 'casualties', 'traffic_density', 'weather', 'hour', 'custom_risk_score']].head(10))
check = pd.read_csv("data/cleaned_accidents.csv")
print(check.columns.tolist())
print('custom_risk_score' in check.columns)