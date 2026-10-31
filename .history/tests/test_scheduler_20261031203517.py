from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ucl.db.models import Base, Match, Team
from ucl.pipelines.refresh import fingerprint
from ucl.pipelines.scheduler import IDLE_EVERY, LIVE_EVERY, choose_interval

NOW = datetime(2026, 11, 3, 12, 0)


def at(**kw) -> datetime:
    return NOW + timedelta(**kw)


def test_idle_when_nothing_is_scheduled():
    assert choose_interval(NOW, []) == IDLE_EVERY


def test_live_just_before_kickoff_and_during_the_match():
    assert choose_interval(NOW, [at(minutes=20)]) == LIVE_EVERY
    assert choose_interval(NOW, [at(hours=-2)]) == LIVE_EVERY


def test_stale_unfinished_match_does_not_keep_polling_fast():
    assert choose_interval(NOW, [at(hours=-5)]) == IDLE_EVERY


def test_wakes_when_the_live_window_opens():
    assert choose_interval(NOW, [at(hours=3)]) == 3 * 3600 - 30 * 60


def test_far_future_stays_idle():
    assert choose_interval(NOW, [at(days=3)]) == IDLE_EVERY


def test_never_sleeps_less_than_a_minute():
    assert choose_interval(NOW, [at(minutes=31)]) == 60


def test_live_beats_later_matches():
    assert choose_interval(NOW, [at(hours=5), at(minutes=-30)]) == LIVE_EVERY


def test_fingerprint_changes_only_when_results_change():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessionmaker(engine)() as s:
        s.add_all([Team(id=1, name="A"), Team(id=2, name="B")])
        s.add(Match(id=1, season=2026, utc_date=datetime(2026, 10, 1, 19),
                    status="SCHEDULED", home_team_id=1, away_team_id=2))
        s.commit()
        first = fingerprint(engine, 2026)
        assert fingerprint(engine, 2026) == first

        match = s.get(Match, 1)
        match.status, match.home_goals, match.away_goals = "FINISHED", 2, 1
        s.commit()
        assert fingerprint(engine, 2026) != first