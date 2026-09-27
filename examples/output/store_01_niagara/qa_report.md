# Deployment readiness: STORE-01

Source `store_01_niagara.csv` · rules v1 · pointmap 0.1.0

## Summary

| Points | Auto-accepted | Flagged for spot-check | Review queue | Equipment ready |
|---:|---:|---:|---:|---:|
| 56 | 45 (80%) | 7 (12%) | 4 (7%) | 5 of 5 |

## Equipment readiness

Required points come from `rules/equipment_templates.yaml`. `A|B` means either point satisfies the requirement.

| Equipment | Type | Mapped | In review | Status | Missing required | Missing recommended |
|---|---|---:|---:|---|---|---|
| RTU-01 | rooftop unit | 12 | 1 | READY | - | OA-DMPR-C |
| RTU-02 | rooftop unit | 12 | 1 | READY | - | OA-DMPR-C |
| RTU-03 | rooftop unit | 11 | 1 | READY | - | RA-CO2, OA-DMPR-C |
| RTU-04 | rooftop unit | 13 | 0 | READY | - | RA-CO2, OA-DMPR-C |
| EF-01 | exhaust fan | 2 | 0 | READY | - | - |

## Site-level points

- `/Drivers/BacnetNetwork/Weather/points/OutdoorTemp` -> STORE-01.OA-T (auto)
- `/Drivers/BacnetNetwork/Weather/points/OutdoorHumidity` -> STORE-01.OA-RH (auto)

## Anomalies

Metadata that doesn't add up. Each one is a question for the site, not a guess.

- `/Drivers/BacnetNetwork/RTU_1/points/EconDmprPos`: UNUSUAL_EQUIPMENT: DMPR-C on rtu RTU-01
- `/Drivers/BacnetNetwork/RTU_2/points/RAT`: UNITS_CONFLICT: % (percent) but RA-T expects temp
- `/Drivers/BacnetNetwork/RTU_2/points/EconDmprPos`: UNUSUAL_EQUIPMENT: DMPR-C on rtu RTU-02
- `/Drivers/BacnetNetwork/RTU_3/points/EconDmprPos`: UNUSUAL_EQUIPMENT: DMPR-C on rtu RTU-03
- `/Drivers/BacnetNetwork/RTU_4/points/DAT`: DUPLICATE: RTU-04.DA-T is claimed by rows 39, 51
- `/Drivers/BacnetNetwork/RTU_4/points/EconDmprPos`: UNUSUAL_EQUIPMENT: DMPR-C on rtu RTU-04
- `/Drivers/BacnetNetwork/RTU_4_old/points/DAT`: DUPLICATE: RTU-04.DA-T is claimed by rows 39, 51

## Review queue by reason

| Reason | Points |
|---|---:|
| no matching point role | 2 |
| communication diagnostic | 1 |
| no recognizable tokens (SPACETEMP) | 1 |

Point-level detail: `review_queue.csv`.

## Naming notes

Informational flags on accepted points (see the `flags` column in `tagged_points.csv`).

- UNKNOWN_TOKEN: 4
