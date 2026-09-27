# Deployment readiness: PINE-PAPER

Source `pine_paper_alc.csv` · rules v1 · pointmap 0.1.0

## Summary

| Points | Auto-accepted | Flagged for spot-check | Review queue | Equipment ready |
|---:|---:|---:|---:|---:|
| 61 | 54 (89%) | 2 (3%) | 5 (8%) | 5 of 6 |

## Equipment readiness

Required points come from `rules/equipment_templates.yaml`. `A|B` means either point satisfies the requirement.

| Equipment | Type | Mapped | In review | Status | Missing required | Missing recommended |
|---|---|---:|---:|---|---|---|
| RTU-01 | rooftop unit | 13 | 1 | BLOCKED | SF-S | - |
| RTU-02 | rooftop unit | 15 | 2 | READY | - | - |
| RTU-03 | rooftop unit | 15 | 0 | READY | - | - |
| UH-01 | unit heater | 4 | 0 | READY | - | SF-S |
| UH-02 | unit heater | 5 | 0 | READY | - | - |
| EF-01 | exhaust fan | 2 | 0 | READY | - | - |

## Site-level points

- `#pine_paper/site/oa_temp` -> PINE-PAPER.OA-T (auto)
- `#pine_paper/site/oa_humidity` -> PINE-PAPER.OA-RH (auto)

## Anomalies

Metadata that doesn't add up. Each one is a question for the site, not a guess.

- `#pine_paper/rtu_1/sf_status`: TYPE_MISMATCH: AI is unusual for SF-S (expected BI/BV); UNITS_CONFLICT: A (current) but SF-S expects an on/off state; STATUS_ON_ANALOG: SF-S arrives as AI in A; check how proof is wired
- `#pine_paper/rtu_3/ra_temp`: DESC_DISAGREES: description suggests position=mixed

## Review queue by reason

| Reason | Points |
|---|---:|
| alarm point (not telemetry) | 1 |
| no matching point role | 1 |
| no recognizable tokens (DOCK, DOOR) | 1 |
| status wired as analog input | 1 |
| test point | 1 |

Point-level detail: `review_queue.csv`.
