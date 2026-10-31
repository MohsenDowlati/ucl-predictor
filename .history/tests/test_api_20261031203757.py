from datetime import datetime

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.deps import get_session
from api.main import app
from ucl.config import settings
from ucl.db.models import Base, Match, Prediction, Team


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "model_version", "v1")   # don't depend on the local .env
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(engine)
    with Session() as s:
        s.add_all([Team(id=1, name="Alpha FC", short_name="Alpha"),
                   Team(id=2, name="Beta United", short_name=None)])
        s.add_all([
            Match(id=10, season=2026, utc_date=datetime(2026, 9, 1, 19), stage="LEAGUE_STAGE",
                  status="FINISHED", home_team_id=1, away_team_id=2,
                  home_goals=2, away_goals=0, duration="REGULAR"),
            Match(id=11, season=2026, utc_date=datetime(2026, 10, 1, 19), stage="LEAGUE_STAGE",
                  status="SCHEDULED", home_team_id=2, away_team_id=1,
                  home_goals=None, away_goals=None),
        ])
        s.add_all([
            Prediction(match_id=11, model_version="v1", p_home=0.30, p_draw=0.30, p_away=0.40),
            Prediction(match_id=11, model_version="v1", p_home=0.25, p_draw=0.30, p_away=0.45),
            Prediction(match_id=11, model_version="other", p_home=0.90, p_draw=0.05, p_away=0.05),
        ])
        s.commit()
    pd.DataFrame({
        "match_id": [10, 10], "team_id": [1, 2],
        "utc_date": [datetime(2026, 9, 1, 19)] * 2,
        "elo_before": [1500.0, 1500.0], "elo_after": [1515.0, 1485.0],
    }).to_sql("elo_history", engine, index=False)

    def override():
        with Session() as s:
            yield s

    app.dependency_overrides[get_session] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_upcoming_uses_newest_prediction_of_the_active_model(client):
    body = client.get("/matches?status=upcoming").json()
    assert [m["id"] for m in body] == [11]
    pred = body[0]["prediction"]
    assert pred["home"] == 0.25 and pred["model_version"] == "v2"
    assert body[0]["kickoff"].endswith("Z")


def test_finished_matches(client):
    body = client.get("/matches?status=finished").json()
    assert [m["id"] for m in body] == [10]
    assert body[0]["home_goals"] == 2 and body[0]["prediction"] is None


def test_match_detail_has_history_oldest_first(client):
    body = client.get("/matches/11").json()
    assert [p["home"] for p in body["prediction_history"]] == [0.30, 0.25]
    assert body["home"]["name"] == "Beta United"


def test_unknown_match_and_team_return_404(client):
    assert client.get("/matches/999").status_code == 404
    assert client.get("/teams/999").status_code == 404


def test_teams_sorted_by_elo(client):
    body = client.get("/teams").json()
    assert [t["name"] for t in body] == ["Alpha FC", "Beta United"]
    assert body[0]["elo"] == 1515.0


def test_team_detail(client):
    body = client.get("/teams/1").json()
    assert body["elo"] == 1515.0 and len(body["elo_history"]) == 1
    assert [m["id"] for m in body["recent_matches"]] == [10]
    assert [m["id"] for m in body["upcoming_matches"]] == [11]


def test_model_info(client, tmp_path, monkeypatch):
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "artifacts" / "metrics_v1.json").write_text('{"test": {}}')
    monkeypatch.chdir(tmp_path)
    assert client.get("/model/info").json()["version"] == "v1"