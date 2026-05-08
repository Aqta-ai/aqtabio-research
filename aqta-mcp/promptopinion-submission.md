# AqtaBio MCP for Prompt Opinion

A SHARP-aware MCP server that gives a clinician's Prompt Opinion
workspace pre-etiologic zoonotic spillover risk for the area their
patient lives in, and writes the result back to the EHR as a FHIR R4
`RiskAssessment` resource. Live, public, no authentication.

- **MCP endpoint**: `https://qjtqgvpd9s.eu-west-1.awsapprunner.com/mcp`
- **A2A v1.0 agent card**: `https://qjtqgvpd9s.eu-west-1.awsapprunner.com/.well-known/agent.json`
- **Public source mirror**: <https://github.com/Aqta-ai/aqtabio-research>
- **Live HAPI write-back**: round-trip is verifiable end-to-end against
  `https://hapi.fhir.org/baseR4` from any browser

## Why Prompt Opinion specifically

Prompt Opinion ships a clinician workspace that consumes MCP servers
declaring the `ai.promptopinion/fhir-context` extension. AqtaBio is the
first **pre-etiologic zoonotic spillover** signal callable from that
workspace. The SHARP context block (`patient_id`, `encounter_id`,
`fhir_server`, `access_token`) is propagated end-to-end:

1. The clinician's EHR session credentials reach AqtaBio without
   bespoke token-handling.
2. AqtaBio reads the Patient resource from the EHR via SMART-on-FHIR.
3. **Only `address.country` is retained.** No identifier, name, DOB,
   condition, or encounter detail is stored or returned.
4. AqtaBio returns a population-level risk score for that area —
   never a per-patient diagnosis.
5. The result can be written back to the EHR as a FHIR R4
   `RiskAssessment` so the encounter has a durable, queryable
   surveillance signal attached to the patient record.

## Two SHARP-aware tools

Both declared in `capabilities.tools_using_sharp` on the agent card.

### `get_patient_local_risk`

Reads the Patient resource via the SHARP-propagated session, extracts
country, and returns the population-level spillover risk for that
country's seeded tile.

```bash
curl -X POST https://qjtqgvpd9s.eu-west-1.awsapprunner.com/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "get_patient_local_risk",
      "arguments": {
        "sharp_context": {
          "patient_id": "131502547",
          "fhir_server": "https://hapi.fhir.org/baseR4",
          "access_token": "none"
        },
        "pathogen": "ebola"
      }
    }
  }'
```

Response shape (verified live):

```json
{
  "sharp_propagated": true,
  "patient_country": "NG",
  "tile_id": "AF-025-10235",
  "pathogen": "ebola",
  "month": "2026-05",
  "population_risk_score": 0.0,
  "risk_tier": "baseline",
  "phi_minimisation": "Only address.country was retained from the FHIR Patient resource. No patient identifier, name, DOB, or condition is returned. Risk is population-level (25 km tile).",
  "summary_for_clinician": "Ebola Virus Disease spillover risk in this patient's home country (NG) for 2026-05: score 0.0. This is a population-level signal, not a per-patient diagnosis."
}
```

### `emit_riskassessment_to_ehr`

Writes a FHIR R4 `RiskAssessment` back to the same FHIR server, signed
to the patient via `subject.reference`. **Defaults to dry-run** so a
mis-configured SHARP context cannot accidentally write to a real
production EHR. Pass `confirm_write: true` to actually POST.

Dry-run (default — what a workspace gets without explicit confirmation):

```bash
curl -X POST https://qjtqgvpd9s.eu-west-1.awsapprunner.com/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "emit_riskassessment_to_ehr",
      "arguments": {
        "sharp_context": {
          "patient_id": "131502547",
          "fhir_server": "https://hapi.fhir.org/baseR4",
          "access_token": "none"
        },
        "pathogen": "ebola"
      }
    }
  }'
```

Returns `dry_run: true`, the resource that *would* be POSTed, and
`fhir_host_is_known_sandbox` so the workspace can decide whether to
prompt the clinician for confirmation. Add `"confirm_write": true` to
the arguments to actually write; the response then includes
`ehr_resource_url` for re-fetch.

## How a Prompt Opinion workspace consumes this

1. Discover the agent card at the well-known URI.
2. Read `capabilities.extensions` and confirm
   `ai.promptopinion/fhir-context` is declared.
3. When invoking a SHARP-aware tool, populate the `sharp_context`
   argument from the workspace's current SMART-on-FHIR session. The
   four expected keys (`patient_id`, `encounter_id`, `fhir_server`,
   `access_token`) are listed in `capabilities.sharp_context.fields_consumed`.
4. Render the `summary_for_clinician` string in the workspace.
5. For `emit_riskassessment_to_ehr`, treat the dry-run response as a
   confirmation prompt: show the `dry_run_resource` to the clinician,
   then re-call with `confirm_write: true` if approved.

## Why the design choices look the way they do

- **Country-coarse mapping** (not patient address). PHI minimisation
  is the constraint; the model is population-level anyway, so a
  finer geocode would be more leakage for no clinical gain.
- **Dry-run default on EHR write.** A live MCP that any workspace can
  call should never write PHI to an arbitrary FHIR host on a single
  RPC; the clinician's UI must be able to show the resource, ask, and
  re-call.
- **Sandbox allowlist** (`hapi.fhir.org`, `server.fire.ly`,
  `spark.incendi.no`, `fhir.smarthealthit.org`) — writes still succeed
  to non-sandbox hosts when `confirm_write: true`, but the response
  surfaces `wrote_to_non_sandbox_host: true` so the workspace can
  audit it. The bearer token from the SHARP block is forwarded
  verbatim and is never stored on the AqtaBio side.

## Verifying the round-trip yourself

After a write, fetch the resource back:

```bash
curl -H "Accept: application/fhir+json" \
  https://hapi.fhir.org/baseR4/RiskAssessment/<resource_id>
```

The same idempotency contract documented for `submit_to_hapi_fhir`
applies: repeat calls for the same `(pathogen, tile_id)` return the
existing resource id rather than creating a duplicate.

## Limits, said up front

- **No prospective deployment.** Validation is retrospective against
  the held-out 25-event historical cohort. Aggregate AUROC / AUCPR /
  lead-time across the full cohort is the deliverable of the
  forthcoming medRxiv preprint (target Q3 2026).
- **5 of 8 priority pathogens have seeded tile predictions.** Mpox,
  Nipah, and Hantavirus are trained but pending tile seeding; calls
  for those pathogens return `prediction_status: pending_tile_seeding`.
- **Country coverage is sparse** (578 production tiles, densest in
  sub-Saharan Africa, eastern Europe, Southeast Asia). Patients with
  countries outside that footprint get a clean error rather than a
  fabricated risk score.
- **EU AI Act conformity is not yet complete.** Roadmap and
  classification rationale (Annex III §5(a)) live at
  [`docs/regulatory/ce-marking-and-eu-ai-act.md`](https://github.com/Aqta-ai/aqtabio-research/blob/main/docs/regulatory/ce-marking-and-eu-ai-act.md).

## Citation

> Chueayen, A. (2026). *AqtaBio: pre-etiologic zoonotic spillover
> risk forecasting (v0.1.0).* Aqta Technologies Limited.
> Live MCP: <https://qjtqgvpd9s.eu-west-1.awsapprunner.com/mcp>.
> Source mirror: <https://github.com/Aqta-ai/aqtabio-research>.
