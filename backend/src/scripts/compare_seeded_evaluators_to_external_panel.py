"""Compare APEX evaluator scores to an external LLM judge panel (mean ± std).

1. **Panel:** averages JSON judge files under ``evaluation/external_llm_judges/`` (eval1–4 → strong/decent/mixed/weak).

2. **APEX LLM scores:** read from a captured pytest print log (default ``evaluation/validation_model_outputs.txt``)
   — the same output as ``test_seeded_difficult_diagnosis_print_and_structure``. No live
   OpenAI calls and no re-run of the transcript pipeline.

**Hybrid v1 / v2** use the raw **``llm_scores``** dict in each block (same kind of signal as the external
LLM judges). The rule-only **baseline** uses the ``scores: emp=…`` line and is shown for reference only;
it is not an LLM-to-LLM comparison with the panel.

Usage (from ``backend/``)::

    PYTHONPATH="$(pwd)/src" poetry run python -m scripts.compare_seeded_evaluators_to_external_panel

Optional::

    PYTHONPATH="$(pwd)/src" poetry run python -m scripts.compare_seeded_evaluators_to_external_panel \\
        --apex-output path/to/your_capture.txt
"""

from __future__ import annotations

import argparse
import ast
import json
import math
import re
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping

# ``python -m`` from backend: ensure ``src/`` and backend root on path for any future imports.
_SRC_ROOT = Path(__file__).resolve().parents[1]
_BACKEND_ROOT = _SRC_ROOT.parent
for p in (_SRC_ROOT, _BACKEND_ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

METRICS = (
    "empathy_score",
    "communication_score",
    "spikes_completion_score",
    "overall_score",
)

CASE_ORDER = ("strong", "decent", "mixed", "weak")

EVAL_SUFFIX_TO_CASE: Dict[str, str] = {
    "1": "strong",
    "2": "decent",
    "3": "mixed",
    "4": "weak",
}

LABEL_TO_CASE: Dict[str, str] = {
    "STRONG": "strong",
    "DECENT": "decent",
    "MIXED": "mixed",
    "WEAK": "weak",
}

EXTERNAL_ROOT = _BACKEND_ROOT / "evaluation" / "external_llm_judges"
REPORT_PATH = _BACKEND_ROOT / "evaluation" / "panel_comparison_report.json"
DEFAULT_APEX_SNAPSHOT = _BACKEND_ROOT / "evaluation" / "validation_model_outputs.txt"


def _infer_case_from_filename(name: str) -> str | None:
    m = re.search(r"eval[_\s-]?([1-4])\b", name, flags=re.IGNORECASE)
    if not m:
        m = re.search(r"eval([1-4])", name, flags=re.IGNORECASE)
    if not m:
        return None
    return EVAL_SUFFIX_TO_CASE.get(m.group(1))


def _parse_external_file(path: Path) -> tuple[Dict[str, Any] | None, str | None]:
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return None, "empty file"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return None, f"JSON decode error: {e}"
    if not isinstance(data, dict):
        return None, "root is not an object"
    scores = data.get("scores")
    if not isinstance(scores, dict):
        return None, "missing or invalid scores object"
    missing = [k for k in METRICS if k not in scores]
    if missing:
        return None, f"scores missing keys: {missing}"
    try:
        out = {k: float(scores[k]) for k in METRICS}
    except (TypeError, ValueError) as e:
        return None, f"non-numeric score: {e}"
    return {"scores": out, "source_file": str(path.relative_to(_BACKEND_ROOT))}, None


def collect_external_panel_by_case() -> tuple[Dict[str, List[Dict[str, float]]], List[str]]:
    """Load all external judge score dicts grouped by case (strong/decent/mixed/weak)."""
    per_case: Dict[str, List[Dict[str, float]]] = {c: [] for c in CASE_ORDER}
    warnings: List[str] = []

    if not EXTERNAL_ROOT.is_dir():
        warnings.append(f"External judge root not found: {EXTERNAL_ROOT}")
        return per_case, warnings

    for path in sorted(EXTERNAL_ROOT.rglob("*")):
        if path.suffix.lower() not in (".txt", ".json"):
            continue
        if not path.is_file():
            continue
        case = _infer_case_from_filename(path.name)
        if case is None:
            warnings.append(f"skip (no eval1–4 in name): {path.relative_to(_BACKEND_ROOT)}")
            continue
        parsed, err = _parse_external_file(path)
        if err:
            warnings.append(f"skip {path.relative_to(_BACKEND_ROOT)}: {err}")
            continue
        per_case[case].append(parsed["scores"])  # type: ignore[index]

    return per_case, warnings


def _panel_mean_std(values: List[float]) -> Dict[str, float]:
    if not values:
        return {"mean": float("nan"), "std": float("nan")}
    mean = statistics.fmean(values)
    if len(values) < 2:
        std = 0.0
    else:
        std = statistics.pstdev(values)
    return {"mean": round(mean, 4), "std": round(std, 4)}


def build_panel_summary(
    per_case: Dict[str, List[Dict[str, float]]],
) -> Dict[str, Dict[str, Dict[str, float]]]:
    out: Dict[str, Dict[str, Dict[str, float]]] = {}
    for case in CASE_ORDER:
        rows = per_case[case]
        out[case] = {}
        for m in METRICS:
            vals = [r[m] for r in rows if m in r]
            out[case][m] = _panel_mean_std(vals)
    return out


def _parse_dict_after_label(blob: str, label: str) -> Dict[str, float] | None:
    """Parse ``label: { ... }`` on one line (e.g. ``llm_scores`` or ``merged_scores``)."""
    m = re.search(rf"{re.escape(label)}:\s*(\{{[^\n]+\}})", blob)
    if not m:
        return None
    try:
        d = ast.literal_eval(m.group(1))
    except (SyntaxError, ValueError):
        return None
    if not isinstance(d, dict):
        return None
    return {k: float(d[k]) for k in METRICS if k in d}


def parse_apex_snapshot_file(path: Path) -> tuple[Dict[str, Dict[str, Dict[str, float]]], List[str]]:
    """Parse pytest capture log (e.g. ``validation_model_outputs.txt``) into model_outputs (baseline; hybrid = ``llm_scores``)."""
    warnings: List[str] = []
    if not path.is_file():
        raise FileNotFoundError(f"APEX snapshot file not found: {path}")

    text = path.read_text(encoding="utf-8")
    out: Dict[str, Dict[str, Dict[str, float]]] = {
        "baseline": {},
        "hybrid_v1": {},
        "hybrid_v2": {},
    }

    chunks = re.split(
        r"={10,}\s*\nFIXTURE:\s*DIFFICULT_DIAGNOSIS_",
        text,
        flags=re.IGNORECASE,
    )
    for chunk in chunks[1:]:
        label_m = re.match(r"(STRONG|DECENT|MIXED|WEAK)\b", chunk, flags=re.IGNORECASE)
        if not label_m:
            warnings.append("skip chunk: could not read STRONG|DECENT|MIXED|WEAK after FIXTURE:")
            continue
        case = LABEL_TO_CASE[label_m.group(1).upper()]

        base_m = re.search(
            r"BASELINE\s*\(rule-only[^\n]*\n\s*scores:\s*emp=([\d.]+)\s+comm=([\d.]+)\s+spikes=([\d.]+)\s+overall=([\d.]+)",
            chunk,
            re.IGNORECASE | re.DOTALL,
        )
        if base_m:
            out["baseline"][case] = {
                "empathy_score": float(base_m.group(1)),
                "communication_score": float(base_m.group(2)),
                "spikes_completion_score": float(base_m.group(3)),
                "overall_score": float(base_m.group(4)),
            }
        else:
            warnings.append(f"{case}: baseline scores line not found")

        v1_region = re.search(
            r"HYBRID\s+V1\s*\(real LLM\)(.*?)HYBRID\s+V2\s*\(real LLM\)",
            chunk,
            re.DOTALL | re.IGNORECASE,
        )
        if v1_region:
            ls = _parse_dict_after_label(v1_region.group(1), "llm_scores")
            if ls and len(ls) == 4:
                out["hybrid_v1"][case] = ls
            else:
                warnings.append(f"{case}: hybrid_v1 llm_scores not parsed")
        else:
            warnings.append(f"{case}: HYBRID V1 block not found")

        v2_region = re.search(r"HYBRID\s+V2\s*\(real LLM\)(.*)", chunk, re.DOTALL | re.IGNORECASE)
        if v2_region:
            ls = _parse_dict_after_label(v2_region.group(1), "llm_scores")
            if ls and len(ls) == 4:
                out["hybrid_v2"][case] = ls
            else:
                warnings.append(f"{case}: hybrid_v2 llm_scores not parsed")
        else:
            warnings.append(f"{case}: HYBRID V2 block not found")

    for ev in out:
        for c in CASE_ORDER:
            if c not in out[ev]:
                warnings.append(f"missing {ev}/{c}")

    return out, warnings


def _abs_error(a: float, b: float) -> float:
    return round(abs(a - b), 4)


def build_comparison(
    panel_summary: Mapping[str, Mapping[str, Mapping[str, float]]],
    model_outputs: Mapping[str, Mapping[str, Mapping[str, float]]],
) -> Dict[str, Any]:
    comp: Dict[str, Any] = {}
    for ev_name in ("baseline", "hybrid_v1", "hybrid_v2"):
        comp[ev_name] = {}
        for case in CASE_ORDER:
            comp[ev_name][case] = {}
            for m in METRICS:
                pm = panel_summary[case][m]["mean"]
                model_val = model_outputs[ev_name][case][m]
                if math.isnan(pm):
                    comp[ev_name][case][m] = {
                        "model": model_val,
                        "panel_mean": None,
                        "abs_error": None,
                    }
                else:
                    comp[ev_name][case][m] = {
                        "model": model_val,
                        "panel_mean": pm,
                        "abs_error": _abs_error(model_val, pm),
                    }
    return comp


def _mean_abs_error_for_evaluator(
    comparison: Mapping[str, Mapping[str, Mapping[str, Any]]], ev_name: str
) -> float:
    errs: List[float] = []
    for case in CASE_ORDER:
        for m in METRICS:
            cell = comparison[ev_name][case][m]
            ae = cell.get("abs_error")
            if ae is not None:
                errs.append(float(ae))
    return statistics.fmean(errs) if errs else float("nan")


def _print_tables(
    panel_summary: Mapping[str, Any],
    model_outputs: Mapping[str, Any],
    comparison: Mapping[str, Any],
) -> None:
    print("\n=== External panel (mean ± std by case) ===")
    for case in CASE_ORDER:
        print(f"\n-- {case} --")
        for m in METRICS:
            s = panel_summary[case][m]
            print(f"  {m}: mean={s['mean']} std={s['std']}")

    print("\n=== APEX scores from snapshot ===")
    print("  (baseline = rule-only ``scores:`` line; hybrid v1/v2 = raw ``llm_scores`` vs panel LLM means)")
    for ev in ("baseline", "hybrid_v1", "hybrid_v2"):
        print(f"\n-- {ev} --")
        for case in CASE_ORDER:
            row = model_outputs[ev][case]
            print(
                f"  {case}: emp={row['empathy_score']:.2f} comm={row['communication_score']:.2f} "
                f"spikes={row['spikes_completion_score']:.2f} overall={row['overall_score']:.2f}"
            )

    print("\n=== Absolute error vs external panel mean (LLM judge average) ===")
    for ev in ("baseline", "hybrid_v1", "hybrid_v2"):
        print(f"\n-- {ev} --")
        for case in CASE_ORDER:
            parts = []
            for m in METRICS:
                c = comparison[ev][case][m]
                ae = c.get("abs_error")
                parts.append(f"{m}={ae}" if ae is not None else f"{m}=n/a")
            print(f"  {case}: " + " | ".join(parts))


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare external panel means to APEX snapshot scores.")
    parser.add_argument(
        "--apex-output",
        type=Path,
        default=DEFAULT_APEX_SNAPSHOT,
        help=f"Path to pytest print capture (default: {DEFAULT_APEX_SNAPSHOT})",
    )
    args = parser.parse_args()

    print("Collecting external judge files from:", EXTERNAL_ROOT)
    per_case_lists, ext_warnings = collect_external_panel_by_case()
    for w in ext_warnings:
        print("WARNING:", w)

    panel_summary = build_panel_summary(per_case_lists)

    apex_path = args.apex_output
    if not apex_path.is_absolute():
        apex_path = (_BACKEND_ROOT / apex_path).resolve()
    print("\nReading APEX scores from snapshot (no live LLM):", apex_path)
    model_outputs, apex_warnings = parse_apex_snapshot_file(apex_path)
    for w in apex_warnings:
        print("WARNING:", w)

    comparison = build_comparison(panel_summary, model_outputs)

    report = {
        "panel_summary": panel_summary,
        "model_outputs": model_outputs,
        "comparison": comparison,
        "meta": {
            "external_root": str(EXTERNAL_ROOT),
            "apex_snapshot_file": str(apex_path.relative_to(_BACKEND_ROOT))
            if apex_path.is_relative_to(_BACKEND_ROOT)
            else str(apex_path),
            "case_mapping": "eval1=strong, eval2=decent, eval3=mixed, eval4=weak",
            "apex_score_source": (
                "baseline: rule-only scores line; hybrid_v1/v2: llm_scores (raw LLM) from snapshot — "
                "comparable to external LLM panel means"
            ),
        },
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nWrote JSON report: {REPORT_PATH}")

    _print_tables(panel_summary, model_outputs, comparison)

    mae_b = _mean_abs_error_for_evaluator(comparison, "baseline")
    mae_v1 = _mean_abs_error_for_evaluator(comparison, "hybrid_v1")
    mae_v2 = _mean_abs_error_for_evaluator(comparison, "hybrid_v2")

    print("\n=== Summary (mean absolute error vs panel mean, all cases × metrics) ===")
    print("  baseline is rule-only (not LLM); prefer hybrid rows for LLM-vs-panel alignment.")
    print(f"  baseline:   {mae_b:.4f}")
    print(f"  hybrid_v1:  {mae_v1:.4f}")
    print(f"  hybrid_v2:  {mae_v2:.4f}")

    best_hybrid = min(("hybrid_v1", mae_v1), ("hybrid_v2", mae_v2), key=lambda x: x[1])
    if not math.isnan(best_hybrid[1]):
        print(
            f"\nClosest hybrid LLM scores to external panel mean (lowest MAE): "
            f"{best_hybrid[0]} (MAE={best_hybrid[1]:.4f})"
        )
    if not math.isnan(mae_b):
        print(f"  (baseline MAE for reference: {mae_b:.4f})")
    else:
        print("\nCould not compute MAE (no panel data or no valid comparisons).")


if __name__ == "__main__":
    main()
