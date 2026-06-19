"""Unit tests for local sleep analytics (SleepTracker)."""
import json
import sys
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(
    0,
    str(Path(__file__).parent.parent / "config" / "custom_components" / "cradlewise"),
)
from sleep_analytics import SleepTracker  # noqa: E402


# ── Helpers ────────────────────────────────────────────────────────────────────

_TODAY = date(2026, 5, 25)
_TOMORROW = date(2026, 5, 26)


def _dt(hour: int, minute: int = 0, day: date = _TODAY) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=timezone.utc)


@contextmanager
def _freeze(now: datetime):
    """Pin date.today() and datetime.now() inside sleep_analytics."""
    with (
        patch("sleep_analytics.date") as mock_date,
        patch("sleep_analytics.datetime") as mock_dt,
    ):
        mock_date.today.return_value = now.date()
        mock_dt.now.return_value = now
        mock_dt.fromisoformat.side_effect = datetime.fromisoformat
        yield mock_dt, mock_date


@pytest.fixture
def tracker(tmp_path):
    with _freeze(_dt(6)):
        return SleepTracker(tmp_path / "sleep.json")


# ── Initial state ──────────────────────────────────────────────────────────────

def test_initial_state(tracker):
    assert tracker.nap_count == 0
    assert tracker.total_sleep_minutes == 0.0
    assert tracker.longest_nap_minutes is None
    assert tracker.last_nap_start is None
    assert tracker.last_nap_end is None
    assert tracker.soothing_count == 0


# ── Nap detection ──────────────────────────────────────────────────────────────

def test_nap_start_and_end(tracker):
    # 08:00 — baby falls asleep
    with _freeze(_dt(8, 0)):
        tracker.on_state_update({"babySleepState": 4})
    assert tracker.nap_count == 0  # not yet completed

    # 09:30 — baby wakes up (90-minute nap)
    with _freeze(_dt(9, 30)):
        tracker.on_state_update({"babySleepState": 1})

    assert tracker.nap_count == 1
    assert tracker.total_sleep_minutes == 90.0
    assert tracker.longest_nap_minutes == 90.0


def test_nap_awake_state_1_ends_nap(tracker):
    with _freeze(_dt(8)):
        tracker.on_state_update({"babySleepState": 4})
    with _freeze(_dt(9)):
        tracker.on_state_update({"babySleepState": 1})
    assert tracker.nap_count == 1


def test_nap_stirring_state_ends_nap(tracker):
    with _freeze(_dt(8)):
        tracker.on_state_update({"babySleepState": 4})
    with _freeze(_dt(9)):
        tracker.on_state_update({"babySleepState": 2})  # stirring
    assert tracker.nap_count == 1


def test_nap_away_state_ends_nap(tracker):
    with _freeze(_dt(8)):
        tracker.on_state_update({"babySleepState": 4})
    with _freeze(_dt(9)):
        tracker.on_state_update({"babySleepState": 0})  # away
    assert tracker.nap_count == 1


def test_updates_during_sleep_dont_duplicate_nap(tracker):
    with _freeze(_dt(8)):
        tracker.on_state_update({"babySleepState": 4})
    with _freeze(_dt(8, 30)):
        tracker.on_state_update({"babySleepState": 4})  # still asleep
    with _freeze(_dt(9)):
        tracker.on_state_update({"babySleepState": 4})  # still asleep
    with _freeze(_dt(9, 30)):
        tracker.on_state_update({"babySleepState": 1})  # wake up

    assert tracker.nap_count == 1
    assert tracker.total_sleep_minutes == 90.0


def test_unknown_sleep_state_none_does_not_start_nap(tracker):
    with _freeze(_dt(8)):
        tracker.on_state_update({"babySleepState": None})
    with _freeze(_dt(9)):
        tracker.on_state_update({"babySleepState": 1})
    assert tracker.nap_count == 0


# ── Short-nap filtering ────────────────────────────────────────────────────────

def test_sub_minute_nap_is_ignored(tracker):
    start = _dt(8, 0)
    end = datetime(2026, 5, 25, 8, 0, 30, tzinfo=timezone.utc)  # 30 seconds
    with _freeze(start):
        tracker.on_state_update({"babySleepState": 4})
    with _freeze(end):
        tracker.on_state_update({"babySleepState": 1})
    assert tracker.nap_count == 0


def test_exactly_one_minute_nap_is_recorded(tracker):
    with _freeze(_dt(8, 0)):
        tracker.on_state_update({"babySleepState": 4})
    end = datetime(2026, 5, 25, 8, 1, tzinfo=timezone.utc)
    with _freeze(end):
        tracker.on_state_update({"babySleepState": 1})
    assert tracker.nap_count == 1


# ── Multiple naps ──────────────────────────────────────────────────────────────

def test_multiple_naps_accumulate(tracker):
    # Nap 1: 08:00–09:00 (60 min)
    with _freeze(_dt(8)):
        tracker.on_state_update({"babySleepState": 4})
    with _freeze(_dt(9)):
        tracker.on_state_update({"babySleepState": 1})

    # Nap 2: 13:00–14:30 (90 min)
    with _freeze(_dt(13)):
        tracker.on_state_update({"babySleepState": 4})
    with _freeze(_dt(14, 30)):
        tracker.on_state_update({"babySleepState": 1})

    assert tracker.nap_count == 2
    assert tracker.total_sleep_minutes == 150.0
    assert tracker.longest_nap_minutes == 90.0


def test_longest_nap_picks_max(tracker):
    with _freeze(_dt(8)):
        tracker.on_state_update({"babySleepState": 4})
    with _freeze(_dt(8, 30)):
        tracker.on_state_update({"babySleepState": 1})  # 30 min

    with _freeze(_dt(13)):
        tracker.on_state_update({"babySleepState": 4})
    with _freeze(_dt(15)):
        tracker.on_state_update({"babySleepState": 1})  # 120 min

    with _freeze(_dt(20)):
        tracker.on_state_update({"babySleepState": 4})
    with _freeze(_dt(21)):
        tracker.on_state_update({"babySleepState": 1})  # 60 min

    assert tracker.longest_nap_minutes == 120.0


# ── Ongoing nap ────────────────────────────────────────────────────────────────

def test_total_sleep_includes_ongoing_nap(tracker):
    # Completed nap: 30 min
    with _freeze(_dt(8)):
        tracker.on_state_update({"babySleepState": 4})
    with _freeze(_dt(8, 30)):
        tracker.on_state_update({"babySleepState": 1})

    # Start second nap at 13:00; check total at 13:45 (ongoing 45 min)
    with _freeze(_dt(13)):
        tracker.on_state_update({"babySleepState": 4})

    with _freeze(_dt(13, 45)):
        with patch("sleep_analytics.datetime") as mock_dt:
            mock_dt.now.return_value = _dt(13, 45)
            mock_dt.fromisoformat.side_effect = datetime.fromisoformat
            total = tracker.total_sleep_minutes

    assert total == 75.0  # 30 completed + 45 ongoing


def test_last_nap_start_returns_ongoing_when_no_completed_naps(tracker):
    with _freeze(_dt(8)):
        tracker.on_state_update({"babySleepState": 4})
    assert tracker.last_nap_start == _dt(8)


def test_last_nap_end_is_none_during_ongoing_nap(tracker):
    with _freeze(_dt(8)):
        tracker.on_state_update({"babySleepState": 4})
    assert tracker.last_nap_end is None


# ── Timestamps ────────────────────────────────────────────────────────────────

def test_last_nap_timestamps(tracker):
    with _freeze(_dt(8)):
        tracker.on_state_update({"babySleepState": 4})
    with _freeze(_dt(9, 15)):
        tracker.on_state_update({"babySleepState": 1})

    assert tracker.last_nap_start == _dt(8)
    assert tracker.last_nap_end == _dt(9, 15)


def test_last_nap_timestamps_update_to_most_recent(tracker):
    with _freeze(_dt(8)):
        tracker.on_state_update({"babySleepState": 4})
    with _freeze(_dt(9)):
        tracker.on_state_update({"babySleepState": 1})

    with _freeze(_dt(13)):
        tracker.on_state_update({"babySleepState": 4})
    with _freeze(_dt(14)):
        tracker.on_state_update({"babySleepState": 1})

    assert tracker.last_nap_start == _dt(13)
    assert tracker.last_nap_end == _dt(14)


# ── Soothing count ─────────────────────────────────────────────────────────────

def test_soothing_increments_on_leading_edge(tracker):
    with _freeze(_dt(8)):
        tracker.on_state_update({"isCribHelping": True})
    assert tracker.soothing_count == 1


def test_soothing_does_not_double_count_sustained_true(tracker):
    with _freeze(_dt(8)):
        tracker.on_state_update({"isCribHelping": True})
    with _freeze(_dt(8, 5)):
        tracker.on_state_update({"isCribHelping": True})
    with _freeze(_dt(8, 10)):
        tracker.on_state_update({"isCribHelping": True})
    assert tracker.soothing_count == 1


def test_soothing_counts_separate_events(tracker):
    with _freeze(_dt(8)):
        tracker.on_state_update({"isCribHelping": True})
    with _freeze(_dt(8, 15)):
        tracker.on_state_update({"isCribHelping": False})
    with _freeze(_dt(9)):
        tracker.on_state_update({"isCribHelping": True})
    assert tracker.soothing_count == 2


def test_soothing_missing_key_treated_as_false(tracker):
    with _freeze(_dt(8)):
        tracker.on_state_update({})  # isCribHelping absent
    with _freeze(_dt(8, 5)):
        tracker.on_state_update({"isCribHelping": True})
    assert tracker.soothing_count == 1


# ── Day reset ──────────────────────────────────────────────────────────────────

def test_day_reset_clears_all_data(tmp_path):
    with _freeze(_dt(8)):
        tracker = SleepTracker(tmp_path / "sleep.json")
        tracker.on_state_update({"babySleepState": 4})
    with _freeze(_dt(9)):
        tracker.on_state_update({"babySleepState": 1})
        tracker.on_state_update({"isCribHelping": True})

    assert tracker.nap_count == 1
    assert tracker.soothing_count == 1

    # Next day — first update triggers reset
    with _freeze(datetime(_TOMORROW.year, _TOMORROW.month, _TOMORROW.day, 6, tzinfo=timezone.utc)):
        tracker.on_state_update({"babySleepState": 1})

    assert tracker.nap_count == 0
    assert tracker.total_sleep_minutes == 0.0
    assert tracker.soothing_count == 0
    assert tracker.last_nap_start is None


# ── Persistence ────────────────────────────────────────────────────────────────

def test_persistence_saves_and_reloads(tmp_path):
    path = tmp_path / "sleep.json"

    with _freeze(_dt(8)):
        t1 = SleepTracker(path)
        t1.on_state_update({"babySleepState": 4})
    with _freeze(_dt(9)):
        t1.on_state_update({"babySleepState": 1})
        t1.on_state_update({"isCribHelping": True})

    # New tracker instance loads from same file
    with _freeze(_dt(10)):
        t2 = SleepTracker(path)

    assert t2.nap_count == 1
    assert t2.total_sleep_minutes == 60.0
    assert t2.soothing_count == 1
    assert t2.last_nap_start == _dt(8)
    assert t2.last_nap_end == _dt(9)


def test_persistence_ignores_yesterday_data(tmp_path):
    path = tmp_path / "sleep.json"

    # Write yesterday's data manually
    path.write_text(json.dumps({
        "date": "2026-05-24",
        "naps": [{"start": "2026-05-24T08:00:00+00:00", "end": "2026-05-24T09:00:00+00:00", "minutes": 60.0}],
        "current_nap_start": None,
        "soothing_count": 3,
    }))

    with _freeze(_dt(6)):
        tracker = SleepTracker(path)

    assert tracker.nap_count == 0
    assert tracker.soothing_count == 0


def test_persistence_resumes_nap_in_progress(tmp_path):
    """HA restart mid-nap: current_nap_start is restored from storage."""
    path = tmp_path / "sleep.json"

    # HA restarts at 9:00 while baby has been asleep since 8:00
    path.write_text(json.dumps({
        "date": _TODAY.isoformat(),
        "naps": [],
        "current_nap_start": "2026-05-25T08:00:00+00:00",
        "soothing_count": 0,
    }))

    with _freeze(_dt(9)):
        tracker = SleepTracker(path)

    # Baby wakes at 10:00 — nap should be 8:00–10:00 = 120 min
    with _freeze(_dt(10)):
        tracker.on_state_update({"babySleepState": 1})

    assert tracker.nap_count == 1
    assert tracker.total_sleep_minutes == 120.0


def test_persistence_file_corrupt_starts_fresh(tmp_path):
    path = tmp_path / "sleep.json"
    path.write_text("not valid json {{{")

    with _freeze(_dt(6)):
        tracker = SleepTracker(path)

    assert tracker.nap_count == 0


def test_persistence_missing_file_starts_fresh(tmp_path):
    with _freeze(_dt(6)):
        tracker = SleepTracker(tmp_path / "nonexistent.json")
    assert tracker.nap_count == 0


# ── Data integrity in persisted file ──────────────────────────────────────────

def test_persisted_file_contains_expected_fields(tmp_path):
    path = tmp_path / "sleep.json"
    with _freeze(_dt(8)):
        tracker = SleepTracker(path)
        tracker.on_state_update({"babySleepState": 4})
    with _freeze(_dt(9)):
        tracker.on_state_update({"babySleepState": 1})

    data = json.loads(path.read_text())
    assert data["date"] == _TODAY.isoformat()
    assert len(data["naps"]) == 1
    assert data["naps"][0]["minutes"] == 60.0
    assert data["current_nap_start"] is None
    assert data["soothing_count"] == 0
