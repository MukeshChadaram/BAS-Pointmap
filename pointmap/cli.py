"""Command-line interface.

    pointmap map EXPORT.csv --site SITE --out DIR [--rules DIR]
    pointmap evaluate TAGGED.csv ANSWER_KEY.csv [TAGGED.csv ANSWER_KEY.csv ...] [--markdown]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .evaluate import evaluate, per_site_markdown
from .export.brick import write_brick
from .export.haystack import write_haystack
from .export.report import write_report
from .export.tables import write_tables
from .ingest import IngestError
from .pipeline import run
from .rules import RuleError, load_rules


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pointmap",
        description="Map vendor BAS point names to Project Haystack tags and Brick classes.",
    )
    parser.add_argument("--version", action="version", version=f"pointmap {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    map_cmd = commands.add_parser("map", help="map one site's point export")
    map_cmd.add_argument("export", type=Path, help="vendor point export (CSV)")
    map_cmd.add_argument("--site", help="site id (optional if the CSV has a single-valued 'site' column)")
    map_cmd.add_argument("--out", type=Path, default=Path("output"), help="output directory (default: output/)")
    map_cmd.add_argument("--rules", type=Path, default=None, help="rules directory (default: repo rules/)")

    eval_cmd = commands.add_parser("evaluate", help="score runs against hand-labelled answer keys")
    eval_cmd.add_argument("pairs", type=Path, nargs="+", metavar="TAGGED TRUTH",
                          help="one or more pairs: tagged_points.csv from a map run, then its answer key")
    eval_cmd.add_argument("--markdown", action="store_true", help="print the results tables only")

    args = parser.parse_args(argv)
    try:
        return _map(args) if args.command == "map" else _evaluate(args)
    except (RuleError, IngestError, ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except BrokenPipeError:  # output piped into `head` etc.: not an error
        sys.stderr.close()
        return 0


def _map(args) -> int:
    rules = load_rules(args.rules)
    result = run(args.export, site=args.site, rules=rules)
    args.out.mkdir(parents=True, exist_ok=True)

    tagged, review = write_tables(result.results, args.out)
    written = [tagged, review,
               write_haystack(result.site, result.results, rules, args.out),
               write_brick(result.site, result.results, rules, args.out),
               write_report(result, args.out)]

    counts = result.qa.counts
    ready = sum(1 for e in result.qa.readiness if e.ready)
    print(f"{result.site}: {counts['total']} points | auto {counts['auto']} | "
          f"flagged {counts['flagged']} | review {counts['review']} | "
          f"equipment ready {ready}/{len(result.qa.readiness)}")
    for path in written:
        print(f"  wrote {path}")
    return 0


def _evaluate(args) -> int:
    if len(args.pairs) % 2:
        raise ValueError("evaluate takes pairs of files: TAGGED TRUTH [TAGGED TRUTH ...]")
    per_site = [evaluate(tagged, truth) for tagged, truth in zip(args.pairs[::2], args.pairs[1::2])]
    evaluation = per_site[0]
    for other in per_site[1:]:
        evaluation = evaluation + other
    print(evaluation.as_markdown())
    if len(per_site) > 1:
        print()
        print(per_site_markdown(per_site))
    if evaluation.unmatched and not args.markdown:
        print(f"\nwarning: {len(evaluation.unmatched)} tagged rows have no answer-key entry", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
