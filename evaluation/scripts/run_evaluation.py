"""
RescueVision AI - Evaluation harness.

Runs real measurements against the existing backend code (no fabricated
numbers): vision detection quality on the four synthetic scenarios, raw
per-frame vision processing latency/FPS, agent policy decision latency and a
decision-table sanity check, and end-to-end (vision + agent) latency.

Everything this script cannot measure locally (live AWS latency/cost/
throughput/utilization) is written to the results JSON as the literal string
"NOT MEASURED" with a reason -- it is never estimated.

Usage (from repo root):
    python evaluation/run_evaluation.py

Or directly:
    python evaluation/scripts/run_evaluation.py
"""
from __future__ import annotations

import json
import platform
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
EVAL_DIR = REPO_ROOT / "evaluation"
RESULTS_DIR = EVAL_DIR / "results"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import cv2  # noqa: E402

from app.agent.policy import AgentPolicy  # noqa: E402
from app.configuration.config import Settings  # noqa: E402
from app.vision.detectors import DETECTORS  # noqa: E402
from app.vision.opencv_processor import OpenCV5Processor  # noqa: E402
from app.vision.pipeline import VisionPipeline  # noqa: E402
from app.vision.temporal_analyzer import TemporalAnalyzer  # noqa: E402
from app.vision.video_source import SyntheticFrameSource  # noqa: E402

INCIDENT_SCENARIOS = ["fire_smoke", "person_down", "route_obstruction"]
ALL_SCENARIOS = INCIDENT_SCENARIOS + ["normal"]

VISION_QUALITY_NUM_FRAMES = 260  # empirically confirmed below to let escalation complete (see notes)
PERF_NUM_FRAMES = 200
FPS = 15.0


def _settings() -> Settings:
    # Plain local-mode settings, identical defaults to backend/tests/conftest.py's
    # fixture, minus the tmp_path storage overrides (this script never touches
    # storage/incident backends, only thresholds/roi/agent_policy/monitoring).
    return Settings(
        storage_backend="local",
        incident_backend="local",
        notification_backend="local",
    )


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = (len(ordered) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(ordered) - 1)
    if f == c:
        return ordered[f]
    return ordered[f] + (ordered[c] - ordered[f]) * (k - f)


def _latency_stats(latencies_ms: list[float]) -> dict:
    return {
        "n": len(latencies_ms),
        "mean_ms": round(statistics.mean(latencies_ms), 4) if latencies_ms else 0.0,
        "median_ms": round(statistics.median(latencies_ms), 4) if latencies_ms else 0.0,
        "p95_ms": round(_percentile(latencies_ms, 95), 4) if latencies_ms else 0.0,
        "min_ms": round(min(latencies_ms), 4) if latencies_ms else 0.0,
        "max_ms": round(max(latencies_ms), 4) if latencies_ms else 0.0,
        "derived_fps_from_mean": round(1000.0 / statistics.mean(latencies_ms), 2) if latencies_ms and statistics.mean(latencies_ms) > 0 else None,
    }


# ---------------------------------------------------------------------------
# 1. Vision detection quality (n=4 synthetic scenarios)
# ---------------------------------------------------------------------------

def run_vision_quality(settings: Settings) -> dict:
    per_scenario = {}
    for scenario in ALL_SCENARIOS:
        detector_scenario = scenario if scenario in INCIDENT_SCENARIOS else settings.default_scenario
        src = SyntheticFrameSource(scenario, num_frames=VISION_QUALITY_NUM_FRAMES, fps=FPS)
        pipeline = VisionPipeline(detector_scenario, settings.thresholds, settings.region_of_interest, region_name=scenario)

        states_seen = set()
        time_to_possible = None
        time_to_confirmed = None
        peak_confidence = 0.0
        frame_of_confirmed = None

        for candidate in pipeline.run(src.frames()):
            states_seen.add(candidate.state)
            peak_confidence = max(peak_confidence, candidate.confidence)
            if candidate.state == "possible" and time_to_possible is None:
                time_to_possible = candidate.timestamp_seconds
            if candidate.state == "confirmed" and time_to_confirmed is None:
                time_to_confirmed = candidate.timestamp_seconds
                frame_of_confirmed = candidate.frame_index

        reached_possible = "possible" in states_seen
        reached_confirmed = "confirmed" in states_seen

        per_scenario[scenario] = {
            "is_incident_scenario": scenario in INCIDENT_SCENARIOS,
            "num_frames_run": VISION_QUALITY_NUM_FRAMES,
            "fps_assumed": FPS,
            "states_seen": sorted(states_seen),
            "reached_possible": reached_possible,
            "reached_confirmed": reached_confirmed,
            "time_to_possible_seconds": time_to_possible,
            "time_to_confirmed_seconds": time_to_confirmed,
            "frame_index_of_first_confirmed": frame_of_confirmed,
            "peak_confidence": round(peak_confidence, 4),
        }

    # Confusion matrix: positive class = "incident scenario reaches confirmed".
    # Ground truth: fire_smoke/person_down/route_obstruction MUST reach confirmed;
    # normal MUST NEVER reach confirmed (or even possible).
    tp = sum(1 for s in INCIDENT_SCENARIOS if per_scenario[s]["reached_confirmed"])
    fn = sum(1 for s in INCIDENT_SCENARIOS if not per_scenario[s]["reached_confirmed"])
    fp = 1 if per_scenario["normal"]["reached_confirmed"] else 0
    tn = 1 if not per_scenario["normal"]["reached_confirmed"] else 0

    normal_false_alarm_possible = per_scenario["normal"]["reached_possible"]

    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    f1 = (2 * precision * recall / (precision + recall)) if precision and recall and (precision + recall) > 0 else (0.0 if precision == 0 or recall == 0 else None)
    fpr = fp / (fp + tn) if (fp + tn) else None
    fnr = fn / (fn + tp) if (fn + tp) else None

    return {
        "methodology": (
            "n=4 synthetic scenario clips only (fire_smoke, person_down, route_obstruction, normal). "
            "This is NOT a statistically meaningful benchmark -- it is an illustrative, fully-reproducible "
            "smoke test of the pipeline's detection logic on deterministic synthetic footage, not a claim "
            "of real-world accuracy. Positive class = 'scenario reaches confirmed state'."
        ),
        "per_scenario": per_scenario,
        "confusion_matrix_n4": {
            "true_positives": tp,
            "false_negatives": fn,
            "false_positives": fp,
            "true_negatives": tn,
            "normal_scenario_reached_possible_state": normal_false_alarm_possible,
        },
        "metrics_n4_illustrative_only": {
            "precision": round(precision, 4) if precision is not None else None,
            "recall": round(recall, 4) if recall is not None else None,
            "f1": round(f1, 4) if f1 is not None else None,
            "false_positive_rate": round(fpr, 4) if fpr is not None else None,
            "false_negative_rate": round(fnr, 4) if fnr is not None else None,
        },
    }


# ---------------------------------------------------------------------------
# 2. Performance: raw per-frame vision cost (process + detect + temporal update)
# ---------------------------------------------------------------------------

def run_vision_frame_latency(settings: Settings) -> dict:
    per_scenario = {}
    for scenario in ALL_SCENARIOS:
        detector_scenario = scenario if scenario in INCIDENT_SCENARIOS else settings.default_scenario
        src = SyntheticFrameSource(scenario, num_frames=PERF_NUM_FRAMES, fps=FPS)
        # Pre-generate frames so synthetic-rendering cost is excluded from the
        # timed region -- we want the vision-processing cost alone.
        frames = list(src.frames())

        processor = OpenCV5Processor(settings.region_of_interest)
        detector = DETECTORS[detector_scenario](settings.thresholds)
        temporal = TemporalAnalyzer(settings.thresholds)

        latencies_ms = []
        for frame in frames:
            t0 = time.perf_counter()
            processed = processor.process(frame.image_bgr, frame.index, frame.timestamp_seconds)
            detection = detector.detect(processed)
            temporal.update(detection, frame.timestamp_seconds)
            t1 = time.perf_counter()
            latencies_ms.append((t1 - t0) * 1000.0)

        per_scenario[scenario] = _latency_stats(latencies_ms)

    return {
        "methodology": (
            f"Timed OpenCV5Processor.process() + scenario detector .detect() + TemporalAnalyzer.update() "
            f"only, per frame, over {PERF_NUM_FRAMES} pre-generated frames per scenario at {FPS} fps synthetic "
            f"source framerate. Synthetic-frame *rendering* time is excluded (frames generated before timing "
            f"starts). Measured on THIS development machine only -- not a universal/hardware-independent number."
        ),
        "per_scenario": per_scenario,
    }


def run_vision_frame_latency_combined(settings: Settings) -> dict:
    """Same measurement as above but pooling all scenarios' per-frame timings
    into one combined latency/FPS figure, since that's the single headline
    number most useful for a capacity-planning read."""
    all_latencies_ms = []
    for scenario in ALL_SCENARIOS:
        detector_scenario = scenario if scenario in INCIDENT_SCENARIOS else settings.default_scenario
        src = SyntheticFrameSource(scenario, num_frames=PERF_NUM_FRAMES, fps=FPS)
        frames = list(src.frames())
        processor = OpenCV5Processor(settings.region_of_interest)
        detector = DETECTORS[detector_scenario](settings.thresholds)
        temporal = TemporalAnalyzer(settings.thresholds)
        for frame in frames:
            t0 = time.perf_counter()
            processed = processor.process(frame.image_bgr, frame.index, frame.timestamp_seconds)
            detection = detector.detect(processed)
            temporal.update(detection, frame.timestamp_seconds)
            t1 = time.perf_counter()
            all_latencies_ms.append((t1 - t0) * 1000.0)
    stats = _latency_stats(all_latencies_ms)
    stats["total_frames_pooled"] = len(all_latencies_ms)
    stats["scenarios_pooled"] = ALL_SCENARIOS
    return stats


# ---------------------------------------------------------------------------
# 3. Agent decision latency (pure function)
# ---------------------------------------------------------------------------

def _sample_evidence_dicts() -> list[dict]:
    samples = []
    for scenario in INCIDENT_SCENARIOS:
        samples.append({"state": "none", "confidence": 0.0, "duration_seconds": 0.0, "scenario": scenario})
        samples.append({"state": "possible", "confidence": 0.45, "duration_seconds": 4.0, "scenario": scenario})
        samples.append({"state": "possible", "confidence": 0.7, "duration_seconds": 4.0, "scenario": scenario})
        samples.append({"state": "confirmed", "confidence": 0.6, "duration_seconds": 10.0, "scenario": scenario})
        samples.append({"state": "confirmed", "confidence": 0.95, "duration_seconds": 10.0, "scenario": scenario})
    return samples


def run_agent_decision_latency(settings: Settings) -> dict:
    policy = AgentPolicy(settings.agent_policy, settings.thresholds, settings.monitoring)
    samples = _sample_evidence_dicts()
    repeats = 200  # cycle through the sample set this many times for stable timing stats
    latencies_ms = []
    for _ in range(repeats):
        for evidence in samples:
            t0 = time.perf_counter()
            policy.evaluate(evidence)
            t1 = time.perf_counter()
            latencies_ms.append((t1 - t0) * 1000.0)
    stats = _latency_stats(latencies_ms)
    stats["methodology"] = (
        f"Timed AgentPolicy.evaluate() alone (pure/deterministic function, no I/O) over "
        f"{len(samples)} representative evidence dicts x {repeats} repeats = {len(latencies_ms)} calls."
    )
    return stats


# ---------------------------------------------------------------------------
# 4. End-to-end latency (vision + agent per frame)
# ---------------------------------------------------------------------------

def run_end_to_end_latency(settings: Settings) -> dict:
    per_scenario = {}
    for scenario in ALL_SCENARIOS:
        detector_scenario = scenario if scenario in INCIDENT_SCENARIOS else settings.default_scenario
        src = SyntheticFrameSource(scenario, num_frames=PERF_NUM_FRAMES, fps=FPS)
        frames = list(src.frames())
        pipeline = VisionPipeline(detector_scenario, settings.thresholds, settings.region_of_interest, region_name=scenario)
        policy = AgentPolicy(settings.agent_policy, settings.thresholds, settings.monitoring)

        latencies_ms = []
        for frame in frames:
            t0 = time.perf_counter()
            candidate = pipeline.process_frame(frame)
            policy.evaluate(candidate.to_agent_evidence())
            t1 = time.perf_counter()
            latencies_ms.append((t1 - t0) * 1000.0)
        per_scenario[scenario] = _latency_stats(latencies_ms)

    return {
        "methodology": (
            f"Timed VisionPipeline.process_frame() (processor + detector + temporal + evidence extraction, "
            f"including evidence-frame JPEG encoding once a signal is present) followed by AgentPolicy.evaluate(), "
            f"per frame, over {PERF_NUM_FRAMES} frames per scenario. Measured on this development machine only."
        ),
        "per_scenario": per_scenario,
    }


# ---------------------------------------------------------------------------
# 5. Decision-table test + human-escalation rate
# ---------------------------------------------------------------------------

def _expected_outcome(evidence: dict, settings: Settings) -> dict:
    """Independent re-derivation of the documented policy rules (see
    backend/app/agent/policy.py docstring / AgentPolicy.evaluate), used as a
    sanity check against the actual implementation's output."""
    t = settings.thresholds
    p = settings.agent_policy
    state = evidence["state"]
    confidence = evidence["confidence"]
    scenario = evidence["scenario"]

    if state == "none" or confidence < t.min_frame_confidence:
        return {"severity": "NONE", "decision": "CONTINUE_OBSERVATION", "action": "NONE", "requires_human_approval": False}

    if state == "possible":
        severity = "LOW" if confidence < 0.6 else "MEDIUM"
        return {"severity": severity, "decision": "INCREASE_MONITORING", "action": "STORE_EVIDENCE_ONLY", "requires_human_approval": False}

    # confirmed
    severity = "HIGH" if confidence >= p.high_confidence_autonomous_threshold else "MEDIUM"
    person_down_gate = scenario == "person_down" and p.person_down_always_requires_approval
    low_confidence_gate = confidence < p.human_approval_confidence_ceiling
    requires_approval = person_down_gate or low_confidence_gate
    action = "REQUEST_HUMAN_APPROVAL" if requires_approval else "SEND_ALERT"
    return {"severity": severity, "decision": "CREATE_INCIDENT", "action": action, "requires_human_approval": requires_approval}


def run_decision_table(settings: Settings) -> dict:
    policy = AgentPolicy(settings.agent_policy, settings.thresholds, settings.monitoring)
    states = ["none", "possible", "confirmed"]
    confidences = [0.0, 0.2, 0.34, 0.35, 0.5, 0.6, 0.7, 0.84, 0.85, 0.86, 0.95, 1.0]
    duration_by_state = {"none": 0.0, "possible": 4.0, "confirmed": 10.0}

    rows = []
    mismatches = 0
    confirmed_rows = 0
    confirmed_requiring_approval = 0

    for scenario in INCIDENT_SCENARIOS:
        for state in states:
            for confidence in confidences:
                evidence = {
                    "state": state,
                    "confidence": confidence,
                    "duration_seconds": duration_by_state[state],
                    "scenario": scenario,
                }
                actual = policy.evaluate(evidence)
                expected = _expected_outcome(evidence, settings)
                actual_dict = {
                    "severity": actual.severity,
                    "decision": actual.decision,
                    "action": actual.action,
                    "requires_human_approval": actual.requires_human_approval,
                }
                matches = actual_dict == expected
                if not matches:
                    mismatches += 1
                if state == "confirmed" and confidence >= t_min_frame_confidence(settings):
                    confirmed_rows += 1
                    if actual.requires_human_approval:
                        confirmed_requiring_approval += 1

                rows.append(
                    {
                        "scenario": scenario,
                        "state": state,
                        "confidence": confidence,
                        "duration_seconds": duration_by_state[state],
                        "actual": actual_dict,
                        "expected": expected,
                        "matches_documented_policy": matches,
                    }
                )

    human_escalation_rate = (
        confirmed_requiring_approval / confirmed_rows if confirmed_rows else None
    )

    return {
        "methodology": (
            "Cartesian product of scenario x state x confidence run through the actual AgentPolicy.evaluate(), "
            "compared against an independently re-derived expectation of the documented rules in "
            "backend/app/agent/policy.py. 'matches_documented_policy' is a live pass/fail, not asserted blindly."
        ),
        "total_rows": len(rows),
        "mismatches": mismatches,
        "all_rows_match_documented_policy": mismatches == 0,
        "human_escalation_rate_among_confirmed": round(human_escalation_rate, 4) if human_escalation_rate is not None else None,
        "confirmed_rows_considered": confirmed_rows,
        "confirmed_rows_requiring_human_approval": confirmed_requiring_approval,
        "rows": rows,
    }


def t_min_frame_confidence(settings: Settings) -> float:
    return settings.thresholds.min_frame_confidence


# ---------------------------------------------------------------------------
# 6. Cloud (explicitly not measured)
# ---------------------------------------------------------------------------

def run_cloud_section() -> dict:
    reason = "No live AWS deployment exists in this environment; local-mode only (storage_backend=local, no AWS credentials configured)."
    return {
        "aws_processing_latency_ms": "NOT MEASURED",
        "aws_throughput_events_per_sec": "NOT MEASURED",
        "aws_cost_per_1000_events_usd": "NOT MEASURED",
        "aws_resource_utilization": "NOT MEASURED",
        "reason": reason,
    }


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> Path:
    settings = _settings()
    started_at = datetime.now(timezone.utc)

    results = {
        "run_timestamp_utc": started_at.isoformat(),
        "environment": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "processor": platform.processor(),
            "opencv_version": cv2.__version__,
            "note": "Performance numbers below were measured on this single development machine at this "
            "point in time; they are not a universal or hardware-independent benchmark.",
        },
        "config_used": {
            "thresholds": settings.thresholds.model_dump(),
            "agent_policy": settings.agent_policy.model_dump(),
            "monitoring": settings.monitoring.model_dump(),
            "region_of_interest": settings.region_of_interest.model_dump(),
        },
        "vision_detection_quality": run_vision_quality(settings),
        "performance": {
            "vision_frame_latency_per_scenario": run_vision_frame_latency(settings),
            "vision_frame_latency_combined": run_vision_frame_latency_combined(settings),
            "agent_decision_latency": run_agent_decision_latency(settings),
            "end_to_end_latency_per_scenario": run_end_to_end_latency(settings),
        },
        "agent_evaluation": run_decision_table(settings),
        "cloud": run_cloud_section(),
    }

    finished_at = datetime.now(timezone.utc)
    results["run_duration_seconds"] = round((finished_at - started_at).total_seconds(), 3)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = started_at.strftime("%Y%m%dT%H%M%SZ")
    out_path = RESULTS_DIR / f"evaluation_{stamp}.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    latest_path = RESULTS_DIR / "latest.json"
    latest_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print(f"Evaluation complete in {results['run_duration_seconds']}s")
    print(f"Results written to: {out_path}")
    print(f"Latest copy:        {latest_path}")
    return out_path


if __name__ == "__main__":
    main()
