"""pointmap: normalize multi-vendor BAS point names into Project Haystack
tags and Brick Schema classes, with a human review queue for anything it
cannot map confidently.

The pipeline runs one module per stage, in this order:

    ingest    read the vendor export; normalize columns, object types, units
    tokens    split vendor paths, find the equipment, break the name into tokens
    classify  turn tokens + metadata into a point role with a confidence score
    qa        commissioning checks: required points, duplicates, anomalies
    export    CSV tables, Haystack JSON, Brick Turtle, QA report

pipeline.run() wires the stages together. Everything is deterministic: the
same input and rules always produce byte-identical output.
"""

__version__ = "0.1.0"
