"""Stage 3: turn a parsed name plus BACnet metadata into a point role.

The principle: a wrong mapping made with confidence is worse than an unmapped
point, because a mislabeled point feeds bad data straight into a control
decision. So this stage maps what the evidence proves, explains every
decision, and refuses the rest.

How one point is classified (this order is the walk-through):

  1. Refuse non-telemetry outright: SPARE, TEST, PID gains, alarms -> review.
  2. Look up every token in abbreviations.yaml. An unknown token gets one
     fuzzy-match attempt (stdlib difflib); if that fails it counts as noise.
  3. Ambiguous tokens (SP, SPT, OUT, RUN) fork into competing hypotheses.
  4. Each hypothesis merges its tokens' meanings into one set of dimensions.
     A hypothesis whose tokens contradict each other is dropped.
  5. Equipment context fills gaps the name leaves open: a bare "fan" on an RTU
     is the supply fan; "SS" on an exhaust fan starts that fan.
  6. Every hypothesis is tested against every role in point_roles.yaml.
     A missing dimension may come from a naming convention (full credit) or be
     inferred from metadata (object type -> function, units -> quantity), but a
     name that needed metadata to be complete starts from a lower score.
  7. Metadata then confirms or contradicts the candidate: object type, units,
     description. Penalties apply for noise, missing equipment, odd equipment.
  8. The highest score wins. If a *different* role scored within MARGIN, the
     result is marked ambiguous and penalised. Nothing is picked silently.
  9. The final score sets the status: auto >= 0.80, flagged >= 0.50, else review.
     Two hard limits apply on top: auto requires every word of the name to be
     understood (no unknown or fuzzy-matched tokens), and a point that can't be
     attached to equipment always goes to review.
"""

from __future__ import annotations

import difflib
import itertools
from dataclasses import dataclass, field

from .models import AUTO, FLAGGED, REVIEW, ParsedName, PointRecord, PointResult
from .rules import Role, RuleSet
from .tokens import tokenize_text

# ---------------------------------------------------------------------------
# Scoring weights. Kept together so they can be read, argued about and tuned
# in one place. A clean name confirmed by object type and units scores 1.00.
# ---------------------------------------------------------------------------
BASE_COMPLETE_NAME = 0.60       # the name alone (plus equipment context) defines the role
BASE_NEEDS_METADATA = 0.45      # a dimension had to be inferred from object type / units
AMBIGUOUS_TOKEN = -0.05         # an ambiguous token (SP, SPT...) was resolved by evidence
TYPE_AGREES = 0.20
TYPE_CONTRADICTS = -0.25
UNITS_AGREE = 0.20
UNITS_CONTRADICT = -0.30        # units contradicting the quantity is the strongest warning
DESCRIPTION_AGREES = 0.05
DESCRIPTION_CONTRADICTS = -0.10
UNEXPLAINED_MEANING = -0.10     # per dimension the name carries that the role doesn't use
UNKNOWN_TOKEN = -0.10           # per unrecognized token...
UNKNOWN_TOKEN_CAP = -0.30       # ...up to this much in total
FUZZY_TOKEN = -0.10             # per token recovered by fuzzy matching (can only lower confidence)
UNUSUAL_EQUIPMENT = -0.15       # role doesn't normally live on this equipment type
NO_EQUIPMENT = -0.20            # no equipment in the name and the role isn't site-level
AMBIGUOUS_RESULT = -0.15        # a different role scored within MARGIN of the winner
MARGIN = 0.10

AUTO_THRESHOLD = 0.80
REVIEW_THRESHOLD = 0.50

FUZZY_CUTOFF = 0.82             # difflib similarity needed to accept a typo correction
MAX_HYPOTHESES = 16             # guard against combinatorial blow-up on pathological names


# ---------------------------------------------------------------------------
# Working objects (internal to this stage)
# ---------------------------------------------------------------------------
@dataclass
class TokenReading:
    token: str
    alternatives: list        # list of dimension dicts; more than one = ambiguous
    fuzzy_from: str | None = None

    @property
    def label(self) -> str:
        return f"{self.token}~{self.fuzzy_from}" if self.fuzzy_from else self.token


@dataclass
class Hypothesis:
    dims: dict
    choices: list = field(default_factory=list)   # "SP→quantity=pressure" for each ambiguous token
    notes: list = field(default_factory=list)     # where context-filled dimensions came from


@dataclass
class Candidate:
    role: Role
    hypothesis: Hypothesis
    dims: dict                                    # final dimensions, including inferred ones
    breakdown: list = field(default_factory=list) # (reason, delta) pairs that sum to the score
    inferred: list = field(default_factory=list)
    flags: list = field(default_factory=list)

    @property
    def score(self) -> float:
        return round(max(0.0, min(1.0, sum(delta for _, delta in self.breakdown))), 2)


@dataclass
class Context:
    """Everything about the point that isn't the hypothesis being tested."""

    record: PointRecord
    parsed: ParsedName
    rules: RuleSet
    unknown: list
    fuzzy: list
    description_dims: dict

    @property
    def units_family(self) -> str | None:
        # The units column wins; a unit written inside the name is the fallback.
        return self.record.units_family or self.parsed.name_unit_family

    @property
    def units_label(self) -> str | None:
        return self.record.units or self.parsed.name_unit


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def classify_point(site: str, record: PointRecord, parsed: ParsedName, rules: RuleSet) -> PointResult:
    evidence: list[str] = []
    base_flags = list(record.ingest_flags)
    equipment = parsed.equipment
    if equipment:
        evidence.append(f"equipment: '{equipment.raw}' -> {equipment.type} {equipment.ref}")

    # Step 1: nothing left to classify, or clearly not telemetry.
    if not parsed.tokens:
        return _refuse(site, record, parsed, evidence, base_flags, "no point tokens left after removing the equipment")
    junk = next((t for t in parsed.tokens if t in rules.non_telemetry), None)
    if junk:
        evidence.append(f"token {junk} marks non-telemetry")
        return _refuse(site, record, parsed, evidence, base_flags, rules.non_telemetry[junk])

    # Step 2: read every token.
    readings, unknown, fuzzy = _read_tokens(parsed.tokens, rules)
    evidence.append("tokens: " + " · ".join(_describe_reading(r) for r in readings)
                    + (f" · unknown: {', '.join(unknown)}" if unknown else ""))
    if not readings:
        return _refuse(site, record, parsed, evidence, base_flags,
                       f"no recognizable tokens ({', '.join(unknown)})")

    # Steps 3-4: fork on ambiguous tokens, drop self-contradicting hypotheses.
    hypotheses, contradictions = _expand(readings)
    if not hypotheses:
        return _refuse(site, record, parsed, evidence, base_flags,
                       "name contradicts itself: " + "; ".join(contradictions))

    # Step 5: equipment context.
    for hypothesis in hypotheses:
        _apply_equipment_context(hypothesis, parsed, rules)

    # Steps 6-7: test every hypothesis against every role.
    ctx = Context(record, parsed, rules, unknown, fuzzy, _description_dims(record, rules))
    candidates = [
        candidate
        for hypothesis in hypotheses
        for role in rules.roles
        if (candidate := _evaluate(role, hypothesis, ctx)) is not None
    ]
    if not candidates:
        seen = " | ".join(_fmt_dims(h.dims) for h in hypotheses)
        return _refuse(site, record, parsed, evidence, base_flags,
                       f"no point role matches: {seen}")

    # Step 8: pick the winner deterministically (score, then YAML order).
    candidates.sort(key=lambda c: (-c.score, c.role.order))
    best = candidates[0]
    runner_up = next((c for c in candidates[1:] if c.role.id != best.role.id), None)
    if runner_up and round(best.score - runner_up.score, 2) < MARGIN:
        best.breakdown.append((f"ambiguous: {runner_up.role.id} scored {runner_up.score:.2f}", AMBIGUOUS_RESULT))
        best.flags.append(f"AMBIGUOUS: {best.role.id} vs {runner_up.role.id}")

    return _build_result(site, record, parsed, best, runner_up, evidence, base_flags)


# ---------------------------------------------------------------------------
# Step 2: token reading
# ---------------------------------------------------------------------------
def _read_tokens(tokens: list[str], rules: RuleSet):
    readings, unknown, fuzzy = [], [], []
    for token in tokens:
        if token in rules.tokens:
            readings.append(TokenReading(token, rules.tokens[token]))
            continue
        # One typo-recovery attempt, only for tokens long enough to be words.
        close = (difflib.get_close_matches(token, rules.fuzzy_vocabulary, n=1, cutoff=FUZZY_CUTOFF)
                 if len(token) >= 4 else [])
        if close:
            readings.append(TokenReading(token, rules.tokens[close[0]], fuzzy_from=close[0]))
            fuzzy.append(f"{token}~{close[0]}")
        else:
            unknown.append(token)
    return readings, unknown, fuzzy


# ---------------------------------------------------------------------------
# Steps 3-4: hypotheses
# ---------------------------------------------------------------------------
def _expand(readings: list[TokenReading]):
    """One hypothesis per combination of ambiguous-token alternatives.

    Readings where an ambiguous token contributes nothing new are dropped when
    a fuller reading exists: in "SA-SP-SP" the two SPs must mean one static
    pressure and one setpoint, not the same thing twice.
    """
    hypotheses, contradictions = [], []
    combos = itertools.product(*[r.alternatives for r in readings])
    for combo in itertools.islice(combos, MAX_HYPOTHESES):
        dims, choices, conflict, wasted = {}, [], None, 0
        for reading, meaning in zip(readings, combo):
            if len(reading.alternatives) > 1:
                choices.append(f"{reading.label}→{_fmt_dims(meaning)}")
                # An ambiguous token read in a way that adds nothing new is a
                # wasted reading ("SA-SP-SP" read as pressure + pressure).
                if all(dims.get(d) == v for d, v in meaning.items()):
                    wasted += 1
            for dim, value in meaning.items():
                if dims.get(dim, value) != value:
                    conflict = f"{dim} is both {dims[dim]} and {value} ({reading.label})"
                    break
                dims[dim] = value
            if conflict:
                break
        if conflict:
            contradictions.append(conflict)
        else:
            hypotheses.append((wasted, Hypothesis(dims=dims, choices=choices)))
    # Keep only the readings in which every ambiguous token pulls its weight.
    fewest = min((w for w, _ in hypotheses), default=0)
    return [h for w, h in hypotheses if w == fewest], sorted(set(contradictions))


# ---------------------------------------------------------------------------
# Step 5: equipment context
# ---------------------------------------------------------------------------
def _apply_equipment_context(hypothesis: Hypothesis, parsed: ParsedName, rules: RuleSet) -> None:
    """Fill (never overwrite) dimensions the equipment type makes obvious."""
    if parsed.equipment is None:
        return
    equip = rules.equipment[parsed.equipment.type]
    dims = hypothesis.dims

    subject = dims.get("subject")
    for dim, value in equip.subject_defaults.get(subject, {}).items():
        if dim not in dims:
            dims[dim] = value
            hypothesis.notes.append(f"{dim}={value} from context ({subject} on a {equip.label})")

    # Equipment-wide defaults only apply to points that name no quantity:
    # "SS" on an exhaust fan is the fan's start/stop, but "ZN_T" on it is still a zone temp.
    if "quantity" not in dims:
        for dim, value in equip.defaults.items():
            if dim not in dims:
                dims[dim] = value
                hypothesis.notes.append(f"{dim}={value} from context (point on a {equip.label})")


# ---------------------------------------------------------------------------
# Steps 6-7: test one hypothesis against one role
# ---------------------------------------------------------------------------
def _evaluate(role: Role, hypothesis: Hypothesis, ctx: Context) -> Candidate | None:
    dims = dict(hypothesis.dims)
    inferred_from_metadata, conventions = [], []

    # Hard requirements: satisfied by the name, a convention, or metadata; else reject.
    for dim, wanted in role.requires.items():
        have = dims.get(dim)
        if have == wanted:
            continue
        if have is not None:
            return None                                   # the name says something else
        how, from_metadata = _fill_gap(dim, wanted, dims, ctx)
        if how is None:
            return None                                   # nothing can supply it
        dims[dim] = wanted
        (inferred_from_metadata if from_metadata else conventions).append(how)

    # Optional dimensions may be absent, but must not contradict.
    for dim, wanted in role.optional.items():
        if dims.get(dim, wanted) != wanted:
            return None
    if role.medium and dims.get("medium", role.medium) != role.medium:
        return None

    candidate = Candidate(role, hypothesis, dims, inferred=conventions + inferred_from_metadata)
    add = candidate.breakdown.append

    # Base score: did the name carry the meaning, or did metadata have to help?
    if inferred_from_metadata:
        add(("name needed metadata to be complete", BASE_NEEDS_METADATA))
    else:
        add(("name defines the role", BASE_COMPLETE_NAME))
    if hypothesis.choices:
        add((f"ambiguous token resolved ({'; '.join(hypothesis.choices)})", AMBIGUOUS_TOKEN))

    # Object type.
    object_type = ctx.record.object_type
    if object_type:
        if object_type in role.bacnet_types:
            add((f"object type {object_type} agrees", TYPE_AGREES))
        else:
            add((f"object type {object_type} contradicts", TYPE_CONTRADICTS))
            candidate.flags.append(
                f"TYPE_MISMATCH: {object_type} is unusual for {role.id} (expected {'/'.join(role.bacnet_types)})")

    # Units. When units filled the quantity gap they still count as agreeing:
    # the lower base score has already charged for the incomplete name.
    family = ctx.units_family
    if family:
        if role.units_family and family in role.units_family:
            add((f"units {ctx.units_label} agree", UNITS_AGREE))
        elif not role.units_family and family == "state":
            add((f"units {ctx.units_label} agree (on/off state)", UNITS_AGREE))
        else:
            add((f"units {ctx.units_label} contradict", UNITS_CONTRADICT))
            expected = "/".join(role.units_family) if role.units_family else "an on/off state"
            candidate.flags.append(f"UNITS_CONFLICT: {ctx.units_label} ({family}) but {role.id} expects {expected}")

    # Description (weak evidence: supports or questions, never decides).
    described = ctx.description_dims
    if described:
        compared = [d for d in ("position", "quantity", "subject") if d in described and d in dims]
        disagree = [d for d in compared if described[d] != dims[d]]
        if disagree:
            add(("description disagrees", DESCRIPTION_CONTRADICTS))
            candidate.flags.append("DESC_DISAGREES: description suggests "
                                   + ", ".join(f"{d}={described[d]}" for d in disagree))
        elif compared:
            add(("description agrees", DESCRIPTION_AGREES))

    # Meaning in the name that this role doesn't account for.
    explained = set(role.requires) | set(role.optional) | {"medium"}
    for dim in sorted(set(dims) - explained):
        add((f"'{dim}={dims[dim]}' unexplained by {role.id}", UNEXPLAINED_MEANING))
        candidate.flags.append(f"UNEXPLAINED: name says {dim}={dims[dim]}, which {role.id} doesn't use")

    # Naming noise.
    if ctx.unknown:
        add((f"unknown tokens {', '.join(ctx.unknown)}",
             max(UNKNOWN_TOKEN_CAP, UNKNOWN_TOKEN * len(ctx.unknown))))
        candidate.flags.append(f"UNKNOWN_TOKEN: {', '.join(ctx.unknown)}")
    for correction in ctx.fuzzy:
        add((f"fuzzy match {correction}", FUZZY_TOKEN))
        candidate.flags.append(f"FUZZY: read {correction}")

    # Equipment fit.
    equipment = ctx.parsed.equipment
    if equipment is None and not role.site_level:
        add(("no equipment in the name", NO_EQUIPMENT))
        candidate.flags.append("NO_EQUIPMENT: point could not be attached to equipment")
    elif equipment is not None and role.equip_types and equipment.type not in role.equip_types:
        add((f"{role.id} is unusual on a {equipment.type}", UNUSUAL_EQUIPMENT))
        candidate.flags.append(f"UNUSUAL_EQUIPMENT: {role.id} on {equipment.type} {equipment.ref}")

    return candidate


def _fill_gap(dim: str, wanted: str, dims: dict, ctx: Context) -> tuple[str | None, bool]:
    """Try to supply a missing dimension. Returns (explanation, came_from_metadata)."""
    rules = ctx.rules
    if dim == "function":
        # Naming convention first: this is how the name is written, so full credit.
        for convention in rules.conventions:
            present = dims.get(convention.dim)
            if present and (convention.value is None or present == convention.value) \
                    and convention.function == wanted:
                return f"function={wanted} by convention: {convention.why}", False
        # Then the object type (metadata: lower base score).
        object_type = ctx.record.object_type
        if object_type and wanted in rules.object_type_functions.get(object_type, ()):
            return f"function={wanted} inferred from object type {object_type}", True
    if dim == "quantity" and ctx.units_family == wanted:
        return f"quantity={wanted} inferred from units {ctx.units_label}", True
    if dim == "subject" and wanted == "stage" and dims.get("mode") and ctx.parsed.index is not None:
        return f"stage inferred from numbered {dims['mode']} token", True
    return None, False


# ---------------------------------------------------------------------------
# Result assembly
# ---------------------------------------------------------------------------
def _build_result(site, record, parsed, best: Candidate, runner_up, evidence, base_flags) -> PointResult:
    role = best.role
    flags = base_flags + best.flags
    evidence = evidence + best.hypothesis.notes + best.inferred

    # Canonical point name: stage number for staged roles, index suffix otherwise.
    stage = None
    if role.stage:
        if parsed.index is not None:
            stage = parsed.index
            canonical_point = role.canonical.format(n=stage)
        else:
            canonical_point = role.canonical.format(n="")
            flags.append("STAGE_MISSING: staged point without a stage number")
    else:
        canonical_point = role.canonical
        if parsed.index is not None:
            canonical_point = f"{role.canonical}-{parsed.index}"
            flags.append(f"INDEXED: numbered point ({parsed.index}); confirm it is a distinct sensor")

    if role.requires.get("function") == "status" and record.object_type in ("AI", "AV"):
        flags.append(f"STATUS_ON_ANALOG: {role.id} arrives as {record.object_type}"
                     + (f" in {record.units}" if record.units else "")
                     + "; check how proof is wired")

    owner = parsed.equipment.ref if parsed.equipment else (site if role.site_level else "UNASSIGNED")

    score = best.score
    evidence.append("score: " + ", ".join(f"{reason} {delta:+.2f}" for reason, delta in best.breakdown)
                    + f" = {score:.2f}")
    if runner_up:
        evidence.append(f"runner-up: {runner_up.role.id} {runner_up.score:.2f}")

    if owner == "UNASSIGNED":
        # A point that can't be attached to equipment can't be modelled or
        # controlled, however confident the role is. A person must place it.
        status = REVIEW
        reason = (f"no equipment in the name: best guess {role.id} ({score:.2f}); "
                  f"assign equipment from the device list or drawings")
    elif score >= AUTO_THRESHOLD and any(f.startswith(("FUZZY", "UNKNOWN_TOKEN")) for f in flags):
        # Auto-accept means every word of the name was understood. A typo read
        # through fuzzy matching, or a word the dictionary doesn't know ("HI LIMIT"
        # on a DAT), may be accepted, but a person looks at it first.
        status, reason = FLAGGED, None
        evidence.append("capped at flagged: the name contains words the rules don't fully understand")
    elif score >= AUTO_THRESHOLD:
        status, reason = AUTO, None
    elif score >= REVIEW_THRESHOLD:
        status, reason = FLAGGED, None
    else:
        status, reason = REVIEW, _review_reason(best, record, score)

    return PointResult(
        site=site, record=record, parsed=parsed,
        role_id=role.id, role_name=role.name,
        canonical_point=canonical_point, canonical_name=f"{owner}.{canonical_point}",
        haystack_tags=list(role.haystack) + ["point"], brick_class=role.brick,
        stage=stage, confidence=score, status=status,
        evidence=evidence, flags=flags, review_reason=reason,
    )


def _review_reason(best: Candidate, record: PointRecord, score: float) -> str:
    """The most useful sentence for the person working the review queue."""
    role = best.role
    # A classic field-wiring question, worth naming explicitly.
    if (role.requires.get("function") == "status" and record.object_type in ("AI", "AV")
            and record.units_family == "current"):
        return (f"status point wired as an analog input reading amps (current transducer?). "
                f"Confirm how proof is wired before mapping as {role.id}")
    conflicts = [f for f in best.flags if f.startswith(("UNITS_CONFLICT", "TYPE_MISMATCH"))]
    if conflicts:
        return f"best guess {role.id} ({score:.2f}) but metadata disagrees: " + "; ".join(
            f.split(": ", 1)[1] for f in conflicts)
    return f"low confidence: best guess {role.id} ({score:.2f})"


def _refuse(site, record, parsed, evidence, flags, reason) -> PointResult:
    """A point the classifier will not map at all."""
    return PointResult(
        site=site, record=record, parsed=parsed,
        role_id=None, role_name=None, canonical_point=None, canonical_name=None,
        haystack_tags=[], brick_class=None, stage=None,
        confidence=0.0, status=REVIEW, evidence=evidence, flags=list(flags), review_reason=reason,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _description_dims(record: PointRecord, rules: RuleSet) -> dict:
    """Unambiguous dimensions mentioned in the free-text description."""
    if not record.description:
        return {}
    dims = {}
    for token in tokenize_text(record.description, rules):
        alternatives = rules.tokens.get(token)
        if alternatives and len(alternatives) == 1:
            for dim, value in alternatives[0].items():
                dims.setdefault(dim, value)
    return dims


def _describe_reading(reading: TokenReading) -> str:
    if len(reading.alternatives) > 1:
        return f"{reading.label}=?(" + " or ".join(_fmt_dims(a) for a in reading.alternatives) + ")"
    return f"{reading.label}={_fmt_dims(reading.alternatives[0]) or '(descriptive)'}"


def _fmt_dims(dims: dict) -> str:
    return ",".join(f"{k}={v}" for k, v in dims.items())
