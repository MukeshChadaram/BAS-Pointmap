# Deployment readiness: LEGACY-MIX

Source `legacy_mix_chaos.csv` · rules v1 · pointmap 0.1.0

## Summary

| Points | Auto-accepted | Flagged for spot-check | Review queue | Equipment ready |
|---:|---:|---:|---:|---:|
| 56 | 34 (61%) | 10 (18%) | 12 (21%) | 8 of 11 |

## Equipment readiness

Required points come from `rules/equipment_templates.yaml`. `A|B` means either point satisfies the requirement.

| Equipment | Type | Mapped | In review | Status | Missing required | Missing recommended |
|---|---|---:|---:|---|---|---|
| RTU-01 | rooftop unit | 9 | 2 | READY | - | RA-CO2, OA-DMPR-C |
| AHU-01 | air handling unit | 8 | 2 | BLOCKED | DA-P | DA-T-SP, DA-P-SP |
| VAV-2-01 | VAV box | 4 | 0 | READY | - | AIRFLOW-SP, DA-T, RHT-VLV-C, ZN-T-HTG-SP |
| VAV-2-02 | VAV box | 5 | 0 | READY | - | AIRFLOW-SP, DA-T, ZN-T-HTG-SP |
| VAV-2-03 | VAV box | 4 | 0 | READY | - | AIRFLOW-SP, DA-T, RHT-VLV-C, ZN-T-HTG-SP |
| VAV-2-04 | VAV box | 4 | 0 | READY | - | AIRFLOW-SP, DA-T, RHT-VLV-C, ZN-T-HTG-SP |
| EF-02 | exhaust fan | 2 | 0 | READY | - | - |
| UH-03 | unit heater | 2 | 1 | BLOCKED | HTG-STG-C | SF-S, ZN-T-SP |
| BB-01 | baseboard heater | 2 | 0 | READY | - | OCC-S |
| VH-01 | vestibule heater | 0 | 1 | BLOCKED | ZN-T | ZN-T-SP |
| FCU-01 | fan coil unit | 2 | 1 | READY | - | SF-S, DA-T, HTG-VLV-C, ZN-T-SP |

## Site-level points

- `OAT` -> LEGACY-MIX.OA-T (auto)
- `OA HUMIDITY` -> LEGACY-MIX.OA-RH (auto)

## Anomalies

Metadata that doesn't add up. Each one is a question for the site, not a guess.

- `Rtu #1 Disch Air Tmp`: DUPLICATE: RTU-01.DA-T is claimed by rows 1, 2, 10
- `RTU1-DAT`: DUPLICATE: RTU-01.DA-T is claimed by rows 1, 2, 10
- `RTU1 DAT HI LIMIT`: DUPLICATE: RTU-01.DA-T is claimed by rows 1, 2, 10
- `AHU1 MAT`: DUPLICATE: AHU-01.MA-T is claimed by rows 13, 14; DUPLICATE: AHU-01.MA-T is claimed by rows 13, 14
- `ROOM 214 TEMP`: NO_EQUIPMENT: point could not be attached to equipment
- `MAIN KW`: UNITS_UNKNOWN: units 'kW' not recognized

## Review queue by reason

| Reason | Points |
|---|---:|
| no matching point role | 5 |
| alarm point (not telemetry) | 1 |
| cannot attach to equipment | 1 |
| loop tuning parameter | 1 |
| low confidence | 1 |
| no recognizable tokens (LIGHTING, RELAY) | 1 |
| no recognizable tokens (MAIN, KW) | 1 |
| spare / unused I/O | 1 |

Point-level detail: `review_queue.csv`.

## Naming notes

Informational flags on accepted points (see the `flags` column in `tagged_points.csv`).

- FUZZY: 1
- INDEXED: 1
- UNKNOWN_TOKEN: 1
