"""Tests for the three new Cradlewise expansion automations.

Covers:
  - YAML structural integrity (required fields, correct trigger/condition/action shapes)
  - Jinja2 condition template logic (nap-length gate, nap-count gate)
  - Variable template rendering (nap_mins, timestamps, total_sleep_h, pluralisation)
  - Notification message content and URL targets
  - Auto-soothe timing constants (2-min trigger, 5-min delay)
  - Entity/service reference spot-checks against known configuration

Running:
  source venv/bin/activate && pytest tests/test_cradlewise_automations.py -v
"""

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
import yaml

# ── Fixtures ──────────────────────────────────────────────────────────────────

AUTOMATIONS_PATH = Path(__file__).parent.parent / "config" / "automations.yaml"
CONFIGURATION_PATH = Path(__file__).parent.parent / "config" / "configuration.yaml"

TIMELAPSE_ID = "cradlewise_nap_timelapse"
SUMMARY_ID = "cradlewise_daily_summary"
SOOTHE_ID = "cradlewise_auto_soothe"
CRY_ALERT_ID = "cradlewise_cry_alert"

NEW_AUTOMATION_IDS = [TIMELAPSE_ID, SUMMARY_ID, SOOTHE_ID, CRY_ALERT_ID]


@pytest.fixture(scope="module")
def automations() -> list[dict]:
    return yaml.safe_load(AUTOMATIONS_PATH.read_text())


@pytest.fixture(scope="module")
def configuration() -> dict:
    # HA tags (!include, !secret) are not valid YAML — strip them before parsing.
    raw = CONFIGURATION_PATH.read_text()
    raw = re.sub(r"!include\s+\S+", '""', raw)
    raw = re.sub(r"!secret\s+\S+", '""', raw)
    return yaml.safe_load(raw)


def find_auto(automations: list[dict], auto_id: str) -> dict:
    for a in automations:
        if a.get("id") == auto_id:
            return a
    pytest.fail(f"Automation '{auto_id}' not found in automations.yaml")


# ── Jinja2 test harness ───────────────────────────────────────────────────────


def _make_env(state_map: dict[str, str]):
    """Return a Jinja2 Environment that mimics the HA template API."""
    import jinja2

    def states(entity_id: str) -> str:
        return state_map.get(entity_id, "unknown")

    def as_timestamp(val: Any) -> float:
        if isinstance(val, (int, float)):
            return float(val)
        try:
            dt = datetime.fromisoformat(str(val).strip())
            return dt.timestamp()
        except (ValueError, TypeError):
            return 0.0

    def float_filter(val, default=0):
        try:
            return float(val)
        except (ValueError, TypeError):
            return float(default)

    def int_filter(val, default=0):
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return int(default)

    env = jinja2.Environment(undefined=jinja2.Undefined)
    env.globals.update({"states": states, "as_timestamp": as_timestamp})
    env.filters.update({"float": float_filter, "int": int_filter})
    return env


def render(template_str: str, state_map: dict[str, str], extra_vars: dict | None = None) -> str:
    env = _make_env(state_map)
    tmpl = env.from_string(template_str)
    return tmpl.render(**(extra_vars or {})).strip()


# ── Structural: all three IDs present ────────────────────────────────────────


@pytest.mark.parametrize("auto_id", NEW_AUTOMATION_IDS)
def test_automation_exists(automations, auto_id):
    find_auto(automations, auto_id)  # fails the test if absent


@pytest.mark.parametrize("auto_id", NEW_AUTOMATION_IDS)
def test_required_top_level_fields(automations, auto_id):
    a = find_auto(automations, auto_id)
    for field in ("id", "alias", "trigger", "action", "mode"):
        assert field in a, f"'{auto_id}' missing field '{field}'"


@pytest.mark.parametrize("auto_id", NEW_AUTOMATION_IDS)
def test_mode_is_single(automations, auto_id):
    a = find_auto(automations, auto_id)
    assert a["mode"] == "single"


# ── Structural: nap timelapse ─────────────────────────────────────────────────


def test_timelapse_trigger_entity(automations):
    a = find_auto(automations, TIMELAPSE_ID)
    triggers = a["trigger"]
    assert any(
        t.get("entity_id") == "sensor.cradlewise_avo_last_nap_ended"
        for t in triggers
    )


def test_timelapse_has_template_condition(automations):
    a = find_auto(automations, TIMELAPSE_ID)
    conditions = a.get("condition", [])
    assert any(c.get("condition") == "template" for c in conditions)


def test_timelapse_action_calls_frigate_rest_command(automations):
    a = find_auto(automations, TIMELAPSE_ID)
    services = [step.get("service", "") for step in a["action"] if isinstance(step, dict)]
    assert "rest_command.frigate_export_nap" in services


def test_timelapse_action_updates_input_text(automations):
    a = find_auto(automations, TIMELAPSE_ID)
    services = [step.get("service", "") for step in a["action"] if isinstance(step, dict)]
    assert "input_text.set_value" in services


def test_timelapse_action_notifies_all_three_devices(automations):
    a = find_auto(automations, TIMELAPSE_ID)
    notify_services = [
        s for s in (step.get("service", "") for step in a["action"] if isinstance(step, dict))
        if s.startswith("notify.")
    ]
    assert len(notify_services) == 3, f"Expected 3 notify calls, got {len(notify_services)}: {notify_services}"


def test_timelapse_notification_url_points_to_frigate(automations):
    a = find_auto(automations, TIMELAPSE_ID)
    for step in a["action"]:
        if not isinstance(step, dict):
            continue
        data = step.get("data", {})
        nested = data.get("data", {})
        if "url" in nested:
            assert "frigate" in nested["url"].lower() or "ccab4aaf" in nested["url"], (
                f"Unexpected URL: {nested['url']}"
            )


def test_timelapse_rest_command_defined_in_configuration(configuration):
    rest_commands = configuration.get("rest_command", {})
    assert "frigate_export_nap" in rest_commands, (
        "rest_command.frigate_export_nap must be defined in configuration.yaml"
    )


def test_timelapse_input_text_defined_in_configuration(configuration):
    input_texts = configuration.get("input_text", {})
    assert "cradlewise_last_timelapse" in input_texts, (
        "input_text.cradlewise_last_timelapse must be defined in configuration.yaml"
    )


# ── Template logic: nap timelapse condition ───────────────────────────────────

_T0 = "2026-06-18T10:00:00+00:00"  # nap start
_T4 = "2026-06-18T10:04:00+00:00"  # 4 min later
_T5 = "2026-06-18T10:05:00+00:00"  # 5 min later
_T45 = "2026-06-18T10:45:00+00:00"  # 45 min later

_CONDITION_TEMPLATE = """\
{% set nap_start = states('sensor.cradlewise_avo_last_nap_started') %}
{% set nap_end = states('sensor.cradlewise_avo_last_nap_ended') %}
{% if nap_start not in ['unknown', 'unavailable', 'none', '']
   and nap_end not in ['unknown', 'unavailable', 'none', ''] %}
  {% set dur_min = ((as_timestamp(nap_end) - as_timestamp(nap_start)) / 60) | int %}
  {{ dur_min >= 5 }}
{% else %}
  false
{% endif %}"""


@pytest.mark.parametrize("start,end,expected_pass", [
    (_T0, _T5, True),   # exactly 5 min → pass
    (_T0, _T45, True),  # 45 min → pass
    (_T0, _T4, False),  # 4 min → blocked
    # Both unknown → blocked
    ("unknown", "unknown", False),
    ("unavailable", _T5, False),
    (_T0, "unavailable", False),
    ("", _T5, False),
    (_T0, "", False),
])
def test_timelapse_condition_gate(start, end, expected_pass):
    states = {
        "sensor.cradlewise_avo_last_nap_started": start,
        "sensor.cradlewise_avo_last_nap_ended": end,
    }
    result = render(_CONDITION_TEMPLATE, states).lower()
    if expected_pass:
        assert result == "true", f"Expected True for start={start!r} end={end!r}, got {result!r}"
    else:
        assert result == "false", f"Expected False for start={start!r} end={end!r}, got {result!r}"


def test_timelapse_condition_boundary_just_under_five_minutes():
    """4 min 59 sec should NOT pass — integer truncation clips to 4."""
    start = "2026-06-18T10:00:00+00:00"
    end = "2026-06-18T10:04:59+00:00"
    states = {
        "sensor.cradlewise_avo_last_nap_started": start,
        "sensor.cradlewise_avo_last_nap_ended": end,
    }
    result = render(_CONDITION_TEMPLATE, states).lower()
    assert result == "false"


# ── Template logic: nap timelapse variable rendering ─────────────────────────

_NAP_MINS_TEMPLATE = """\
{{ ((as_timestamp(states('sensor.cradlewise_avo_last_nap_ended'))
     - as_timestamp(states('sensor.cradlewise_avo_last_nap_started'))) / 60) | round(0) | int }}"""


@pytest.mark.parametrize("start,end,expected_mins", [
    (_T0, _T45, 45),
    (_T0, _T5, 5),
    (_T0, "2026-06-18T11:30:00+00:00", 90),
])
def test_nap_mins_template(start, end, expected_mins):
    states = {
        "sensor.cradlewise_avo_last_nap_started": start,
        "sensor.cradlewise_avo_last_nap_ended": end,
    }
    result = int(render(_NAP_MINS_TEMPLATE, states))
    assert result == expected_mins


def test_nap_start_ts_is_unix_epoch():
    states = {"sensor.cradlewise_avo_last_nap_started": _T0}
    tmpl = "{{ as_timestamp(states('sensor.cradlewise_avo_last_nap_started')) | int }}"
    result = int(render(tmpl, states))
    expected = int(datetime.fromisoformat(_T0).timestamp())
    assert result == expected


# ── Structural: daily summary ─────────────────────────────────────────────────


def test_summary_trigger_is_time_at_2000(automations):
    a = find_auto(automations, SUMMARY_ID)
    triggers = a["trigger"]
    assert any(t.get("at") == "20:00:00" for t in triggers), (
        f"Expected time trigger at 20:00:00, got: {[t.get('at') for t in triggers]}"
    )


def test_summary_condition_is_numeric_state_above_zero(automations):
    a = find_auto(automations, SUMMARY_ID)
    conditions = a.get("condition", [])
    assert any(
        c.get("condition") == "numeric_state"
        and c.get("entity_id") == "sensor.cradlewise_avo_nap_count_today"
        and c.get("above") == 0
        for c in conditions
    ), f"Expected numeric_state condition on nap_count_today above 0; got: {conditions}"


def test_summary_notifies_all_three_devices(automations):
    a = find_auto(automations, SUMMARY_ID)
    notify_services = [
        s for s in (step.get("service", "") for step in a["action"] if isinstance(step, dict))
        if s.startswith("notify.")
    ]
    assert len(notify_services) == 3


def test_summary_notification_url_points_to_naps_care(automations):
    a = find_auto(automations, SUMMARY_ID)
    for step in a["action"]:
        if not isinstance(step, dict):
            continue
        url = step.get("data", {}).get("data", {}).get("url", "")
        if url:
            assert "naps" in url or "cradlewise" in url, f"Unexpected dashboard URL: {url}"


# ── Template logic: daily summary pluralisation ──────────────────────────────

_LABEL_TEMPLATE = "{{ 'nap' if nap_count == 1 else 'naps' }}"
_MESSAGE_TEMPLATE = (
    "{{ nap_count }} {{ nap_label }} · {{ total_sleep_h }}h total sleep "
    "· longest {{ longest_nap }} min · {{ efficiency }}% efficient"
)


@pytest.mark.parametrize("count,expected_label", [
    (1, "nap"),
    (2, "naps"),
    (3, "naps"),
    (10, "naps"),
])
def test_summary_nap_label_pluralisation(count, expected_label):
    result = render(_LABEL_TEMPLATE, {}, {"nap_count": count})
    assert result == expected_label


def test_summary_total_sleep_converts_minutes_to_hours():
    # 180 min of total_sleep_today → 3.0h
    tmpl = "{{ (states('sensor.cradlewise_avo_total_sleep_today') | float(0) / 60) | round(1) }}"
    result = render(tmpl, {"sensor.cradlewise_avo_total_sleep_today": "180"})
    assert float(result) == pytest.approx(3.0)


def test_summary_total_sleep_handles_unknown_state():
    tmpl = "{{ (states('sensor.cradlewise_avo_total_sleep_today') | float(0) / 60) | round(1) }}"
    result = render(tmpl, {"sensor.cradlewise_avo_total_sleep_today": "unknown"})
    assert float(result) == pytest.approx(0.0)


def test_summary_message_contains_all_fields():
    result = render(
        _MESSAGE_TEMPLATE,
        {},
        {"nap_count": 2, "nap_label": "naps", "total_sleep_h": 3.5, "longest_nap": 90, "efficiency": 82},
    )
    assert "2 naps" in result
    assert "3.5h" in result
    assert "90 min" in result
    assert "82%" in result


def test_summary_message_singular_nap():
    result = render(
        _MESSAGE_TEMPLATE,
        {},
        {"nap_count": 1, "nap_label": "nap", "total_sleep_h": 1.5, "longest_nap": 90, "efficiency": 75},
    )
    assert "1 nap " in result  # singular, not "1 naps"
    assert "naps" not in result


# ── Structural: auto-soothe ───────────────────────────────────────────────────


def test_soothe_trigger_entity(automations):
    a = find_auto(automations, SOOTHE_ID)
    triggers = a["trigger"]
    assert any(
        t.get("entity_id") == "binary_sensor.cradlewise_avo_baby_needs_attention"
        for t in triggers
    )


def test_soothe_trigger_to_state_on(automations):
    a = find_auto(automations, SOOTHE_ID)
    triggers = a["trigger"]
    assert any(t.get("to") == "on" for t in triggers), (
        "Trigger should fire on 'on' state"
    )


def test_soothe_trigger_for_two_minutes(automations):
    a = find_auto(automations, SOOTHE_ID)
    triggers = a["trigger"]
    assert any(t.get("for") == "00:02:00" for t in triggers), (
        "Trigger should require 2-minute sustained state before firing"
    )


def test_soothe_condition_checks_baby_present(automations):
    a = find_auto(automations, SOOTHE_ID)
    conditions = a.get("condition", [])
    assert any(
        c.get("entity_id") == "binary_sensor.cradlewise_avo_baby_present"
        and c.get("state") == "on"
        for c in conditions
    )


def test_soothe_condition_checks_rocking_off(automations):
    a = find_auto(automations, SOOTHE_ID)
    conditions = a.get("condition", [])
    assert any(
        c.get("entity_id") == "switch.cradlewise_avo_rocking"
        and c.get("state") == "off"
        for c in conditions
    )


def test_soothe_action_starts_rocking(automations):
    a = find_auto(automations, SOOTHE_ID)
    actions = [step for step in a["action"] if isinstance(step, dict)]
    turn_on = next(
        (s for s in actions if s.get("service") == "switch.turn_on"),
        None,
    )
    assert turn_on is not None
    rocking_id = (
        turn_on.get("target", {}).get("entity_id")
        or turn_on.get("data", {}).get("entity_id")
    )
    assert rocking_id == "switch.cradlewise_avo_rocking"


def test_soothe_action_delay_is_five_minutes(automations):
    a = find_auto(automations, SOOTHE_ID)
    delays = [step.get("delay") for step in a["action"] if isinstance(step, dict) and "delay" in step]
    assert "00:05:00" in delays, f"Expected 5-min delay, found: {delays}"


def test_soothe_action_auto_off_checks_settled(automations):
    """After the delay, the automation should verify baby settled before turning off."""
    a = find_auto(automations, SOOTHE_ID)
    # Find the condition step inside the action sequence (not the pre-condition)
    in_action_conditions = [
        step for step in a["action"]
        if isinstance(step, dict) and step.get("condition") == "state"
    ]
    assert any(
        c.get("entity_id") == "binary_sensor.cradlewise_avo_baby_needs_attention"
        and c.get("state") == "off"
        for c in in_action_conditions
    ), "Action should check that baby_needs_attention is off before stopping rocking"


def test_soothe_action_stops_rocking_on_settle(automations):
    a = find_auto(automations, SOOTHE_ID)
    services = [step.get("service", "") for step in a["action"] if isinstance(step, dict)]
    assert "switch.turn_off" in services


# ── Structural: cry alert ─────────────────────────────────────────────────────


def _choose_branches(automation: dict) -> list[dict]:
    """Return the list of choose-branches in the automation's action sequence."""
    for step in automation["action"]:
        if isinstance(step, dict) and "choose" in step:
            return step["choose"]
    return []


def _branch_for_state(automation: dict, state: str) -> dict | None:
    """Find the choose-branch gated on baby_crying == `state`."""
    for branch in _choose_branches(automation):
        for cond in branch.get("conditions", []):
            if (
                cond.get("entity_id") == "binary_sensor.cradlewise_avo_baby_crying"
                and cond.get("state") == state
            ):
                return branch
    return None


def test_cry_alert_trigger_entity(automations):
    a = find_auto(automations, CRY_ALERT_ID)
    assert any(
        t.get("entity_id") == "binary_sensor.cradlewise_avo_baby_crying"
        for t in a["trigger"]
    )


def test_cry_alert_uses_choose_with_two_branches(automations):
    a = find_auto(automations, CRY_ALERT_ID)
    branches = _choose_branches(a)
    assert len(branches) == 2, f"Expected on/off branches, got {len(branches)}"


def test_cry_alert_has_on_and_off_branches(automations):
    a = find_auto(automations, CRY_ALERT_ID)
    assert _branch_for_state(a, "on") is not None, "Missing crying-started branch"
    assert _branch_for_state(a, "off") is not None, "Missing baby-settled branch"


def test_cry_alert_on_branch_notifies(automations):
    a = find_auto(automations, CRY_ALERT_ID)
    branch = _branch_for_state(a, "on")
    notifies = [s for s in branch["sequence"] if s.get("service", "").startswith("notify.")]
    assert len(notifies) >= 1


def test_cry_alert_off_branch_notifies(automations):
    a = find_auto(automations, CRY_ALERT_ID)
    branch = _branch_for_state(a, "off")
    notifies = [s for s in branch["sequence"] if s.get("service", "").startswith("notify.")]
    assert len(notifies) >= 1


def test_cry_alert_uses_consistent_tag_for_replacement(automations):
    """Both branches must share one notification tag so alerts replace, not stack."""
    a = find_auto(automations, CRY_ALERT_ID)
    tags = set()
    for branch in _choose_branches(a):
        for step in branch["sequence"]:
            tag = step.get("data", {}).get("data", {}).get("tag")
            if tag:
                tags.add(tag)
    assert tags == {"cradlewise_cry"}, f"Expected single shared tag, got {tags}"


def test_cry_alert_on_branch_links_to_dashboard(automations):
    a = find_auto(automations, CRY_ALERT_ID)
    branch = _branch_for_state(a, "on")
    urls = [
        step.get("data", {}).get("data", {}).get("url", "")
        for step in branch["sequence"]
    ]
    assert any("cradlewise" in u for u in urls), f"Expected a cradlewise dashboard link; got {urls}"


# ── Cross-cutting: no duplicate automation IDs ────────────────────────────────


def test_no_duplicate_automation_ids(automations):
    ids = [a.get("id") for a in automations if a.get("id")]
    assert len(ids) == len(set(ids)), f"Duplicate IDs: {[i for i in ids if ids.count(i) > 1]}"
