# Benchmark data

Four synthetic sites, each written in a real vendor's naming conventions. No real building's data is included.

| File | Site | Style | Points |
|---|---|---|---:|
| `pine_paper_alc.csv` | PINE-PAPER | Automated Logic WebCTRL paths, metric units, long-form object types | 61 |
| `office_a_metasys.csv` | OFFICE-A | Johnson Controls Metasys item references, imperial units | 70 |
| `store_01_niagara.csv` | STORE-01 | Niagara slot paths, camelCase names, BACnet object ids | 56 |
| `legacy_mix_chaos.csv` | LEGACY-MIX | Hand-typed names from several eras, Latin-1 encoded | 56 |

The traps are deliberate. They include ambiguous abbreviations (`SP` as setpoint or static pressure), a fan status wired as an analog input reading amps, units that contradict names, missing units and object types, duplicates from stale controllers and merged exports, typos, points with no equipment, out-of-scope points (lighting, metering, domestic hot water) and junk (spares, tuning gains, alarms, diagnostics).

## Answer keys (`ground_truth/`)

One key per site, same file name as the export. Every label was written by hand from the design of the row, and the keys were frozen before the tool was first run on them.

| Column | Meaning |
|---|---|
| `point_name`, `device_instance` | Match key (the same name can exist on two controllers) |
| `expected_equip` | Canonical equipment id; blank for site-level points |
| `expected_point` | Canonical point, or `NONE` when the correct behaviour is to refuse |
| `expected_role` | Role id from `rules/point_roles.yaml` |
| `expected_canonical_name` | `expected_equip.expected_point` (site id for site-level points) |
| `expected_outcome` | `map` or `refuse` |
| `note` | Why, for anything non-obvious. Every refusal has one |

A key records what each point **is**. It deliberately does not record whether the tool should say `auto` or `flagged`: that is the tool's own confidence, and labelling it would grade the tool against its own output.
