# Deployment readiness: OFFICE-A

Source `office_a_metasys.csv` · rules v1 · pointmap 0.1.0

## Summary

| Points | Auto-accepted | Flagged for spot-check | Review queue | Equipment ready |
|---:|---:|---:|---:|---:|
| 70 | 58 (83%) | 4 (6%) | 8 (11%) | 8 of 10 |

## Equipment readiness

Required points come from `rules/equipment_templates.yaml`. `A|B` means either point satisfies the requirement.

| Equipment | Type | Mapped | In review | Status | Missing required | Missing recommended |
|---|---|---:|---:|---|---|---|
| AHU-01 | air handling unit | 14 | 2 | READY | - | - |
| AHU-02 | air handling unit | 6 | 1 | READY | - | DA-T-SP, DA-P-SP, OA-DMPR-C |
| VAV-201 | VAV box | 5 | 1 | READY | - | DA-T, RHT-VLV-C, ZN-T-HTG-SP |
| VAV-202 | VAV box | 5 | 1 | READY | - | DA-T, RHT-VLV-C, ZN-T-HTG-SP |
| VAV-203 | VAV box | 6 | 0 | READY | - | RHT-VLV-C, ZN-T-HTG-SP |
| VAV-204 | VAV box | 5 | 0 | BLOCKED | DMPR-C | RHT-VLV-C, ZN-T-HTG-SP |
| VAV-205 | VAV box | 4 | 1 | BLOCKED | ZN-T-SP|ZN-T-CLG-SP | DA-T, RHT-VLV-C, ZN-T-HTG-SP |
| VAV-301 | VAV box | 5 | 1 | READY | - | DA-T, RHT-VLV-C, ZN-T-HTG-SP |
| VAV-302 | VAV box | 5 | 0 | READY | - | DA-T, RHT-VLV-C, ZN-T-HTG-SP |
| VAV-303 | VAV box | 5 | 0 | READY | - | DA-T, RHT-VLV-C, ZN-T-HTG-SP |

## Site-level points

- `OFFICE-A:NAE-01/OA-T` -> OFFICE-A.OA-T (auto)
- `OFFICE-A:NAE-01/OA-RH` -> OFFICE-A.OA-RH (auto)

## Anomalies

Metadata that doesn't add up. Each one is a question for the site, not a guess.

- `OFFICE-A:NAE-01/FC-1.AHU-1.SA-T`: DUPLICATE: AHU-01.DA-T is claimed by rows 1, 23
- `OFFICE-A:NAE-01/FC-1.AHU-2.MA-T`: UNITS_CONFLICT: % (percent) but MA-T expects temp
- `OFFICE-A:NAE-01/FC-1.AHU-2.SF-O`: TYPE_MISMATCH: AO is unusual for SF-C (expected BO/BV); UNITS_CONFLICT: % (percent) but SF-C expects an on/off state
- `OFFICE-A:NAE-02/FC-1.AHU-1.SA-T`: DUPLICATE: AHU-01.DA-T is claimed by rows 1, 23
- `OFFICE-A:NAE-01/FC-3.VMA-302.ZN-T`: UNITS_CONFLICT: % (percent) but ZN-T expects temp
- `OFFICE-A:NAE-01/FC-2.ZN-T`: NO_EQUIPMENT: point could not be attached to equipment

## Review queue by reason

| Reason | Points |
|---|---:|
| no matching point role | 5 |
| alarm point (not telemetry) | 1 |
| cannot attach to equipment | 1 |
| metadata disagrees with the name | 1 |

Point-level detail: `review_queue.csv`.
