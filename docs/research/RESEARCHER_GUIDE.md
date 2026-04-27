# AqtaBio Research Platform Guide

## Overview

AqtaBio is a machine learning platform for predicting zoonotic disease spillover risk across global landscapes. This guide provides researchers with comprehensive information on using the platform for scientific analysis.

## Quick Start for Researchers

### 1. Access the Platform

**Production URL**: https://aqtabio.org/
**API Base**: https://kfj3domgfgegnd7aqtfwpdj56y0evnyv.lambda-url.eu-west-1.on.aws

**Authentication**: Use judge access code `AQTA-SOLVE-2026` for research access.

### 2. Supported Pathogens

- **Ebola Virus Disease (EVD)** - Forest-edge spillover dynamics
- **H5N1 Avian Influenza** - Poultry-human transmission pathways  
- **Crimean-Congo Hemorrhagic Fever (CCHFV)** - Tick-borne climate-sensitive transmission

### 3. Geographic Coverage

- **Global**: 10km x 10km grid tiles
- **Focus Regions**: Sub-Saharan Africa, Southeast Asia, Eastern Europe
- **Total Coverage**: 45+ countries with high-resolution risk mapping

## Scientific Methodology

### Machine Learning Models

**Model Type**: XGBoost ensemble with pathogen-specific feature engineering
**Training Data**: Historical spillover events (2000-2024) from WHO, FAO, ECDC sources
**Validation**: Temporal cross-validation with 80/20 train-test split

### Feature Engineering

#### Core Environmental Features
- `biotic_transition_index`: Forest-agriculture interface intensity
- `lulc_diversity_shannon`: Land use diversity (Shannon entropy)
- `forest_loss_3yr`: Recent deforestation rate
- `temp_anomaly_12mo`: Temperature deviation from long-term mean
- `rainfall_anomaly_12mo`: Precipitation anomaly

#### Socioeconomic Features  
- `population_density_log`: Log-transformed human population density
- `livestock_density_pig_log`: Log-transformed pig density (H5N1 specific)
- `road_density`: Transportation network density
- `conflict_density_50km`: Armed conflict events within 50km

#### Spillover History
- `distance_to_past_spillover_log`: Distance to nearest historical spillover event

### Model Interpretability

**SHAP Explanations**: Each prediction includes pathogen-specific SHAP values explaining the top 3 risk drivers.

**Expected Patterns**:
- **Ebola**: Forest transition, population density, deforestation
- **H5N1**: Livestock density, temperature anomalies, transportation
- **CCHFV**: Climate variables, livestock exposure, seasonal patterns

## API Reference for Researchers

### Authentication

```bash
# Get access token
curl -X POST "https://kfj3domgfgegnd7aqtfwpdj56y0evnyv.lambda-url.eu-west-1.on.aws/auth/judge-token" \
  -H "Content-Type: application/json" \
  -d '{"code": "AQTA-SOLVE-2026"}'
```

### Core Endpoints

#### 1. Tile Risk Prediction

```bash
GET /tiles/{tile_id}/risk?pathogen={pathogen}&month={YYYY-MM}

# Example
curl -H "Authorization: Bearer $TOKEN" \
  "https://kfj3domgfgegnd7aqtfwpdj56y0evnyv.lambda-url.eu-west-1.on.aws/tiles/AF-025-10000/risk?pathogen=ebola&month=2026-03"
```

**Response**:
```json
{
  "tile_id": "AF-025-10000",
  "month": "2026-03", 
  "risk_score": 0.895,
  "confidence": {"p10": 0.823, "p90": 0.967},
  "top_drivers": [
    {"feature_name": "biotic_transition_index", "shap_value": 0.0318},
    {"feature_name": "forest_loss_3yr", "shap_value": 0.0298},
    {"feature_name": "population_density_log", "shap_value": 0.0226}
  ],
  "data_freshness": "2026-03-15T18:00:00Z",
  "governed": true,
  "model_version": "v1.0-ebola"
}
```

#### 2. Spatial Query

```bash
GET /tiles?bbox={min_lon,min_lat,max_lon,max_lat}&pathogen={pathogen}&month={YYYY-MM}&limit=100

# Example: West Africa region
curl -H "Authorization: Bearer $TOKEN" \
  "https://kfj3domgfgegnd7aqtfwpdj56y0evnyv.lambda-url.eu-west-1.on.aws/tiles?bbox=-15,4,5,15&pathogen=ebola&month=2026-03&limit=50"
```

#### 3. Seasonal Aggregation

```bash
GET /tiles/{tile_id}/risk?pathogen={pathogen}&month={YYYY-MM}&season={peak|off-peak}

# Example: Peak transmission season
curl -H "Authorization: Bearer $TOKEN" \
  "https://kfj3domgfgegnd7aqtfwpdj56y0evnyv.lambda-url.eu-west-1.on.aws/tiles/AF-025-10000/risk?pathogen=cchfv&month=2026-06&season=peak"
```

### Batch Processing

For large-scale analysis, use the spatial query endpoint with pagination:

```python
import requests
import pandas as pd

def get_regional_risk_data(bbox, pathogen, month, token):
    """Fetch risk data for a geographic region."""
    url = f"https://kfj3domgfgegnd7aqtfwpdj56y0evnyv.lambda-url.eu-west-1.on.aws/tiles"
    headers = {"Authorization": f"Bearer {token}"}
    
    all_tiles = []
    offset = 0
    limit = 100
    
    while True:
        params = {
            "bbox": bbox,
            "pathogen": pathogen, 
            "month": month,
            "limit": limit,
            "offset": offset
        }
        
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        
        if not data.get("tiles"):
            break
            
        all_tiles.extend(data["tiles"])
        offset += limit
        
        if len(data["tiles"]) < limit:
            break
    
    return pd.DataFrame(all_tiles)

# Example usage
token = "your_jwt_token"
west_africa_data = get_regional_risk_data(
    bbox="-15,4,5,15",
    pathogen="ebola", 
    month="2026-03",
    token=token
)
```

## Research Use Cases

### 1. Hotspot Identification

Identify high-risk areas for targeted surveillance:

```python
# Find top 10% risk tiles
high_risk_tiles = west_africa_data[
    west_africa_data['risk_score'] > west_africa_data['risk_score'].quantile(0.9)
]

# Cluster analysis
from sklearn.cluster import DBSCAN
coords = high_risk_tiles[['centroid_lat', 'centroid_lon']].values
clusters = DBSCAN(eps=0.5, min_samples=3).fit(coords)
```

### 2. Temporal Analysis

Track risk evolution over time:

```python
months = ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"]
temporal_data = []

for month in months:
    monthly_data = get_regional_risk_data(bbox, pathogen, month, token)
    monthly_data['month'] = month
    temporal_data.append(monthly_data)

time_series = pd.concat(temporal_data)
```

### 3. Cross-Pathogen Comparison

Compare risk patterns across pathogens:

```python
pathogens = ["ebola", "h5n1", "cchfv"]
comparison_data = {}

for pathogen in pathogens:
    comparison_data[pathogen] = get_regional_risk_data(
        bbox, pathogen, "2026-03", token
    )

# Correlation analysis
risk_matrix = pd.DataFrame({
    pathogen: data.set_index('tile_id')['risk_score'] 
    for pathogen, data in comparison_data.items()
})

correlation = risk_matrix.corr()
```

### 4. Feature Importance Analysis

Analyze SHAP explanations across regions:

```python
def extract_shap_data(tile_data, pathogen, token):
    """Extract SHAP explanations for detailed analysis."""
    shap_data = []
    
    for _, tile in tile_data.iterrows():
        response = requests.get(
            f"https://kfj3domgfgegnd7aqtfwpdj56y0evnyv.lambda-url.eu-west-1.on.aws/tiles/{tile['tile_id']}/risk",
            headers={"Authorization": f"Bearer {token}"},
            params={"pathogen": pathogen, "month": "2026-03"}
        )
        
        if response.status_code == 200:
            data = response.json()
            for driver in data['top_drivers']:
                shap_data.append({
                    'tile_id': tile['tile_id'],
                    'feature': driver['feature_name'],
                    'shap_value': driver['shap_value'],
                    'risk_score': data['risk_score']
                })
    
    return pd.DataFrame(shap_data)

# Feature importance by region
shap_df = extract_shap_data(west_africa_data, "ebola", token)
feature_importance = shap_df.groupby('feature')['shap_value'].agg(['mean', 'std', 'count'])
```

## Data Quality and Limitations

### Data Freshness
- **Satellite Data**: Updated monthly (30-day lag)
- **Climate Data**: Updated weekly (7-day lag)  
- **Socioeconomic Data**: Updated annually
- **Spillover Events**: Updated as reported (variable lag)

### Spatial Resolution
- **Grid Size**: 10km x 10km
- **Minimum Mapping Unit**: 100 km²
- **Coordinate System**: WGS84 (EPSG:4326)

### Model Limitations
- **Temporal Scope**: Trained on 2000-2024 data
- **Geographic Bias**: Higher accuracy in well-monitored regions
- **Pathogen Coverage**: Limited to three priority pathogens
- **Prediction Horizon**: Optimized for 1-6 month forecasts

### Uncertainty Quantification
- **Confidence Intervals**: P10-P90 range provided for each prediction
- **Model Ensemble**: Uncertainty from 100 bootstrap samples
- **Data Quality Flags**: Circuit breaker warnings for stale data (>90 days)

## Citation and Attribution

### Recommended Citation

```
AqtaBio Research Platform (2026). Machine Learning Platform for Zoonotic Disease 
Spillover Risk Prediction. Version 1.0. Available at: https://aqtabio.org/
```

### Data Sources

- **WHO Disease Outbreak News**: Historical spillover events
- **FAO EMPRES-i**: Animal disease surveillance  
- **ECDC Communicable Disease Threats Reports**: European surveillance
- **NASA MODIS**: Land cover and vegetation indices
- **ESA Climate Change Initiative**: Land cover classification
- **WorldPop**: Population density estimates
- **OpenStreetMap**: Transportation networks
- **ACLED**: Armed conflict location data

## Support and Contact

### Technical Support
- **Documentation**: https://github.com/Aqta-ai/aqta-bio/tree/main/docs
- **API Status**: Check `/health` endpoint
- **Rate Limits**: 1000 requests/hour per token

### Research Collaboration
For research partnerships and data access agreements, contact the AqtaBio research team.

### Reporting Issues
- **Bug Reports**: GitHub Issues
- **Data Quality Issues**: Include tile_id, pathogen, and timestamp
- **Feature Requests**: Research use case descriptions welcome

## Appendix

### Tile ID Format
- **Format**: `{REGION}-{GRID}-{INDEX}`
- **Example**: `AF-025-10000` (Africa, 25km grid, tile 10000)
- **Regions**: AF (Africa), AS (Asia), EU (Europe), NA (North America)

### Feature Definitions

| Feature | Unit | Range | Description |
|---------|------|-------|-------------|
| `biotic_transition_index` | Index | 0-1 | Forest-agriculture interface intensity |
| `forest_loss_3yr` | % | 0-100 | Forest cover loss over 3 years |
| `temp_anomaly_12mo` | °C | -10 to +10 | Temperature deviation from climatology |
| `population_density_log` | log(people/km²) | 0-10 | Log population density |
| `livestock_density_pig_log` | log(pigs/km²) | 0-8 | Log pig density |
| `road_density` | km/km² | 0-5 | Road network density |

### Error Codes

| Code | Description | Action |
|------|-------------|--------|
| 401 | Unauthorized | Check access token |
| 404 | Tile not found | Verify tile_id format |
| 422 | Invalid parameters | Check pathogen/month format |
| 429 | Rate limit exceeded | Reduce request frequency |
| 500 | Server error | Retry after delay |