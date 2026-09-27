"""Load and validate the YAML rule files.

All BAS domain knowledge lives in rules/*.yaml, not in Python. This module
turns those files into typed objects and checks them for mistakes *before* any
point is processed. A typo in a rule fails loudly at start-up instead of
silently mis-mapping a building.
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

DIMENSIONS = ("position", "medium", "quantity", "function", "subject", "mode")
FUNCTIONS = ("sensor", "sp", "cmd", "status")

# rules/ sits next to the package in the repository.
DEFAULT_RULES_DIR = Path(__file__).resolve().parent.parent / "rules"


class RuleError(ValueError):
    """A rule file is malformed. Raised at load time, never mid-run."""


# ---------------------------------------------------------------------------
# Rule objects
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Unit:
    canonical: str
    family: str
    haystack: str | None
    qudt: str | None


@dataclass(frozen=True)
class Convention:
    dim: str               # dimension that must be present...
    value: str | None      # ...optionally with this value
    function: str          # function assumed when the name has none
    why: str


@dataclass(frozen=True)
class Role:
    id: str
    name: str
    requires: dict
    optional: dict
    medium: str | None
    units_family: tuple        # empty tuple = binary/enum point (no units expected)
    bacnet_types: tuple
    equip_types: tuple         # empty tuple = any equipment
    site_level: bool
    stage: bool
    canonical: str
    haystack: tuple
    brick: str
    kind: str
    order: int                 # position in the YAML file: deterministic tie-breaker


@dataclass(frozen=True)
class EquipType:
    key: str
    label: str
    aliases: tuple
    haystack: tuple
    brick: str
    defaults: dict
    subject_defaults: dict
    required: tuple            # tuple of tuples; each inner tuple = acceptable alternatives
    recommended: tuple

    @property
    def prefix(self) -> str:
        """Canonical id prefix: the first alias (VMA-203 becomes VAV-203)."""
        return self.aliases[0]


@dataclass
class RuleSet:
    version: int
    tokens: dict                   # TOKEN -> list of dimension dicts (one entry = unambiguous)
    conventions: list
    non_telemetry: dict            # TOKEN -> review reason
    slash_abbreviations: dict
    mergeable_tokens: frozenset    # tokens camelCase splitting must re-assemble (CO2, DEGF...)
    units: dict                    # normalized alias -> Unit
    none_units: frozenset
    object_types: dict             # normalized alias -> canonical type
    object_type_functions: dict
    roles: list
    equipment: dict                # key -> EquipType
    alias_to_equipment: dict
    equipment_pattern: re.Pattern
    fuzzy_vocabulary: list

    def role(self, role_id: str) -> Role:
        return next(r for r in self.roles if r.id == role_id)


# ---------------------------------------------------------------------------
# Normalization helpers (shared with ingest and tokens)
# ---------------------------------------------------------------------------
def unit_keys(text: str) -> tuple[str, str]:
    """Two lookup keys for a unit string: spaces collapsed, and fully squeezed.

    "deg F", "DEG_F" and "degF" all reach the same key.
    """
    upper = re.sub(r"\s+", " ", str(text).strip().upper())
    squeezed = re.sub(r"[\s_\-.]", "", upper)
    return upper, squeezed


def object_type_key(text: str) -> str:
    """'analog-input', 'analogInput' and 'AI' -> 'ANALOGINPUT' / 'AI'."""
    return re.sub(r"[^A-Z]", "", str(text).upper())


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def load_rules(rules_dir: str | Path | None = None) -> RuleSet:
    """Read the three rule files and return a validated RuleSet."""
    rules_dir = Path(rules_dir) if rules_dir else DEFAULT_RULES_DIR
    abbreviations = _read_yaml(rules_dir / "abbreviations.yaml")
    point_roles = _read_yaml(rules_dir / "point_roles.yaml")
    templates = _read_yaml(rules_dir / "equipment_templates.yaml")

    tokens = _load_tokens(abbreviations.get("tokens", {}))
    units, unit_tokens = _load_units(abbreviations.get("units", []))
    equipment = _load_equipment(templates.get("equipment", {}))
    roles = _load_roles(point_roles.get("roles", []), equipment)
    _validate_templates(equipment, roles)

    alias_to_equipment = {}
    for eq in equipment.values():
        for alias in eq.aliases:
            if alias in alias_to_equipment:
                raise RuleError(f"equipment alias {alias!r} used by two equipment types")
            alias_to_equipment[alias] = eq.key

    return RuleSet(
        version=int(abbreviations.get("version", 1)),
        tokens=tokens,
        conventions=_load_conventions(abbreviations.get("function_conventions", [])),
        non_telemetry={k.upper(): v for k, v in abbreviations.get("non_telemetry", {}).items()},
        slash_abbreviations=abbreviations.get("slash_abbreviations", {}),
        mergeable_tokens=frozenset(
            [t.upper() for t in abbreviations.get("protected_tokens", [])] + unit_tokens
        ),
        units=units,
        none_units=frozenset(
            k for value in abbreviations.get("none_units", []) for k in unit_keys(value)
        ),
        object_types=_load_object_types(abbreviations.get("bacnet_object_types", {})),
        object_type_functions={
            k.upper(): tuple(v) for k, v in abbreviations.get("object_type_functions", {}).items()
        },
        roles=roles,
        equipment=equipment,
        alias_to_equipment=alias_to_equipment,
        equipment_pattern=_equipment_pattern(alias_to_equipment),
        # Candidate words for typo recovery: long enough that a fuzzy match means something.
        fuzzy_vocabulary=sorted(t for t in tokens if len(t) >= 4),
    )


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        raise RuleError(f"rule file not found: {path}")
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _check_dims(dims: dict, where: str) -> dict:
    for dim, value in dims.items():
        if dim not in DIMENSIONS:
            raise RuleError(f"{where}: unknown dimension {dim!r} (allowed: {', '.join(DIMENSIONS)})")
        if dim == "function" and value not in FUNCTIONS:
            raise RuleError(f"{where}: function must be one of {FUNCTIONS}, got {value!r}")
    return dict(dims)


def _load_tokens(raw: dict) -> dict:
    """Normalize every token entry to a list of alternatives."""
    tokens = {}
    for token, meaning in raw.items():
        where = f"abbreviations.yaml token {token}"
        meaning = meaning or {}
        if "ambiguous" in meaning:
            alternatives = [_check_dims(alt, where) for alt in meaning["ambiguous"]]
            if len(alternatives) < 2:
                raise RuleError(f"{where}: an ambiguous token needs at least two alternatives")
        else:
            alternatives = [_check_dims(meaning, where)]
        tokens[str(token).upper()] = alternatives
    return tokens


def _load_conventions(raw: list) -> list:
    conventions = []
    for item in raw:
        dim, _, value = str(item["if_has"]).partition("=")
        if dim not in DIMENSIONS or item["function"] not in FUNCTIONS:
            raise RuleError(f"function_conventions: bad entry {item!r}")
        conventions.append(Convention(dim, value or None, item["function"], item.get("why", "")))
    return conventions


def _load_units(raw: list) -> tuple[dict, list]:
    units, unit_tokens = {}, []
    for entry in raw:
        unit = Unit(entry["canonical"], entry["family"], entry.get("haystack"), entry.get("qudt"))
        for alias in entry.get("aliases", []) + [entry["canonical"]]:
            for key in unit_keys(alias):
                if key in units and units[key] != unit:
                    raise RuleError(f"unit alias {alias!r} maps to two different units")
                units[key] = unit
            squeezed = unit_keys(alias)[1]
            # Units that can appear *inside* a point name ("ZN_TEMP_DegF").
            # Only multi-letter alphanumeric aliases: single letters (F, C, A) are too ambiguous.
            if len(squeezed) >= 3 and squeezed.isalnum():
                unit_tokens.append(squeezed)
    return units, unit_tokens


def _load_object_types(raw: dict) -> dict:
    types = {}
    for canonical, aliases in raw.items():
        for alias in list(aliases) + [canonical]:
            types[object_type_key(alias)] = canonical.upper()
    return types


def _load_equipment(raw: dict) -> dict:
    equipment = {}
    for key, spec in raw.items():
        where = f"equipment_templates.yaml {key}"
        if not spec.get("aliases"):
            raise RuleError(f"{where}: needs at least one alias")
        subject_defaults = {
            subj: _check_dims(dims, where) for subj, dims in (spec.get("subject_defaults") or {}).items()
        }
        equipment[key] = EquipType(
            key=key,
            label=spec.get("label", key),
            aliases=tuple(a.upper() for a in spec["aliases"]),
            haystack=tuple(spec.get("haystack", ["equip"])),
            brick=spec["brick"],
            defaults=_check_dims(spec.get("defaults") or {}, where),
            subject_defaults=subject_defaults,
            required=tuple(tuple(item.split("|")) for item in spec.get("required", [])),
            recommended=tuple(tuple(item.split("|")) for item in spec.get("recommended", [])),
        )
    return equipment


def _load_roles(raw: list, equipment: dict) -> list:
    roles, seen = [], set()
    for order, spec in enumerate(raw):
        role_id = spec["id"]
        where = f"point_roles.yaml {role_id}"
        if role_id in seen:
            raise RuleError(f"{where}: duplicate role id")
        seen.add(role_id)
        requires = _check_dims(spec.get("requires") or {}, where)
        if "function" not in requires:
            raise RuleError(f"{where}: every role must require a function")
        for eq in spec.get("equip_types") or []:
            if eq not in equipment:
                raise RuleError(f"{where}: unknown equipment type {eq!r}")
        stage = bool(spec.get("stage", False))
        canonical = spec.get("canonical", role_id)
        if stage != ("{n}" in canonical):
            raise RuleError(f"{where}: staged roles need '{{n}}' in canonical, others must not have it")
        roles.append(Role(
            id=role_id,
            name=spec["name"],
            requires=requires,
            optional=_check_dims(spec.get("optional") or {}, where),
            medium=spec.get("medium"),
            units_family=tuple(spec.get("units_family") or ()),
            bacnet_types=tuple(t.upper() for t in spec.get("bacnet_types", [])),
            equip_types=tuple(spec.get("equip_types") or ()),
            site_level=bool(spec.get("site_level", False)),
            stage=stage,
            canonical=canonical,
            haystack=tuple(spec["haystack"]),
            brick=spec["brick"],
            kind=spec.get("kind", "Number"),
            order=order,
        ))
    return roles


def _validate_templates(equipment: dict, roles: list) -> None:
    """Every required/recommended entry must match at least one real role."""
    role_ids = [r.id for r in roles]
    for eq in equipment.values():
        for group in eq.required + eq.recommended:
            for pattern in group:
                if not fnmatch.filter(role_ids, pattern):
                    raise RuleError(f"equipment_templates.yaml {eq.key}: {pattern!r} matches no role")


def _equipment_pattern(alias_to_equipment: dict) -> re.Pattern:
    """One regex for every equipment alias, longest alias first.

        (?<![A-Z0-9])   not glued to a preceding letter/digit ("DEF1" is not EF-1)
        (?P<alias>...)  RTU | AHU | VAV | VMA | EF | ...
        [\\s_\\-#]*     optional separator: "RTU_1", "RTU-1", "Rtu #1", "RTU1"
        (?P<id>...)     one or more number groups: "1", "203", "2-03"

    Applied to the upper-cased segment; an alias must be followed by a number,
    so a point token like "EF_S" (exhaust fan status) is not mistaken for equipment.
    """
    aliases = sorted(alias_to_equipment, key=len, reverse=True)
    return re.compile(
        r"(?<![A-Z0-9])(?P<alias>" + "|".join(map(re.escape, aliases)) + r")"
        r"[\s_\-#]*(?P<id>\d+(?:[\s_\-]?\d+)*)"
    )
