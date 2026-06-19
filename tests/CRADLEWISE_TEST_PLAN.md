# Cradlewise Expansion — Test & Validation Plan

Covers the features added in the current revision: nap timelapse export, daily
sleep summary, auto-soothe, two-way audio, and the cry-detection sensor + alert.

## 1. Scope

| Feature | Surface | Where tested |
|---|---|---|
| Nap timelapse export | `automations.yaml`, `rest_command`, `input_text` | `test_cradlewise_automations.py` |
| Daily sleep summary (8pm) | `automations.yaml` | `test_cradlewise_automations.py` |
| Auto-soothe on attention | `automations.yaml` | `test_cradlewise_automations.py` |
| Cry alert notification | `automations.yaml` | `test_cradlewise_automations.py` |
| Cry-detection DSP | `cry_dsp.py` (integration) | `test_cry_detection.py` |
| `baby_crying` sensor | `binary_sensor.py` (integration) | manual + DSP unit tests |
| Two-way audio (`cradlewise.talk`) | `webrtc.py`, `__init__.py` | manual |
| rsync push carve-out for cradlewise | `.rsync-excludes-push` | `test_rsync_excludes.py` |

## 2. Automated tests

### 2.1 Running

The repo's global pytest config gates on `tools/` coverage (`--cov-fail-under=80`).
Run the Cradlewise suites with coverage disabled:

```bash
source venv/bin/activate
pytest tests/test_cry_detection.py tests/test_cradlewise_automations.py tests/test_rsync_excludes.py --no-cov -v
```

Full suite (all 146 tests): `pytest --no-cov -q`

### 2.2 `test_cry_detection.py` — cry-detection DSP (numpy only)

The DSP is isolated in `cry_dsp.py` (no HA/aiortc imports) so it runs in CI.
Synthetic-signal coverage:

- **Positive:** harmonic cry stacks across fundamentals 400–800 Hz; single in-band tone; list input; 16 kHz input (sample-rate independence).
- **Negative (false-positive rejection):** silence, sub-threshold amplitude, white noise (SFM gate), 120 Hz hum (centroid-low gate), 9 kHz hiss (centroid-high gate), empty array.
- **`CryDetector` debounce/voting:** partial-feed buffering across window boundaries, 3-of-5 majority vote to flip ON, 2 windows insufficient, single stray window ignored, clears after baby settles, returns `None` when state unchanged, 96 kHz decimation.
- **Constants sanity:** vote threshold is a strict majority; centroid/SFM/band bounds are well-formed.

### 2.3 `test_cradlewise_automations.py` — automation YAML logic

- Structural: all four automation IDs present, required fields, `mode: single`, no duplicate IDs.
- Nap timelapse: trigger entity, template condition, Frigate REST call, `input_text` update, 3 notify targets, Frigate URL, `rest_command`/`input_text` defined in `configuration.yaml`.
- Timelapse Jinja2 logic: ≥5-min nap gate (incl. 4:59 boundary), unknown/unavailable/empty handling, `nap_mins` rounding, Unix-epoch timestamps.
- Daily summary: 20:00 trigger, `nap_count_today > 0` gate, 3 notify targets, dashboard URL, minutes→hours conversion, unknown handling, nap/naps pluralisation, message field assembly.
- Auto-soothe: 2-min sustained trigger, baby-present + rocking-off preconditions, start-rock action, 5-min delay, settled re-check, stop-rock.
- Cry alert: trigger entity, `choose` with on/off branches, both branches notify, shared `cradlewise_cry` tag (replace not stack), dashboard link.

### 2.4 `test_rsync_excludes.py` — deploy safety

Confirms `make push` updates config, never overwrites remote `.storage/`, and
preserves remote `backups/`, `www/`, and **all** of `custom_components/` while
the cradlewise carve-out still syncs (verified manually, see §3.4).

## 3. Manual / integration validation

These require the live HA instance and the crib; they are not in CI.

### 3.1 Cry sensor end-to-end
1. Confirm `binary_sensor.cradlewise_avo_baby_crying` exists and reads `off`.
2. Play an infant-cry recording near the crib mic (or trigger a real cry).
3. Within ~3 s (3× 1-second windows) the sensor flips `on`; the
   **Notify when baby is crying** automation fires a push tagged `cradlewise_cry`.
4. On silence, sensor clears `off` within ~3 s and a "Baby Settled" push replaces the alert.
5. False-positive check: run a white-noise machine — sensor must stay `off`.

### 3.2 Two-way audio (`cradlewise.talk`)
1. Developer Tools → Actions → `cradlewise.talk` with `media_url` to a short clip.
2. Confirm audio plays from the crib speaker; check logs for "sent N bytes PCM".

### 3.3 Nap timelapse
1. After a ≥5-min nap ends, confirm a Frigate export job starts and
   `input_text.cradlewise_last_timelapse` updates; push notification links to Frigate.
2. Negative: a <5-min nap produces no export (condition gate).

### 3.4 Deploy carve-out (run before trusting `make push`)
```bash
# cradlewise pushes + stale cradlewise files pruned; other components untouched
rsync -avz --delete --exclude-from=.rsync-excludes-push <local>/ <remote>/
```
Expect: cradlewise files updated, sibling components and loose files preserved.

## 4. Known limitations / non-CI gaps

- Cry DSP is validated against **synthetic** signals; real-world thresholds
  (`SFM_MAX`, centroid band, `CRY_BAND_RATIO_MIN`) should be tuned against
  recorded crib audio. Tune constants in `cry_dsp.py`; tests assert behaviour, not exact thresholds.
- Integration modules (`camera.py`, `webrtc.py`, `binary_sensor.py`) require a
  full HA restart to reload — config-entry reload does **not** reimport Python
  modules; stale `.pyc` can mask changes.
- `webrtc.py` cert loading and `sleep_analytics.py` file read run blocking calls
  in the event loop (HA warnings, pre-existing); candidates for executor offload.
