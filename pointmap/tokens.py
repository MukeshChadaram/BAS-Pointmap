"""Stage 2: split a raw vendor point name into equipment + point tokens.

Worked examples, one per vendor style:

    "#pine_paper/rtu_1/da_temp"                  (ALC WebCTRL path)
        segments  ["pine_paper", "rtu_1", "da_temp"]
        equipment rtu RTU-01            tokens ["DA", "TEMP"]

    "OFFICE-A:NAE-01/FC-2.VMA-203.ZN-SP"         (JCI Metasys reference)
        segments  ["OFFICE-A", "NAE-01", "FC-2", "VMA-203", "ZN-SP"]
        equipment vav VAV-203           tokens ["ZN", "SP"]

    "/Drivers/BacnetNetwork/RTU_4/points/HtgStg2" (Niagara ord path)
        equipment rtu RTU-04            tokens ["HTG", "STG"]   index 2

    "vav2-03_ZN_TEMP_DegF"                        (hand-typed)
        equipment vav VAV-2-03          tokens ["ZN", "TEMP"]   unit °F (from the name)

(Named tokens.py rather than tokenize.py so it can never shadow Python's
standard-library tokenize module.)
"""

from __future__ import annotations

import re

from .models import Equipment, ParsedName
from .rules import RuleSet, unit_keys

# Vendor path separators. "#" is handled separately: it is a path root in ALC
# ("#site/...") but a number sign in hand-typed names ("Rtu #1").
_PATH_SEPARATORS = re.compile(r"[/\\:.]")
_NON_ALNUM = re.compile(r"[^A-Z0-9]+")

# camelCase and letter/digit boundaries become token boundaries.
_ACRONYM_THEN_WORD = re.compile(r"([A-Z]+)([A-Z][a-z])")   # "HTGStage"  -> "HTG Stage"
_LOWER_THEN_UPPER = re.compile(r"([a-z])([A-Z])")          # "ZnTmpStpt" -> "Zn Tmp Stpt"
_LETTER_THEN_DIGIT = re.compile(r"([A-Za-z])(\d)")         # "Stg2"      -> "Stg 2"
_DIGIT_THEN_LETTER = re.compile(r"(\d)([A-Za-z])")         # "2nd"       -> "2 nd"


def parse_name(raw: str, rules: RuleSet) -> ParsedName:
    """Break one raw point name into segments, equipment, tokens, index and unit."""
    text = raw.strip()

    # 1. Rewrite slash abbreviations ("S/S" -> "SS") so they survive path splitting.
    #    Whole tokens only: in "points/SpaceTemp" the characters "s/S" straddle a
    #    path separator and must not be touched.
    for written, replacement in rules.slash_abbreviations.items():
        pattern = r"(?<![A-Za-z0-9])" + re.escape(written) + r"(?![A-Za-z0-9])"
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # 2. Drop an ALC-style path root, then split the vendor path.
    text = text.lstrip("#")
    segments = [s.strip() for s in _PATH_SEPARATORS.split(text) if s.strip()]
    if not segments:
        return ParsedName(raw, [], [], None, None, None, None)

    # 3. Find the equipment, nearest to the point first (right-to-left).
    equipment, leaf = _find_equipment(segments, rules)

    # 4. Tokenize what is left of the point itself.
    tokens = tokenize_text(leaf, rules)

    # 5. Pull out the trailing number (a stage or a sensor index) and any unit
    #    written into the name.
    tokens, index = _pull_index(tokens)
    tokens, unit = _pull_name_unit(tokens, rules)

    return ParsedName(
        raw=raw,
        segments=segments,
        tokens=tokens,
        equipment=equipment,
        index=index,
        name_unit=unit.canonical if unit else None,
        name_unit_family=unit.family if unit else None,
    )


def _find_equipment(segments: list[str], rules: RuleSet) -> tuple[Equipment | None, str]:
    """Return (equipment, text of the point itself).

    If the equipment sits inside the last segment ("RTU1-DAT", "Rtu #1 Disch Air
    Tmp") the matched text is cut out and the remainder is the point. Otherwise
    the equipment is a parent folder and the last segment is the point.
    """
    last = len(segments) - 1
    for position in range(last, -1, -1):
        segment = segments[position]
        match = rules.equipment_pattern.search(segment.upper())
        if not match:
            continue
        equipment = _make_equipment(match, segment, rules)
        if position == last:
            leaf = segment[: match.start()] + " " + segment[match.end():]
        else:
            leaf = segments[last]
        return equipment, leaf
    return None, segments[last]


def _make_equipment(match: re.Match, segment: str, rules: RuleSet) -> Equipment:
    """Canonical equipment id.

    A single number is zero-padded ("RTU_1" -> "RTU-01"). Multi-part ids keep
    their parts ("vav2-03" -> "VAV-2-03"). Nothing is invented: "VMA-203" stays
    "VAV-203" because the name never says which floor it is on.
    """
    equip_type = rules.equipment[rules.alias_to_equipment[match.group("alias")]]
    parts = re.findall(r"\d+", match.group("id"))
    ident = parts[0].zfill(2) if len(parts) == 1 else "-".join(parts)
    return Equipment(
        type=equip_type.key,
        ref=f"{equip_type.prefix}-{ident}",
        raw=segment[match.start(): match.end()],
    )


def tokenize_text(text: str, rules: RuleSet) -> list[str]:
    """Split on delimiters and camelCase, upper-case, re-join protected tokens.

    Also used on free-text descriptions, so both go through identical rules.
    """
    spaced = _ACRONYM_THEN_WORD.sub(r"\1 \2", text)
    spaced = _LOWER_THEN_UPPER.sub(r"\1 \2", spaced)
    spaced = _LETTER_THEN_DIGIT.sub(r"\1 \2", spaced)
    spaced = _DIGIT_THEN_LETTER.sub(r"\1 \2", spaced)
    tokens = [t for t in _NON_ALNUM.split(spaced.upper()) if t]
    return _merge_tokens(tokens, rules)


def _merge_tokens(tokens: list[str], rules: RuleSet) -> list[str]:
    """Undo over-splitting: ["CO", "2"] -> ["CO2"], ["DEG", "F"] -> ["DEGF"]."""
    merged, i = [], 0
    while i < len(tokens):
        for width in (4, 3, 2):
            joined = "".join(tokens[i: i + width])
            if i + width <= len(tokens) and joined in rules.mergeable_tokens:
                merged.append(joined)
                i += width
                break
        else:
            merged.append(tokens[i])
            i += 1
    return merged


def _pull_index(tokens: list[str]) -> tuple[list[str], int | None]:
    """Remove bare numbers. The last one is kept as the point's index."""
    numbers = [t for t in tokens if t.isdigit()]
    words = [t for t in tokens if not t.isdigit()]
    return words, (int(numbers[-1]) if numbers else None)


def _pull_name_unit(tokens: list[str], rules: RuleSet):
    """Detect a unit written into the name ("_DegF", "_INWC").

    The unit is recorded as evidence. The token is removed unless it also has
    a meaning of its own (CFM is both a unit and a flow token).
    """
    unit, kept = None, []
    for token in tokens:
        if len(token) >= 3 and token in rules.mergeable_tokens:
            found = next((rules.units[k] for k in unit_keys(token) if k in rules.units), None)
            if found is not None:
                unit = unit or found
                if token not in rules.tokens:
                    continue
        kept.append(token)
    return kept, unit
