import csv
import difflib
import re
import unicodedata
from pathlib import Path

from ucl.db.models import Team

GENERATED_ID_START = 1_000_000          # ids for clubs not in football-data
OVERRIDES_PATH = Path(__file__).with_name("team_aliases.csv")
NOISE = {"fc", "cf", "afc", "sc", "ac", "as", "ssc", "bsc", "fk", "sk"}
CHAR_MAP = str.maketrans({"ø": "o", "ß": "ss", "ł": "l", "đ": "d", "æ": "ae"})


def normalize(name: str) -> str:
    s = unicodedata.normalize("NFKD", name.casefold().translate(CHAR_MAP))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return " ".join(t for t in s.split() if t not in NOISE)


def load_overrides() -> dict[str, str]:
    if not OVERRIDES_PATH.exists():
        return {}
    with OVERRIDES_PATH.open(encoding="utf-8-sig", newline="") as f:
        return {normalize(r["alias"]): r["canonical"].strip() for r in csv.DictReader(f)}


def suggest(key: str, known: dict[str, int], display: dict[int, str]) -> list[str]:
    close = difflib.get_close_matches(key, list(known), n=2, cutoff=0.6)
    long_tokens = {t for t in key.split() if len(t) >= 5}
    shared = [k for k in known if long_tokens & set(k.split())]
    ids: list[int] = []
    for k in close + shared:
        if known[k] not in ids:
            ids.append(known[k])
    return [display[i] for i in ids[:3]]


def resolve_teams(session, names: set[str]):
    """Map openfootball names to team ids.

    Returns (name -> team_id, {new_team_id: display_name}, report_rows).
    """
    overrides = load_overrides()

    known: dict[str, int] = {}   # normalized name -> football-data team id
    display: dict[int, str] = {}
    teams = session.query(Team).filter(Team.id < GENERATED_ID_START).all()
    for t in teams:
        display[t.id] = t.name
        known.setdefault(normalize(t.name), t.id)
    for t in teams:              # short names second, so full names win
        if t.short_name:
            known.setdefault(normalize(t.short_name), t.id)

    team_ids: dict[str, int] = {}
    new_teams: dict[int, str] = {}
    new_by_key: dict[str, int] = {}
    report: list[dict] = []
    next_id = GENERATED_ID_START

    for name in sorted(names):
        target = overrides.get(normalize(name), name)
        key = normalize(target)
        if key in known:
            team_id = known[key]
            how = "override" if target != name else "exact"
            hint = ""
        else:
            if key not in new_by_key:
                new_by_key[key] = next_id
                new_teams[next_id] = target
                next_id += 1
            team_id, how = new_by_key[key], "new"
            hint = " | ".join(suggest(key, known, display))
        team_ids[name] = team_id
        report.append({"openfootball_name": name, "team_id": team_id,
                       "how": how, "possible_matches": hint})
    return team_ids, new_teams, report