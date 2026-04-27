"""
FHIR Resource Mappers for AqtaBio MCP Server
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Maps AqtaBio API responses to HL7 FHIR R4 resources:
  - RiskAssessment  — per-tile spillover risk prediction
  - DetectedIssue   — hotspot alert (tiles exceeding threshold)
  - Observation      — time-series risk trend data
"""

from __future__ import annotations

from datetime import datetime


def _fhir_id(raw: str) -> str:
    """
    Coerce an arbitrary identifier into a valid FHIR `id`.

    FHIR R4 spec: https://hl7.org/fhir/R4/datatypes.html#id
      - Only `[A-Za-z0-9-.]` allowed
      - Length 1-64
      - No underscores (Atlas tile IDs like `AT_sahel_12_5` fail validation)

    Replaces any non-compliant character with `-`, collapses repeated dashes,
    and truncates to 64 chars. Preserves the original tile identifier in
    `subject.identifier.value` so the human-meaningful ID is not lost.
    """
    import re
    cleaned = re.sub(r"[^A-Za-z0-9.-]", "-", raw)
    cleaned = re.sub(r"-+", "-", cleaned).strip("-.")
    return cleaned[:64] or "unknown"


def to_fhir_risk_assessment(
    tile_id: str,
    pathogen: str,
    pathogen_info: dict,
    api_data: dict,
) -> dict:
    """Convert a tile risk score response to a FHIR RiskAssessment resource."""
    risk = api_data.get("risk_score", 0)
    if risk >= 0.9:
        qual = "high"
    elif risk >= 0.7:
        qual = "moderate"
    elif risk >= 0.5:
        qual = "low"
    else:
        qual = "negligible"

    drivers = api_data.get("top_drivers", [])
    basis = [
        {"display": d.get("feature_name", "unknown"), "type": "Observation"}
        for d in (drivers if isinstance(drivers, list) else [])
    ]

    return {
        "resourceType": "RiskAssessment",
        "id": _fhir_id(f"{pathogen}-risk-{tile_id}"),
        "status": "final",
        "subject": {
            "display": tile_id,
            "identifier": {
                "system": "https://aqtabio.org/tiles",
                "value": tile_id,
            },
        },
        "occurrenceDateTime": api_data.get("month", datetime.utcnow().strftime("%Y-%m")),
        "method": {
            "coding": [
                {
                    "system": "https://aqtabio.org/models",
                    "code": "xgboost-shap-v0.1.0",
                    "display": "XGBoost + SHAP Ensemble",
                }
            ]
        },
        "prediction": [
            {
                "outcome": {
                    "coding": [
                        {
                            "system": "http://snomed.info/sct",
                            "code": pathogen_info.get("snomed", ""),
                            "display": pathogen_info.get("display", pathogen),
                        }
                    ]
                },
                "probabilityDecimal": round(risk, 3),
                "qualitativeRisk": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/risk-probability",
                            "code": qual,
                        }
                    ]
                },
            }
        ],
        "basis": basis,
        "note": [
            {
                "text": (
                    f"AqtaBio pre-etiologic spillover risk for {pathogen_info.get('display', pathogen)} "
                    f"at tile {tile_id}. Confidence interval: "
                    f"[{api_data.get('p10', '?')}, {api_data.get('p90', '?')}]."
                )
            }
        ],
    }


def to_fhir_detected_issue(
    pathogen: str,
    pathogen_info: dict,
    api_data: dict,
) -> dict:
    """Convert a hotspot count response to a FHIR DetectedIssue resource."""
    total = api_data.get("total_hotspots", 0)
    critical = api_data.get("critical", 0)
    high = api_data.get("high", 0)
    moderate = api_data.get("moderate", 0)
    month = api_data.get("month", datetime.utcnow().strftime("%Y-%m"))

    if critical > 0:
        severity = "high"
    elif high > 0:
        severity = "moderate"
    elif moderate > 0:
        severity = "low"
    else:
        severity = "low"

    return {
        "resourceType": "DetectedIssue",
        "id": _fhir_id(f"hotspot-{pathogen}-{month}"),
        "status": "final",
        "code": {
            "coding": [
                {
                    "system": "https://aqtabio.org/alerts",
                    "code": "spillover-hotspot",
                    "display": "Zoonotic Spillover Hotspot",
                }
            ]
        },
        "severity": severity,
        "identifiedDateTime": f"{month}-01T00:00:00Z",
        "detail": (
            f"{total} tiles exceed risk threshold for "
            f"{pathogen_info.get('display', pathogen)} "
            f"({critical} critical, {high} high, {moderate} moderate) "
            f"in {pathogen_info.get('region', 'monitored region')}."
        ),
        "extension": [
            {
                "url": "https://aqtabio.org/fhir/ext/hotspot-breakdown",
                "extension": [
                    {"url": "critical", "valueInteger": critical},
                    {"url": "high", "valueInteger": high},
                    {"url": "moderate", "valueInteger": moderate},
                    {"url": "total", "valueInteger": total},
                ],
            }
        ],
    }


def to_fhir_observation_series(
    tile_id: str,
    pathogen: str,
    pathogen_info: dict,
    trend_data: list | dict,
) -> dict:
    """Convert a trend response to a Bundle of FHIR Observation resources."""
    entries = trend_data if isinstance(trend_data, list) else []

    observations = []
    for entry in entries:
        month = entry.get("month", "")
        risk = entry.get("risk_score", 0)
        drivers = entry.get("top_drivers", [])

        components = []
        for d in (drivers if isinstance(drivers, list) else []):
            components.append(
                {
                    "code": {"text": d.get("feature_name", "unknown")},
                    "valueQuantity": {
                        "value": round(d.get("shap_value", 0), 4),
                        "unit": "shap",
                    },
                }
            )

        # FHIR R4 rejects `component: null` — the field must be absent, not null.
        # Build the dict conditionally so we never serialise a null array.
        obs: dict = {
            "resourceType": "Observation",
            "id": _fhir_id(f"risk-trend-{pathogen}-{tile_id}-{month}"),
            "status": "final",
            "code": {
                "coding": [
                    {
                        "system": "https://aqtabio.org/metrics",
                        "code": "spillover-risk-score",
                        "display": f"{pathogen_info.get('display', pathogen)} Spillover Risk",
                    }
                ]
            },
            "subject": {
                "identifier": {
                    "system": "https://aqtabio.org/tiles",
                    "value": tile_id,
                }
            },
            "effectiveDateTime": f"{month}-01" if len(month) == 7 else month,
            "valueQuantity": {
                "value": round(risk, 3),
                "unit": "probability",
                "system": "http://unitsofmeasure.org",
                "code": "1",
            },
        }
        if components:
            obs["component"] = components
        observations.append(obs)

    return {
        "resourceType": "Bundle",
        "type": "collection",
        "total": len(observations),
        "entry": [{"resource": obs} for obs in observations],
    }
