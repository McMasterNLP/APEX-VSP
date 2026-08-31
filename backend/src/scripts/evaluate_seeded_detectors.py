"""Offline evaluation of automatic empathy/SPIKES detectors against seeded fixtures.

Usage (from backend/):

    PYTHONPATH="$(pwd)/src" poetry run python -m scripts.evaluate_seeded_detectors

This evaluates ONLY the detector/preview layer, not scoring:
- EO spans
- response spans
- elicitation spans
- SPIKES stages (via StageTracker)

It compares:
- Seeded gold annotations in tests.fixtures.conversation_fixture
- Against the current rule-based preview pipeline (SimpleRuleNLU + NLUPipeline + StageTracker)
"""

from __future__ import annotations

import asyncio
import collections
import math
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Optional, Iterable

from adapters.nlu.simple_rule_nlu import SimpleRuleNLU
from services.nlu_pipeline import NLUPipeline
from services.stage_tracker import StageTracker
from tests.fixtures.conversation_fixture import (
    TEST_CONVERSATION_BAD,
    TEST_CONVERSATION_MEDIUM,
    TEST_CONVERSATION_GOOD,
)


# -----------------------
# Utility data structures
# -----------------------

@dataclass
class SpanItem:
    fixture_label: str
    category: str  # "eo" | "response" | "elicitation"
    turn_number: int
    text: str
    dimension: Optional[str] = None
    explicit_or_implicit: Optional[str] = None
    subtype: Optional[str] = None  # response/elicitation subtype


@dataclass
class SpanMatch:
    gold: SpanItem
    pred: SpanItem
    sim: float


def normalize_text(s: str) -> str:
    """Normalize span text for matching."""
    s = s.lower().strip()
    # Remove simple punctuation
    s = re.sub(r"[.,!?;:\"\']", " ", s)
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s)
    return s


def token_iou(a: str, b: str) -> float:
    """Token-level IoU between two normalized texts."""
    ta = set(normalize_text(a).split())
    tb = set(normalize_text(b).split())
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union > 0 else 0.0


def span_similarity(a: SpanItem, b: SpanItem) -> float:
    """Compute similarity score in [0,1] between two span texts."""
    na = normalize_text(a.text)
    nb = normalize_text(b.text)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    if na in nb or nb in na:
        return 0.9
    iou = token_iou(na, nb)
    return iou


def greedy_span_matching(
    gold: List[SpanItem],
    pred: List[SpanItem],
    sim_threshold: float = 0.5,
) -> Tuple[List[SpanMatch], List[SpanItem], List[SpanItem], List[Tuple[SpanItem, SpanItem, float]]]:
    """One-to-one greedy matching between gold and predicted spans on same turn/category.

    Returns:
        matches: list of SpanMatch (TPs)
        fn: gold items with no match
        fp: pred items with no match
        near_misses: (gold, pred, sim) where sim < threshold but > 0 (same turn/category)
    """
    matches: List[SpanMatch] = []
    near_misses: List[Tuple[SpanItem, SpanItem, float]] = []

    if not gold or not pred:
        return matches, gold, pred, near_misses

    # Build candidate pairs on same turn & category
    candidates: List[Tuple[SpanItem, SpanItem, float]] = []
    for g in gold:
        for p in pred:
            if g.turn_number != p.turn_number or g.category != p.category:
                continue
            sim = span_similarity(g, p)
            if sim > 0:
                candidates.append((g, p, sim))

    # Sort by similarity descending
    candidates.sort(key=lambda x: x[2], reverse=True)

    used_gold: set[int] = set()
    used_pred: set[int] = set()

    for g, p, sim in candidates:
        gid = id(g)
        pid = id(p)
        if gid in used_gold or pid in used_pred:
            continue
        if sim >= sim_threshold:
            matches.append(SpanMatch(gold=g, pred=p, sim=sim))
            used_gold.add(gid)
            used_pred.add(pid)
        else:
            # Store as potential near miss; we'll filter later
            near_misses.append((g, p, sim))

    fn = [g for g in gold if id(g) not in used_gold]
    fp = [p for p in pred if id(p) not in used_pred]

    # Filter near misses to only those whose gold/pred are still unmatched
    near_filtered: List[Tuple[SpanItem, SpanItem, float]] = []
    for g, p, sim in near_misses:
        if id(g) not in used_gold and id(p) not in used_pred and sim > 0.0:
            near_filtered.append((g, p, sim))

    return matches, fn, fp, near_filtered


def precision_recall_f1(tp: int, fp: int, fn: int) -> Tuple[float, float, float]:
    """Compute precision/recall/F1 with safe handling of zeros."""
    prec = tp / (tp + fp) if tp + fp > 0 else 0.0
    rec = tp / (tp + fn) if tp + fn > 0 else 0.0
    if prec + rec == 0:
        f1 = 0.0
    else:
        f1 = 2 * prec * rec / (prec + rec)
    return prec, rec, f1


# -----------------------
# Detector preview runner
# -----------------------

def build_preview_pipeline() -> Tuple[NLUPipeline, StageTracker]:
    nlu = SimpleRuleNLU()
    pipeline = NLUPipeline(
        span_detector=nlu,
        empathy_detector=nlu,
        question_classifier=nlu,
        tone_analyzer=nlu,
    )
    stage_tracker = StageTracker()
    return pipeline, stage_tracker


def collect_gold_spans(fixture: Dict[str, Any], category: str) -> List[SpanItem]:
    """Collect gold spans of a given category ('eo'|'response'|'elicitation') from fixture."""
    items: List[SpanItem] = []
    label = fixture.get("label", fixture.get("name", "UNKNOWN"))
    for turn in fixture.get("transcript", []):
        tn = turn["turn_number"]
        spans = turn.get("spans_json") or []
        for s in spans:
            if s.get("span_type") != category:
                continue
            text = s.get("text") or ""
            if not text:
                continue
            items.append(
                SpanItem(
                    fixture_label=label,
                    category=category,
                    turn_number=tn,
                    text=text,
                    dimension=s.get("dimension"),
                    explicit_or_implicit=s.get("explicit_or_implicit"),
                    subtype=s.get("type"),
                )
            )
    return items


def collect_preview_spans(
    fixture: Dict[str, Any],
    pipeline: NLUPipeline,
) -> Dict[str, List[SpanItem]]:
    """Run preview pipeline and collect spans per category."""
    label = fixture.get("label", fixture.get("name", "UNKNOWN"))
    eo_items: List[SpanItem] = []
    resp_items: List[SpanItem] = []
    elic_items: List[SpanItem] = []

    async def _process() -> None:
        for turn in fixture.get("transcript", []):
            tn = turn["turn_number"]
            text = turn["text"]
            analysis = await pipeline.analyze(text)

            # EO spans (emotion_spans)
            for s in analysis.get("emotion_spans") or []:
                eo_items.append(
                    SpanItem(
                        fixture_label=label,
                        category="eo",
                        turn_number=tn,
                        text=s.get("text") or "",
                        dimension=s.get("dimension"),
                        explicit_or_implicit=s.get("explicit_or_implicit"),
                        subtype=None,
                    )
                )

            # Response spans
            for s in analysis.get("response_spans") or []:
                resp_items.append(
                    SpanItem(
                        fixture_label=label,
                        category="response",
                        turn_number=tn,
                        text=s.get("text") or "",
                        dimension=None,
                        explicit_or_implicit=None,
                        subtype=s.get("type"),
                    )
                )

            # Elicitation spans
            for s in analysis.get("elicitation_spans") or []:
                elic_items.append(
                    SpanItem(
                        fixture_label=label,
                        category="elicitation",
                        turn_number=tn,
                        text=s.get("text") or "",
                        dimension=s.get("dimension"),
                        explicit_or_implicit=None,
                        subtype=s.get("type"),
                    )
                )

    asyncio.run(_process())

    return {
        "eo": eo_items,
        "response": resp_items,
        "elicitation": elic_items,
    }


def collect_stage_labels(
    fixture: Dict[str, Any],
    stage_tracker: StageTracker,
) -> Tuple[Dict[int, str], Dict[int, str]]:
    """Collect gold and preview SPIKES stages keyed by turn_number.

    Gold: from fixture['expected_spikes'] per turn (if present).
    Preview: from StageTracker.detect_stage on clinician ('user') turns.
    """
    gold: Dict[int, str] = {}
    preview: Dict[int, str] = {}

    # Gold from fixture
    for turn in fixture.get("transcript", []):
        tn = turn["turn_number"]
        stage = turn.get("expected_spikes")
        if stage:
            gold[tn] = str(stage).strip().lower()

    # Preview via StageTracker on clinician turns only (as in live system)
    for turn in fixture.get("transcript", []):
        if turn.get("role") != "user":
            continue
        tn = turn["turn_number"]
        text = turn["text"]
        stage = stage_tracker.detect_stage(text, session=None)
        if stage:
            preview[tn] = str(stage).strip().lower()

    return gold, preview


# -----------------------
# Stage evaluation helpers
# -----------------------

def evaluate_stages(
    gold: Dict[int, str],
    pred: Dict[int, str],
) -> Tuple[Dict[str, Any], Dict[Tuple[str, str], int]]:
    """Compute stage confusion, per-stage metrics, and overall accuracy.

    Only considers turns where either gold or pred has a label.
    """
    stage_map = {
        "setting": "setting",
        "s": "setting",
        "perception": "perception",
        "p": "perception",
        "invitation": "invitation",
        "i": "invitation",
        "knowledge": "knowledge",
        "k": "knowledge",
        "emotion": "empathy",
        "empathy": "empathy",
        "e": "empathy",
        "strategy": "strategy",
        "summary": "strategy",
        "s2": "strategy",
    }

    def canon(stage: Optional[str]) -> Optional[str]:
        if not stage:
            return None
        return stage_map.get(stage.lower())

    confusion: Dict[Tuple[str, str], int] = collections.Counter()
    labels_set: set[str] = set()
    total = 0
    correct = 0

    all_turns = sorted(set(gold.keys()) | set(pred.keys()))
    for tn in all_turns:
        g = canon(gold.get(tn))
        p = canon(pred.get(tn))
        if g is None and p is None:
            continue
        total += 1
        if g is None:
            g = "none"
        if p is None:
            p = "none"
        labels_set.update([g, p])
        confusion[(g, p)] += 1
        if g == p:
            correct += 1

    metrics: Dict[str, Any] = {}
    overall_acc = correct / total if total > 0 else 0.0
    metrics["overall_accuracy"] = overall_acc

    # Per-stage precision/recall/F1
    per_stage: Dict[str, Dict[str, float]] = {}
    for label in sorted(labels_set):
        if label == "none":
            continue
        tp = confusion.get((label, label), 0)
        fp = sum(confusion.get((g, label), 0) for g in labels_set if g != label)
        fn = sum(confusion.get((label, p), 0) for p in labels_set if p != label)
        prec, rec, f1 = precision_recall_f1(tp, fp, fn)
        per_stage[label] = {
            "precision": prec,
            "recall": rec,
            "f1": f1,
        }
    metrics["per_stage"] = per_stage

    return metrics, confusion


# -----------------------
# Main evaluation routine
# -----------------------

def evaluate_fixture(fixture: Dict[str, Any]) -> Dict[str, Any]:
    label = fixture.get("label", fixture.get("name", "UNKNOWN"))
    print(f"=== {label} ===")

    pipeline, stage_tracker = build_preview_pipeline()

    # Gold spans
    gold_eo = collect_gold_spans(fixture, "eo")
    gold_resp = collect_gold_spans(fixture, "response")
    gold_elic = collect_gold_spans(fixture, "elicitation")

    # Preview spans
    preview_spans = collect_preview_spans(fixture, pipeline)
    pred_eo = preview_spans["eo"]
    pred_resp = preview_spans["response"]
    pred_elic = preview_spans["elicitation"]

    results: Dict[str, Any] = {}

    def eval_category(name: str, gold: List[SpanItem], pred: List[SpanItem]) -> None:
        matches, fn, fp, near = greedy_span_matching(gold, pred, sim_threshold=0.5)
        tp = len(matches)
        prec, rec, f1 = precision_recall_f1(tp, len(fp), len(fn))
        results[name] = {
            "tp": tp,
            "fp": len(fp),
            "fn": len(fn),
            "precision": prec,
            "recall": rec,
            "f1": f1,
            "matches": matches,
            "fn_items": fn,
            "fp_items": fp,
            "near_misses": near,
        }
        print(f"{name.capitalize()} detection: P={prec:.3f} R={rec:.3f} F1={f1:.3f} (TP={tp}, FP={len(fp)}, FN={len(fn)})")

    eval_category("eo", gold_eo, pred_eo)
    eval_category("response", gold_resp, pred_resp)
    eval_category("elicitation", gold_elic, pred_elic)

    # Stage evaluation
    gold_stages, pred_stages = collect_stage_labels(fixture, stage_tracker)
    stage_metrics, confusion = evaluate_stages(gold_stages, pred_stages)
    results["stages"] = {
        "metrics": stage_metrics,
        "confusion": confusion,
        "gold": gold_stages,
        "pred": pred_stages,
    }

    print(f"SPIKES stage overall accuracy: {stage_metrics['overall_accuracy']:.3f}")

    # Error analysis: spans
    def print_examples(title: str, items: Iterable[Any], limit: int = 5) -> None:
        items = list(items)
        if not items:
            print(f"{title}: (none)")
            return
        print(title + ":")
        for it in items[:limit]:
            if isinstance(it, SpanItem):
                print(f"  - turn {it.turn_number}: {it.category} -> {repr(it.text)}")
            elif isinstance(it, SpanMatch):
                print(
                    f"  - turn {it.gold.turn_number}: "
                    f"gold={repr(it.gold.text)} pred={repr(it.pred.text)} sim={it.sim:.3f}"
                )
            elif isinstance(it, tuple) and len(it) == 3:
                g, p, sim = it
                print(
                    f"  - turn {g.turn_number}: "
                    f"gold={repr(g.text)} pred={repr(p.text)} sim={sim:.3f}"
                )
            else:
                print(f"  - {it}")

    print()
    print_examples("EO false negatives", results["eo"]["fn_items"])
    print_examples("EO false positives", results["eo"]["fp_items"])
    print_examples("EO near misses", results["eo"]["near_misses"])
    print()
    print_examples("Response false negatives", results["response"]["fn_items"])
    print_examples("Response false positives", results["response"]["fp_items"])
    print_examples("Response near misses", results["response"]["near_misses"])
    print()
    print_examples("Elicitation false negatives", results["elicitation"]["fn_items"])
    print_examples("Elicitation false positives", results["elicitation"]["fp_items"])
    print_examples("Elicitation near misses", results["elicitation"]["near_misses"])

    # Stage confusion/mismatches
    print()
    print("SPIKES stage confusion (gold -> pred: count):")
    if not confusion:
        print("  (none)")
    else:
        for (g, p), c in sorted(confusion.items()):
            print(f"  {g:>9} -> {p:<9}: {c}")

    print()
    print("Stage mismatches (first 10):")
    mismatches = []
    all_turns = sorted(set(results["stages"]["gold"].keys()) | set(results["stages"]["pred"].keys()))
    for tn in all_turns:
        g = results["stages"]["gold"].get(tn)
        p = results["stages"]["pred"].get(tn)
        if (g or p) and g != p:
            mismatches.append((tn, g, p))
    if not mismatches:
        print("  (none)")
    else:
        for tn, g, p in mismatches[:10]:
            print(f"  - turn {tn}: gold={g} pred={p}")

    print()
    return results


def aggregate_overall(results_list: List[Dict[str, Any]]) -> None:
    """Aggregate metrics across all fixtures."""
    sum_tp = collections.Counter()
    sum_fp = collections.Counter()
    sum_fn = collections.Counter()

    stage_correct = 0
    stage_total = 0

    for res in results_list:
        for cat in ("eo", "response", "elicitation"):
            sum_tp[cat] += res[cat]["tp"]
            sum_fp[cat] += res[cat]["fp"]
            sum_fn[cat] += res[cat]["fn"]

        # Stage accuracy
        m = res["stages"]["metrics"]
        acc = m["overall_accuracy"]
        # approximate counts: need total from confusion
        confusion: Dict[Tuple[str, str], int] = res["stages"]["confusion"]
        total = sum(confusion.values())
        correct = int(round(acc * total)) if total > 0 else 0
        stage_correct += correct
        stage_total += total

    print("=== OVERALL ===")
    for cat in ("eo", "response", "elicitation"):
        tp = sum_tp[cat]
        fp = sum_fp[cat]
        fn = sum_fn[cat]
        prec, rec, f1 = precision_recall_f1(tp, fp, fn)
        print(
            f"{cat.capitalize()} detection: P={prec:.3f} R={rec:.3f} F1={f1:.3f} "
            f"(TP={tp}, FP={fp}, FN={fn})"
        )

    if stage_total > 0:
        stage_acc = stage_correct / stage_total
    else:
        stage_acc = 0.0
    print(f"SPIKES stage overall accuracy: {stage_acc:.3f}")


def main() -> None:
    fixtures = [TEST_CONVERSATION_BAD, TEST_CONVERSATION_MEDIUM, TEST_CONVERSATION_GOOD]
    all_results: List[Dict[str, Any]] = []
    for fx in fixtures:
        res = evaluate_fixture(fx)
        all_results.append(res)
        print("=" * 80)
        print()

    aggregate_overall(all_results)


if __name__ == "__main__":
    main()
