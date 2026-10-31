import csv
import re
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path

from ucl.db.models import Match, Team
from ucl.db.session import SessionLocal, init_db
from ucl.ingestion.team_names import GENERATED_ID_START, resolve_teams

RAW_DIR = Path("data/external/openfootball")
REPORT_PATH = Path("data/processed/team_resolution.csv")
MATCH_ID_BASE = 10_000_000   # id = base + (season - 2000) * 1000 + index in season

MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1)}
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

TITLE_RE = re.compile(r"^=\s*UEFA Champions League\s+(\d{4})/\d{2}")
COUNT_RE = re.compile(r"^#\s*Matches\s+(\d+)")
STAGE_RE = re.compile(r"^\s*▪\s*(.+?)\s*$")
DATE_RE = re.compile(
    r"^\s*(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+([A-Z][a-z]{2})\s+(\d{1,2})(?:\s+(\d{4}))?\s*$")
MATCH_RE = re.compile(
    r"^\s*(?:(\d{1,2})[:.](\d{2})\s+)?"
    r"(.+?)\s+\([A-Z]{2,3}\)\s+v\s+(.+?)\s+\([A-Z]{2,3}\)\s+(\d+-\d+.*)$")
SCORE_RE = re.compile(
    r"(?P<a>\d+-\d+)"
    r"(?:\s+pen\.\s+(?P<b>\d+-\d+))?"
    r"(?P<aet>\s+a\.e\.t\.)?"
    r"(?:\s+\((?P<paren>[^)]*)\))?\s*$")

STAGES = {
    "round of 16": "LAST_16",
    "quarterfinals": "QUARTER_FINALS", "quarter-finals": "QUARTER_FINALS",
    "semifinals": "SEMI_FINALS", "semi-finals": "SEMI_FINALS",
    "final": "FINAL",
}


@dataclass
class ParsedMatch:
    season: int
    index: int
    kickoff: datetime
    stage: str
    home: str
    away: str
    home_goals: int
    away_goals: int
    duration: str


def stage_code(heading: str) -> str | None:
    h = heading.strip().lower()
    if h.startswith(("group ", "gruppe ")):
        return "GROUP_STAGE"
    return STAGES.get(h)


def resolve_date(weekday, mon, day, year, start_year) -> date | None:
    month = MONTHS[mon]
    if year:
        return date(int(year), month, int(day))
    for y in (start_year, start_year + 1):
        try:
            d = date(y, month, int(day))
        except ValueError:          # e.g. Feb 29 in a non-leap year
            continue
        if WEEKDAYS[d.weekday()] == weekday:
            return d
    return None


def parse_score(text: str) -> tuple[int, int, str] | None:
    m = SCORE_RE.match(text.strip())
    if not m:
        return None
    parts = [p.strip() for p in (m["paren"] or "").split(",") if p.strip()]
    if m["b"]:
        duration = "PENALTY_SHOOTOUT"
    elif m["aet"]:
        duration = "EXTRA_TIME"
    else:
        duration = "REGULAR"

    if duration == "REGULAR":
        score = m["a"]
    elif parts:
        score = parts[0]            # bracket is (score after 90', half-time score)
    else:
        return None                 # extra time but no 90-minute score given
    try:
        home, away = (int(x) for x in score.split("-"))
    except ValueError:
        return None
    return home, away, duration


def parse_file(path: Path):
    matches: list[ParsedMatch] = []
    warnings: list[str] = []
    season = declared = None
    stage = day = kickoff = None

    text = path.read_text(encoding="utf-8-sig")
    for n, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            if (m := COUNT_RE.match(line)):
                declared = int(m[1])
            continue
        if (m := TITLE_RE.match(line)):
            season = int(m[1])
            continue
        if season is None:
            raise ValueError(f"{path}: no '= UEFA Champions League YYYY/YY' title line")

        if (m := STAGE_RE.match(line)):
            stage = stage_code(m[1])
            if stage is None:
                warnings.append(f"line {n}: unknown stage {m[1]!r}")
                stage = re.sub(r"\W+", "_", m[1].strip().upper())
            day = kickoff = None
            continue

        if (m := DATE_RE.match(line)):
            day = resolve_date(m[1], m[2], m[3], m[4], season)
            kickoff = None
            if day is None:
                warnings.append(f"line {n}: could not resolve date {line!r}")
            continue

        if (m := MATCH_RE.match(line)):
            if m[1]:
                kickoff = time(int(m[1]), int(m[2]))   # later lines reuse the last time
            score = parse_score(m[5])
            if day is None or stage is None or score is None:
                warnings.append(f"line {n}: skipped {line!r}")
                continue
            matches.append(ParsedMatch(
                season, len(matches), datetime.combine(day, kickoff or time(0, 0)),
                stage, m[3].strip(), m[4].strip(), *score))
            continue

        warnings.append(f"line {n}: unrecognised {line!r}")

    return season, matches, declared, warnings


def write_report(report: list[dict]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with REPORT_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(report[0]))
        writer.writeheader()
        writer.writerows(report)


def run() -> None:
    init_db()
    files = sorted(RAW_DIR.rglob("cl.txt"))
    if not files:
        raise SystemExit(f"No cl.txt files found under {RAW_DIR.resolve()}")

    parsed: list[ParsedMatch] = []
    seen: dict[int, Path] = {}
    for f in files:
        season, matches, declared, warnings = parse_file(f)
        if season in seen:
            raise SystemExit(f"Season {season} found twice: {seen[season]} and {f}")
        seen[season] = f
        flag = "" if declared in (None, len(matches)) else f"   <-- file declares {declared}"
        print(f"{season}/{str(season + 1)[-2:]}: parsed {len(matches)} matches{flag}")
        for w in warnings:
            print("    !", w)
        parsed.extend(matches)

    with SessionLocal() as session:
        if session.query(Team).filter(Team.id < GENERATED_ID_START).count() == 0:
            raise SystemExit("No football-data teams in the DB yet. "
                             "Run ucl.ingestion.historical first.")

        # Reload from scratch so alias edits take effect on re-runs.
        session.query(Match).filter(Match.source == "openfootball").delete()
        session.query(Team).filter(Team.id >= GENERATED_ID_START).delete()

        names = {n for pm in parsed for n in (pm.home, pm.away)}
        team_ids, new_teams, report = resolve_teams(session, names)

        session.add_all(Team(id=i, name=n) for i, n in new_teams.items())
        session.add_all(
            Match(
                id=MATCH_ID_BASE + (pm.season - 2000) * 1000 + pm.index,
                season=pm.season,
                utc_date=pm.kickoff,
                stage=pm.stage,
                matchday=None,
                status="FINISHED",
                home_team_id=team_ids[pm.home],
                away_team_id=team_ids[pm.away],
                home_goals=pm.home_goals,
                away_goals=pm.away_goals,
                duration=pm.duration,
                source="openfootball",
            )
            for pm in parsed
        )
        session.commit()

    write_report(report)
    new = [r for r in report if r["how"] == "new"]
    print(f"\n{len(report)} club names: {len(report) - len(new)} linked to football-data "
          f"teams, {len(new)} new.")
    print("New clubs that might actually be existing ones (add to team_aliases.csv):")
    for r in new:
        if r["possible_matches"]:
            print(f"  {r['openfootball_name']!r}  ->  {r['possible_matches']}")
    print(f"Full list: {REPORT_PATH}")


if __name__ == "__main__":
    run()