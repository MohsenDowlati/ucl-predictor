import logging
import time
from collections.abc import Iterable
from datetime import datetime, timezone

from sqlalchemy import select

from ucl.db.models import Match
from ucl.db.session import SessionLocal
from ucl.pipelines import refresh

from ucl.monitoring.report import run_checks

log = logging.getLogger("scheduler")

LIVE_EVERY = 10 * 60        
IDLE_EVERY = 6 * 60 * 60   
LIVE_BEFORE = 30 * 60       
LIVE_AFTER = 4 * 60 * 60    
MIN_SLEEP = 60


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)   


def choose_interval(now: datetime, kickoffs: Iterable[datetime]) -> int:
    """Seconds to wait before the next refresh."""
    interval = IDLE_EVERY
    for k in kickoffs:
        delta = (k - now).total_seconds()
        if -LIVE_AFTER <= delta <= LIVE_BEFORE:
            return LIVE_EVERY
        if delta > LIVE_BEFORE:
            interval = min(interval, int(delta - LIVE_BEFORE))   
    return max(interval, MIN_SLEEP)


def pending_kickoffs() -> list[datetime]:
    with SessionLocal() as session:
        return list(session.scalars(
            select(Match.utc_date).where(
                Match.season == refresh.current_season(), Match.status != "FINISHED")))


def next_sleep() -> int:
    try:
        return choose_interval(utcnow(), pending_kickoffs())
    except Exception:
        log.exception("could not read fixtures; using the live interval")
        return LIVE_EVERY


def log_monitoring() -> None:
    """Warnings go to the log; the full report is `python -m ucl.monitoring.report`."""
    try:
        for level, message in run_checks():
            if level == "WARN":
                log.warning("monitor: %s", message)
    except Exception:
        log.exception("monitoring failed")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    force = True           
    while True:
        try:
            changed = refresh.run(force=force)
            force = False
            log.info("refresh done: %s",
                     "data changed, features and predictions rebuilt" if changed else "no changes")
        except Exception:
            log.exception("refresh failed; will retry")
        log_monitoring()           
        sleep_for = next_sleep()
        log.info("next refresh in %d minutes", sleep_for // 60)
        time.sleep(sleep_for)


if __name__ == "__main__":
    main()