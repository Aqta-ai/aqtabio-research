"""
Historical spillover event definitions for backtesting validation.

This module defines historical spillover events used to validate AqtaBio's
predictive capability. 26 events across multiple pathogens and regions,
with strong EU coverage.

Initial anchor events:
1. 2014 West Africa Ebola (Guinea)
2. 2018 DRC Ebola (North Kivu)
3. 2021 Mbandaka Ebola (DRC)
4. 2022 North Kivu Ebola (Beni, DRC)
5. 2022 H5N1 UK (Birmingham area)
6. 2019 Wuhan SARS-CoV-2 (China)

Expanded cross-pathogen events:
7. 2012 MERS-CoV (Saudi Arabia)
8. 2018 Nipah (Kerala, India)
9. 2020 Ebola (Equateur, DRC)
10. 2023 Marburg (Equatorial Guinea)
11. 2022 Lassa (Nigeria)
12. 2023 CCHFV (Iraq)
13. 2024 H5N1 (US dairy)
14. 2020 Rift Valley Fever (Kenya)
15. 2022 Mpox (global, Belgium index)

EU-focused events:
16. 2018 WNV Italy (record 610 cases)
17. 2018 WNV Greece (315 cases)
18. 2018 WNV Romania (277 cases)
19. 2010 WNV Greece (first major EU outbreak, 262 cases)
20. 2022 WNV Italy (new record 723 cases)
21. 2020 WNV Spain (first significant season, 77 cases)
22. 2016 CCHFV Spain (first autochthonous case in W. Europe)
23. 2018 CCHFV Turkey (1067 cases)
24. 2003 H5N1 Netherlands (89 human cases)
25. 2022 H5N1 France (21M birds culled)

EU_HISTORICAL_SPILLOVERS convenience list filters to EU-only events (13 total).
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class HistoricalSpillover:
    """
    A known historical spillover event used for backtesting validation.
    
    Attributes:
        event_id: Unique identifier for the event (e.g., "2014_west_africa_ebola")
        pathogen_id: Pathogen identifier (e.g., "ebola", "h5n1")
        location: Tuple of (latitude, longitude) coordinates
        tile_id: 25km grid tile identifier snapped to location
        spillover_date: Date of confirmed spillover event
        lookback_months: Number of months before spillover to analyze (default: 12)
        event_name: Human-readable event name for reporting
        location_name: Human-readable location name
        spillover_date_approximate: Whether the spillover date is approximate (default: False)
    """
    event_id: str
    pathogen_id: str
    location: tuple[float, float]
    tile_id: str
    spillover_date: date
    lookback_months: int = 12
    event_name: str = ""
    location_name: str = ""
    spillover_date_approximate: bool = False


@dataclass
class BacktestResult:
    """
    Result of backtesting a single historical spillover event.
    
    Attributes:
        event_id: Reference to the HistoricalSpillover event_id
        hit: Whether the event was predicted in top 5% risk tiles
        lead_time_months: Months of advance warning before spillover
        risk_score_at_event: Risk score at the spillover date
        risk_trajectory: List of (date, risk_score) tuples showing risk evolution
        top_drivers: Top 3 SHAP feature names driving the prediction
        max_percentile_reached: Highest risk percentile reached before spillover
        peak_risk_score: Maximum risk score achieved in lookback period
    """
    event_id: str
    hit: bool
    lead_time_months: Optional[float] = None
    risk_score_at_event: float = 0.0
    risk_trajectory: list[tuple[date, float]] = field(default_factory=list)
    top_drivers: list[str] = field(default_factory=list)
    max_percentile_reached: float = 0.0
    peak_risk_score: float = 0.0


# Historical spillover events for backtesting validation
HISTORICAL_SPILLOVERS = [
    HistoricalSpillover(
        event_id="2014_west_africa_ebola",
        pathogen_id="ebola",
        location=(8.4657, -13.2317),  # Guinea
        tile_id="AF-025-10234",
        spillover_date=date(2014, 3, 1),
        lookback_months=12,
        event_name="2014 West Africa Ebola",
        location_name="Guinea",
    ),
    HistoricalSpillover(
        event_id="2018_drc_ebola",
        pathogen_id="ebola",
        location=(1.2921, 27.7449),  # North Kivu, DRC
        tile_id="AF-025-15678",
        spillover_date=date(2018, 8, 1),
        lookback_months=12,
        event_name="2018 DRC Ebola",
        location_name="North Kivu, DRC",
    ),
    HistoricalSpillover(
        event_id="2021_mbandaka_ebola",
        pathogen_id="ebola",
        location=(0.0486, 18.2604),  # Mbandaka, DRC
        tile_id="AF-025-12345",
        spillover_date=date(2021, 6, 1),
        lookback_months=12,
        event_name="2021 Mbandaka Ebola",
        location_name="Mbandaka, DRC",
    ),
    HistoricalSpillover(
        event_id="2022_north_kivu_ebola",
        pathogen_id="ebola",
        location=(0.5149, 29.2378),  # Beni, North Kivu, DRC
        tile_id="AF-025-15680",
        spillover_date=date(2022, 4, 1),
        lookback_months=12,
        event_name="2022 North Kivu Ebola",
        location_name="Beni, North Kivu, DRC",
    ),
    HistoricalSpillover(
        event_id="2022_h5n1_uk",
        pathogen_id="h5n1",
        location=(52.5200, -1.9159),  # Birmingham area, UK
        tile_id="EU-025-20123",
        spillover_date=date(2022, 10, 1),
        lookback_months=12,
        event_name="2022 H5N1 UK",
        location_name="Birmingham area, UK",
    ),
    HistoricalSpillover(
        event_id="2019_wuhan_sars_cov_2",
        pathogen_id="sars-cov-2",
        location=(30.5928, 114.3055),  # Wuhan, Hubei, China
        tile_id="AS-025-45678",
        spillover_date=date(2019, 12, 8),
        lookback_months=12,
        event_name="2019 Wuhan SARS-CoV-2",
        location_name="Wuhan, Hubei, China",
    ),
    # --- Expanded events (Req 14.1, 14.2) ---
    HistoricalSpillover(
        event_id="2012_mers_cov_saudi",
        pathogen_id="mers-cov",
        location=(24.7136, 46.6753),  # Riyadh, Saudi Arabia
        tile_id="ME-025-30100",
        spillover_date=date(2012, 6, 13),
        lookback_months=12,
        event_name="2012 MERS-CoV Saudi Arabia",
        location_name="Riyadh, Saudi Arabia",
    ),
    HistoricalSpillover(
        event_id="2018_nipah_kerala",
        pathogen_id="nipah",
        location=(11.2588, 75.7804),  # Kozhikode, Kerala, India
        tile_id="AS-025-50200",
        spillover_date=date(2018, 5, 19),
        lookback_months=12,
        event_name="2018 Nipah Kerala",
        location_name="Kozhikode, Kerala, India",
    ),
    HistoricalSpillover(
        event_id="2020_ebola_equateur",
        pathogen_id="ebola",
        location=(0.0486, 18.2604),  # Equateur Province, DRC
        tile_id="AF-025-12350",
        spillover_date=date(2020, 6, 1),
        lookback_months=12,
        event_name="2020 Ebola Equateur DRC",
        location_name="Equateur Province, DRC",
    ),
    HistoricalSpillover(
        event_id="2023_marburg_equatorial_guinea",
        pathogen_id="marburg",
        location=(1.8500, 9.7500),  # Litoral Province, Equatorial Guinea
        tile_id="AF-025-18900",
        spillover_date=date(2023, 2, 13),
        lookback_months=12,
        event_name="2023 Marburg Equatorial Guinea",
        location_name="Litoral Province, Equatorial Guinea",
    ),
    HistoricalSpillover(
        event_id="2022_lassa_nigeria",
        pathogen_id="lassa",
        location=(7.2500, 5.2000),  # Ondo State, Nigeria
        tile_id="AF-025-22100",
        spillover_date=date(2022, 1, 23),
        lookback_months=12,
        event_name="2022 Lassa Nigeria",
        location_name="Ondo State, Nigeria",
    ),
    HistoricalSpillover(
        event_id="2023_cchfv_iraq",
        pathogen_id="cchfv",
        location=(33.3152, 44.3661),  # Baghdad, Iraq
        tile_id="ME-025-31500",
        spillover_date=date(2023, 3, 15),
        lookback_months=12,
        event_name="2023 CCHFV Iraq",
        location_name="Baghdad, Iraq",
    ),
    HistoricalSpillover(
        event_id="2024_h5n1_us_dairy",
        pathogen_id="h5n1",
        location=(32.7767, -96.7970),  # Texas, US
        tile_id="NA-025-60100",
        spillover_date=date(2024, 3, 25),
        lookback_months=12,
        event_name="2024 H5N1 US Dairy",
        location_name="Texas, United States",
    ),
    HistoricalSpillover(
        event_id="2020_rvf_kenya",
        pathogen_id="rift-valley-fever",
        location=(0.5143, 35.2698),  # Rift Valley, Kenya
        tile_id="AF-025-25300",
        spillover_date=date(2020, 6, 15),
        lookback_months=12,
        event_name="2020 Rift Valley Fever Kenya",
        location_name="Rift Valley Province, Kenya",
    ),
    HistoricalSpillover(
        event_id="2022_mpox_global",
        pathogen_id="mpox",
        location=(50.8503, 4.3517),  # Brussels, Belgium (index cluster)
        tile_id="EU-025-40200",
        spillover_date=date(2022, 5, 7),
        lookback_months=12,
        event_name="2022 Mpox Global Outbreak",
        location_name="Brussels, Belgium (index cluster)",
    ),
    # --- EU-focused events ---
    HistoricalSpillover(
        event_id="2018_wnv_italy",
        pathogen_id="wnv",
        location=(44.4949, 11.3426),  # Emilia-Romagna, Italy
        tile_id="EU-025-50100",
        spillover_date=date(2018, 7, 15),
        lookback_months=12,
        event_name="2018 WNV Italy (record 610 cases)",
        location_name="Emilia-Romagna / Veneto, Italy",
    ),
    HistoricalSpillover(
        event_id="2018_wnv_greece",
        pathogen_id="wnv",
        location=(40.6401, 22.9444),  # Central Macedonia, Greece
        tile_id="EU-025-50200",
        spillover_date=date(2018, 7, 1),
        lookback_months=12,
        event_name="2018 WNV Greece (315 cases)",
        location_name="Central Macedonia, Greece",
    ),
    HistoricalSpillover(
        event_id="2018_wnv_romania",
        pathogen_id="wnv",
        location=(44.4268, 26.1025),  # Bucharest, Romania
        tile_id="EU-025-50300",
        spillover_date=date(2018, 7, 15),
        lookback_months=12,
        event_name="2018 WNV Romania (277 cases)",
        location_name="Bucharest / Muntenia, Romania",
    ),
    HistoricalSpillover(
        event_id="2010_wnv_greece",
        pathogen_id="wnv",
        location=(38.2500, 21.7400),  # Central Macedonia, Greece
        tile_id="EU-025-50210",
        spillover_date=date(2010, 8, 1),
        lookback_months=12,
        event_name="2010 WNV Greece (first major EU outbreak, 262 cases)",
        location_name="Central Macedonia, Greece",
    ),
    HistoricalSpillover(
        event_id="2022_wnv_italy",
        pathogen_id="wnv",
        location=(44.4949, 11.3426),  # Emilia-Romagna, Italy
        tile_id="EU-025-50110",
        spillover_date=date(2022, 7, 1),
        lookback_months=12,
        event_name="2022 WNV Italy (new record 723 cases)",
        location_name="Emilia-Romagna / Veneto, Italy",
    ),
    HistoricalSpillover(
        event_id="2020_wnv_spain",
        pathogen_id="wnv",
        location=(37.3891, -5.9845),  # Seville, Andalusia
        tile_id="EU-025-50400",
        spillover_date=date(2020, 8, 1),
        lookback_months=12,
        event_name="2020 WNV Spain (first significant season, 77 cases)",
        location_name="Andalusia (Seville), Spain",
    ),
    HistoricalSpillover(
        event_id="2016_cchfv_spain",
        pathogen_id="cchfv",
        location=(40.6565, -4.6818),  # Ávila, Castilla y León
        tile_id="EU-025-60100",
        spillover_date=date(2016, 8, 25),
        lookback_months=12,
        event_name="2016 CCHFV Spain (first autochthonous case in W. Europe)",
        location_name="Ávila, Castilla y León, Spain",
    ),
    HistoricalSpillover(
        event_id="2018_cchfv_turkey",
        pathogen_id="cchfv",
        location=(40.1885, 36.4013),  # Tokat, Central Anatolia
        tile_id="EU-025-60200",
        spillover_date=date(2018, 5, 1),
        lookback_months=12,
        event_name="2018 CCHFV Turkey (1067 cases)",
        location_name="Tokat / Central Anatolia, Turkey",
    ),
    HistoricalSpillover(
        event_id="2003_h5n1_netherlands",
        pathogen_id="h5n1",
        location=(52.0907, 5.1214),  # Gelderland, Netherlands
        tile_id="EU-025-70100",
        spillover_date=date(2003, 3, 1),
        lookback_months=12,
        event_name="2003 H5N1 Netherlands (89 human cases, 1 fatal)",
        location_name="Gelderland, Netherlands",
    ),
    HistoricalSpillover(
        event_id="2022_h5n1_france",
        pathogen_id="h5n1",
        location=(43.4832, -1.0225),  # Landes, Nouvelle-Aquitaine
        tile_id="EU-025-70200",
        spillover_date=date(2022, 3, 1),
        lookback_months=12,
        event_name="2022 H5N1 France (21M birds culled)",
        location_name="Landes / Vendée, France",
    ),
]

# Convenience: EU-only events
EU_HISTORICAL_SPILLOVERS = [
    e for e in HISTORICAL_SPILLOVERS
    if e.tile_id.startswith("EU-")
]

# Americas spillover events for Task 4.3
AMERICAS_HISTORICAL_SPILLOVERS = [
    # Zika 2015 Brazil
    HistoricalSpillover(
        event_id="2015_zika_brazil",
        pathogen_id="zika",
        location=(-15.7801, -47.9292),  # Brasilia, Brazil
        tile_id="SA-025-10000",
        spillover_date=date(2015, 5, 1),
        lookback_months=12,
        event_name="2015 Zika Brazil",
        location_name="Brasilia, Brazil",
        spillover_date_approximate=True,
    ),
    # Yellow fever 2016 Angola→Brazil
    HistoricalSpillover(
        event_id="2016_yellow_fever_brazil",
        pathogen_id="yellow-fever",
        location=(-23.5505, -46.6333),  # São Paulo, Brazil
        tile_id="SA-025-20000",
        spillover_date=date(2016, 5, 1),
        lookback_months=12,
        event_name="2016 Yellow Fever Brazil",
        location_name="São Paulo, Brazil",
        spillover_date_approximate=True,
    ),
    # H5N1 2024 US dairy
    HistoricalSpillover(
        event_id="2024_h5n1_us_dairy",
        pathogen_id="h5n1",
        location=(32.7767, -96.7970),  # Texas, US
        tile_id="NA-025-60100",
        spillover_date=date(2024, 3, 25),
        lookback_months=12,
        event_name="2024 H5N1 US Dairy",
        location_name="Texas, United States",
    ),
    # Oropouche 2024 Peru
    HistoricalSpillover(
        event_id="2024_oropouche_peru",
        pathogen_id="oropouche",
        location=(-12.0464, -77.0428),  # Lima, Peru
        tile_id="SA-025-30000",
        spillover_date=date(2024, 4, 1),
        lookback_months=12,
        event_name="2024 Oropouche Peru",
        location_name="Lima, Peru",
        spillover_date_approximate=True,
    ),
    # Dengue 2023 Puerto Rico
    HistoricalSpillover(
        event_id="2023_dengue_puerto_rico",
        pathogen_id="dengue",
        location=(18.2208, -66.5901),  # San Juan, Puerto Rico
        tile_id="NA-025-70000",
        spillover_date=date(2023, 8, 1),
        lookback_months=12,
        event_name="2023 Dengue Puerto Rico",
        location_name="San Juan, Puerto Rico",
        spillover_date_approximate=True,
    ),
]
