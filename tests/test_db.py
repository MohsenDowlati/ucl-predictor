from ucl.db.session import SessionLocal
from ucl.db.models import Match


def test_no_negative_goals():
    with SessionLocal() as s:
        bad = s.query(Match).filter(
            (Match.home_goals < 0) | (Match.away_goals < 0)
        ).count()
    assert bad == 0