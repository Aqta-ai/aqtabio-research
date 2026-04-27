# AqtaBio API Examples for Researchers

## Quick Start Examples

### Python Research Toolkit

```python
from scripts.research_toolkit import AqtaBioClient, ResearchAnalytics

# Initialize client
client = AqtaBioClient()

# Get risk for a specific tile
risk_data = client.get_tile_risk(
    tile_id="AF-025-10000",
    pathogen="ebola", 
    month="2026-03"
)

print(f"Risk Score: {risk_data['risk_score']:.3f}")
print(f"Top Driver: {risk_data['top_drivers'][0]['feature_name']}")
```

### R Integration

```r
library(httr)
library(jsonlite)

# Authentication
auth_response <- POST(
  "https://kfj3domgfgegnd7aqtfwpdj56y0evnyv.lambda-url.eu-west-1.on.aws/auth/judge-token",
  body = list(code = "AQTA-SOLVE-2026"),
  encode = "json"
)

token <- content(auth_response)$token

# Get tile risk
get_tile_risk <- function(tile_id, pathogen, month, token) {
  response <- GET(
    paste0("https://kfj3domgfgegnd7aqtfwpdj56y0evnyv.lambda-url.eu-west-1.on.aws/tiles/", tile_id, "/risk"),
    query = list(pathogen = pathogen, month = month),
    add_headers(Authorization = paste("Bearer", token))
  )
  
  return(content(response))
}

# Example usage
ebola_risk <- get_tile_risk("AF-025-10000", "ebola", "2026-03", token)
print(paste("Risk Score:", ebola_risk$risk_score))
```

### MATLAB Integration

```matlab
% Authentication
auth_url = 'https://kfj3domgfgegnd7aqtfwpdj56y0evnyv.lambda-url.eu-west-1.on.aws/auth/judge-token';
auth_data = struct('code', 'AQTA-SOLVE-2026');
auth_options = weboptions('MediaType', 'application/json');

auth_response = webwrite(auth_url, auth_data, auth_options);
token = auth_response.token;

% Get tile risk
function risk_data = getTileRisk(tile_id, pathogen, month, token)
    base_url = 'https://kfj3domgfgegnd7aqtfwpdj56y0evnyv.lambda-url.eu-west-1.on.aws';
    url = sprintf('%s/tiles/%s/risk?pathogen=%s&month=%s', base_url, tile_id, pathogen, month);
    
    options = weboptions('HeaderFields', {'Authorization', ['Bearer ' token]});
    risk_data = webread(url, options);
end

% Example usage
risk_data = getTileRisk('AF-025-10000', 'ebola', '2026-03', token);
fprintf('Risk Score: %.3f\n', risk_data.risk_score);
```

## Research Workflow Examples

### 1. Hotspot Identification

```python
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.cluster import DBSCAN

# Get regional data
client = AqtaBioClient()
west_africa = (-15, 4, 5, 15)  # bbox
ebola_data = client.get_regional_data(west_africa, "ebola", "2026-03")

# Identify hotspots (top 10% risk)
threshold = ebola_data['risk_score'].quantile(0.9)
hotspots = ebola_data[ebola_data['risk_score'] >= threshold]

# Spatial clustering
coords = hotspots[['centroid_lat', 'centroid_lon']].values
clusters = DBSCAN(eps=0.5, min_samples=3).fit(coords)
hotspots['cluster'] = clusters.labels_

# Visualize
plt.figure(figsize=(12, 8))
scatter = plt.scatter(
    hotspots['centroid_lon'], 
    hotspots['centroid_lat'],
    c=hotspots['risk_score'], 
    cmap='Reds',
    s=50
)
plt.colorbar(scatter, label='Risk Score')
plt.xlabel('Longitude')
plt.ylabel('Latitude')
plt.title('Ebola Risk Hotspots - West Africa')
plt.show()

print(f"Identified {len(hotspots)} hotspot tiles")
print(f"Found {len(hotspots[hotspots['cluster'] >= 0])} clustered hotspots")
```

### 2. Temporal Risk Analysis

```python
# Track risk evolution over 6 months
tile_ids = ["AF-025-10000", "AF-025-10001", "AF-025-10002"]
temporal_data = client.get_temporal_series(
    tile_ids, "ebola", "2026-01", "2026-06"
)

# Calculate trends
trends = ResearchAnalytics.calculate_risk_trends(temporal_data)

# Visualize trends
fig, axes = plt.subplots(1, 2, figsize=(15, 6))

# Risk evolution
for tile_id in tile_ids:
    tile_data = temporal_data[temporal_data['tile_id'] == tile_id]
    axes[0].plot(tile_data['month'], tile_data['risk_score'], 
                marker='o', label=tile_id)

axes[0].set_xlabel('Month')
axes[0].set_ylabel('Risk Score')
axes[0].set_title('Risk Evolution Over Time')
axes[0].legend()
axes[0].tick_params(axis='x', rotation=45)

# Trend slopes
axes[1].bar(trends['tile_id'], trends['trend_slope'])
axes[1].set_xlabel('Tile ID')
axes[1].set_ylabel('Trend Slope')
axes[1].set_title('Risk Trend Slopes')
axes[1].tick_params(axis='x', rotation=45)

plt.tight_layout()
plt.show()
```

### 3. Cross-Pathogen Comparison

```python
# Compare risk patterns across pathogens
pathogens = ["ebola", "h5n1", "cchfv"]
sample_tiles = ebola_data['tile_id'].head(50).tolist()

comparison_data = client.get_cross_pathogen_comparison(
    sample_tiles, pathogens, "2026-03"
)

# Risk correlation analysis
risk_cols = [f"{p}_risk" for p in pathogens]
risk_matrix = comparison_data[risk_cols]
risk_matrix.columns = [col.replace('_risk', '').upper() for col in risk_matrix.columns]

# Correlation heatmap
import seaborn as sns
plt.figure(figsize=(8, 6))
sns.heatmap(risk_matrix.corr(), annot=True, cmap='coolwarm', center=0)
plt.title('Cross-Pathogen Risk Correlations')
plt.show()

# Risk distribution comparison
fig, axes = plt.subplots(1, 3, figsize=(18, 5))
for i, pathogen in enumerate(pathogens):
    risk_col = f"{pathogen}_risk"
    axes[i].hist(comparison_data[risk_col].dropna(), bins=20, alpha=0.7)
    axes[i].set_xlabel('Risk Score')
    axes[i].set_ylabel('Frequency')
    axes[i].set_title(f'{pathogen.upper()} Risk Distribution')

plt.tight_layout()
plt.show()
```

### 4. Feature Importance Analysis

```python
# Extract SHAP explanations
shap_data = client.extract_shap_explanations(
    sample_tiles, "ebola", "2026-03"
)

# Feature importance statistics
feature_stats = ResearchAnalytics.feature_importance_analysis(shap_data)

# Top features by mean SHAP value
top_features = feature_stats.nlargest(10, 'mean_shap')

# Visualize feature importance
plt.figure(figsize=(12, 8))
plt.barh(top_features['feature'], top_features['mean_shap'])
plt.xlabel('Mean SHAP Value')
plt.title('Top Risk Drivers - Ebola')
plt.gca().invert_yaxis()
plt.tight_layout()
plt.show()

# Feature frequency analysis
feature_freq = shap_data['feature'].value_counts()
plt.figure(figsize=(12, 6))
feature_freq.head(10).plot(kind='bar')
plt.xlabel('Feature')
plt.ylabel('Frequency in Top 3 Drivers')
plt.title('Feature Frequency in SHAP Explanations')
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()
```

### 5. Seasonal Analysis

```python
# Compare peak vs off-peak seasons
tile_id = "AF-025-10000"
pathogen = "cchfv"  # Climate-sensitive pathogen

# Get seasonal data
peak_data = client.get_tile_risk(tile_id, pathogen, "2026-06", season="peak")
offpeak_data = client.get_tile_risk(tile_id, pathogen, "2026-01", season="off-peak")

print("Seasonal Risk Comparison:")
print(f"Peak Season Risk: {peak_data['risk_score']:.3f}")
print(f"Off-Peak Season Risk: {offpeak_data['risk_score']:.3f}")
print(f"Seasonal Difference: {peak_data['risk_score'] - offpeak_data['risk_score']:.3f}")

# Compare top drivers
print("\nTop Drivers - Peak Season:")
for driver in peak_data['top_drivers']:
    print(f"  {driver['feature_name']}: {driver['shap_value']:.4f}")

print("\nTop Drivers - Off-Peak Season:")
for driver in offpeak_data['top_drivers']:
    print(f"  {driver['feature_name']}: {driver['shap_value']:.4f}")
```

### 6. Uncertainty Analysis

```python
# Analyze prediction uncertainty
uncertainty_data = []

for _, row in ebola_data.head(100).iterrows():
    tile_risk = client.get_tile_risk(row['tile_id'], "ebola", "2026-03")
    
    uncertainty_data.append({
        'tile_id': row['tile_id'],
        'risk_score': tile_risk['risk_score'],
        'p10': tile_risk['confidence']['p10'],
        'p90': tile_risk['confidence']['p90'],
        'uncertainty_width': tile_risk['confidence']['p90'] - tile_risk['confidence']['p10']
    })

uncertainty_df = pd.DataFrame(uncertainty_data)

# Visualize uncertainty
plt.figure(figsize=(12, 8))
plt.errorbar(
    range(len(uncertainty_df)),
    uncertainty_df['risk_score'],
    yerr=[
        uncertainty_df['risk_score'] - uncertainty_df['p10'],
        uncertainty_df['p90'] - uncertainty_df['risk_score']
    ],
    fmt='o',
    alpha=0.6
)
plt.xlabel('Tile Index')
plt.ylabel('Risk Score')
plt.title('Risk Predictions with Uncertainty Intervals')
plt.show()

# Uncertainty vs risk relationship
plt.figure(figsize=(10, 6))
plt.scatter(uncertainty_df['risk_score'], uncertainty_df['uncertainty_width'])
plt.xlabel('Risk Score')
plt.ylabel('Uncertainty Width (P90 - P10)')
plt.title('Risk vs Uncertainty Relationship')
plt.show()
```

## Advanced Analysis Examples

### Geospatial Analysis with GeoPandas

```python
import geopandas as gpd
from shapely.geometry import Point

# Convert to GeoDataFrame
geometry = [Point(lon, lat) for lon, lat in 
           zip(ebola_data['centroid_lon'], ebola_data['centroid_lat'])]
gdf = gpd.GeoDataFrame(ebola_data, geometry=geometry)

# Spatial analysis
# Buffer high-risk areas
high_risk_gdf = gdf[gdf['risk_score'] > 0.7]
buffered = high_risk_gdf.buffer(0.1)  # 0.1 degree buffer

# Spatial join with country boundaries (if available)
# countries = gpd.read_file('path/to/countries.shp')
# country_risk = gpd.sjoin(gdf, countries, how='left', op='within')
```

### Time Series Forecasting

```python
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error

# Prepare time series data
tile_id = "AF-025-10000"
ts_data = temporal_data[temporal_data['tile_id'] == tile_id].copy()
ts_data['month_num'] = pd.to_datetime(ts_data['month']).dt.month

# Simple linear trend model
X = ts_data[['month_num']].values
y = ts_data['risk_score'].values

model = LinearRegression()
model.fit(X, y)

# Forecast next 3 months
future_months = np.array([[7], [8], [9]])  # July, August, September
forecast = model.predict(future_months)

print("Risk Forecast:")
for i, month in enumerate(['2026-07', '2026-08', '2026-09']):
    print(f"{month}: {forecast[i]:.3f}")
```

### Statistical Testing

```python
from scipy import stats

# Compare risk distributions between regions
region1_data = ebola_data[ebola_data['centroid_lat'] > 10]['risk_score']
region2_data = ebola_data[ebola_data['centroid_lat'] <= 10]['risk_score']

# T-test for difference in means
t_stat, p_value = stats.ttest_ind(region1_data, region2_data)

print(f"T-test Results:")
print(f"T-statistic: {t_stat:.3f}")
print(f"P-value: {p_value:.3f}")
print(f"Significant difference: {'Yes' if p_value < 0.05 else 'No'}")

# Mann-Whitney U test (non-parametric)
u_stat, u_p_value = stats.mannwhitneyu(region1_data, region2_data)
print(f"\nMann-Whitney U Test:")
print(f"U-statistic: {u_stat:.3f}")
print(f"P-value: {u_p_value:.3f}")
```

## Data Export Examples

### Export to CSV

```python
# Export regional data
ebola_data.to_csv('ebola_risk_west_africa_2026_03.csv', index=False)

# Export SHAP explanations
shap_data.to_csv('ebola_shap_explanations_2026_03.csv', index=False)

# Export comparison data
comparison_data.to_csv('cross_pathogen_comparison_2026_03.csv', index=False)
```

### Export to GeoJSON

```python
# Convert to GeoJSON for GIS software
gdf.to_file('ebola_risk_west_africa.geojson', driver='GeoJSON')
```

### Export to NetCDF

```python
import xarray as xr

# Create gridded dataset
risk_grid = ebola_data.pivot_table(
    values='risk_score',
    index='centroid_lat',
    columns='centroid_lon'
)

# Convert to xarray Dataset
ds = xr.Dataset({
    'risk_score': (['lat', 'lon'], risk_grid.values)
}, coords={
    'lat': risk_grid.index,
    'lon': risk_grid.columns
})

# Add metadata
ds.attrs['title'] = 'Ebola Risk Predictions'
ds.attrs['source'] = 'AqtaBio Platform'
ds.attrs['date'] = '2026-03'

# Export to NetCDF
ds.to_netcdf('ebola_risk_2026_03.nc')
```

## Error Handling and Best Practices

### Robust API Calls

```python
import time
from requests.exceptions import RequestException

def robust_api_call(func, max_retries=3, delay=1):
    """Wrapper for robust API calls with retry logic."""
    for attempt in range(max_retries):
        try:
            return func()
        except RequestException as e:
            if attempt == max_retries - 1:
                raise e
            print(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
            time.sleep(delay)
            delay *= 2  # Exponential backoff

# Usage
def get_risk_data():
    return client.get_tile_risk("AF-025-10000", "ebola", "2026-03")

risk_data = robust_api_call(get_risk_data)
```

### Rate Limiting

```python
import time
from functools import wraps

def rate_limit(calls_per_second=10):
    """Decorator to rate limit function calls."""
    min_interval = 1.0 / calls_per_second
    last_called = [0.0]
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_called[0]
            left_to_wait = min_interval - elapsed
            if left_to_wait > 0:
                time.sleep(left_to_wait)
            ret = func(*args, **kwargs)
            last_called[0] = time.time()
            return ret
        return wrapper
    return decorator

# Apply rate limiting
@rate_limit(calls_per_second=5)
def get_tile_risk_limited(tile_id, pathogen, month):
    return client.get_tile_risk(tile_id, pathogen, month)
```

### Data Validation

```python
def validate_risk_data(risk_data):
    """Validate risk prediction data."""
    required_fields = ['risk_score', 'confidence', 'top_drivers']
    
    for field in required_fields:
        if field not in risk_data:
            raise ValueError(f"Missing required field: {field}")
    
    risk_score = risk_data['risk_score']
    if not (0 <= risk_score <= 1):
        raise ValueError(f"Invalid risk score: {risk_score}")
    
    confidence = risk_data['confidence']
    if confidence['p10'] > confidence['p90']:
        raise ValueError("Invalid confidence interval: p10 > p90")
    
    return True

# Usage
try:
    risk_data = client.get_tile_risk("AF-025-10000", "ebola", "2026-03")
    validate_risk_data(risk_data)
    print("Data validation passed")
except ValueError as e:
    print(f"Data validation failed: {e}")
```