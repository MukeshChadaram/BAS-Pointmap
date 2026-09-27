# Runbook: onboarding a site's point list

The procedure for taking one building from raw point export to a signed-off, deployment-ready model. The tool does the first pass; this document covers the parts that need a person.

## 1. Collect the export

Get the point list from the front end or from a BACnet discovery: WebCTRL point list, Metasys point export, Niagara station export, or a discovery tool's CSV. One file per site.

The tool needs a point name column. It works far better with the BACnet object type, units and description, because those are the evidence that confirms or contradicts the name. Device instance is needed whenever the same point name exists on more than one controller. If the export lacks object types or units, ask for a better export before mapping: a name-only list will route most points to *flagged* or *review*, by design.

Record where the export came from and when. Point lists drift, and every question you send the site later will reference this version.

## 2. Run the mapping

```bash
pointmap map exports/<site>.csv --site <SITE-ID> --out runs/<site>
```

The console line gives the headline: points, auto, flagged, review, and how many pieces of equipment are ready. Output is deterministic, so re-running on the same export and rules produces identical files.

## 3. Read `qa_report.md` first

Start with **Equipment readiness**. A BLOCKED unit is missing a point the platform needs to run it. For each one, decide whether the point is genuinely absent (the site must add it, or the unit is excluded from scope) or present but not mapped (it is sitting in the review queue; step 4 resolves it).

Then read **Anomalies**. Each is a question for the site rather than something to fix by guessing. The recurring ones:

| Anomaly | Usual cause | What to ask |
|---|---|---|
| `STATUS_ON_ANALOG` | Fan status is a current transducer on an analog input | What is the proof threshold, and is there a binary status anywhere? |
| `UNITS_CONFLICT` | Units set wrong in programming, or the name is wrong | Which one is right? Check the live value |
| `TYPE_MISMATCH` | Point exposed as a value object instead of I/O, or mislabeled | Is this the physical point or a software copy? |
| `DUPLICATE` | Two controllers carry the same point, or a copy/paste naming error | Which one is live? |
| `NO_EQUIPMENT` | Name carries no equipment reference | Which unit does this belong to? (device list or drawings) |

## 4. Work the review queue

`review_queue.csv` holds every point the tool would not trust, each with a best guess, a confidence and a reason. Every row gets exactly one disposition:

| Disposition | When | Action |
|---|---|---|
| **Add a rule** | The name follows a convention the rules don't know yet | Add the token, role or alias to `rules/`, then re-run. Fixes every future site with the same convention. |
| **Fix at source** | The export is wrong (units, object type) | Raise it with the site. Map after correction. |
| **Map manually** | A true one-off that would not generalise into a rule | Record the mapping and the reason. |
| **Exclude** | Spare, test, tuning or diagnostic point | Record as excluded. No action. |

Prefer *add a rule* whenever the pattern will recur. It is the only disposition that makes the next site faster.

## 5. Spot-check flagged points

Flagged points are in the model but carry a flag worth a second look: a fuzzy-matched typo, a numbered sensor, an ambiguity that was close. Check each against live data. A discharge air temperature should read like one, and a zone setpoint should sit in a plausible band.

Never command an output on a live system to verify a mapping without the site's authorisation and an agreed test window.

## 6. Re-run and compare

After rule changes or a corrected export, run again into a fresh directory and diff against the previous run. Because output is deterministic, the diff contains exactly the points whose mapping changed. If a rule change moves points you didn't intend to move, the rule is too broad.

Before committing a rule change, run the benchmark as a regression check:

```bash
pointmap evaluate runs/<site>/tagged_points.csv data/ground_truth/<site>.csv
```

Silent errors (auto-accepted and wrong) must not increase.

## 7. Sign-off criteria

A site is ready to hand over when every piece of equipment in scope is READY or has a documented exception; every anomaly has an answer from the site or a documented decision; the review queue is empty, with every row dispositioned; and every flagged point has been spot-checked. Commit the final export, the rules version and the outputs together, so the model can be reproduced exactly later.
