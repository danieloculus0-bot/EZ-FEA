"""Independent numerical feedback for external agents on native FEA specimens.

Consumes completed native_curriculum.json records and agent predictions. This
does not invoke BEAN, train a model, or substitute analytical labels for native
measurements. The caller must preserve the train/holdout separation.
"""
import math


def score_native_predictions(curriculum, predictions, *, split="holdout"):
    """Score one prediction per measured specimen, without trusting agent scores.

    Each prediction: {"case_id": "...", "predicted_value": positive finite number}.
    Values must use the native specimen's target_metric units. Refuse incomplete
    native runs and incomplete submissions rather than silently improving scores
    by excluding difficult specimens.
    """
    if split not in ("train", "holdout"):
        raise ValueError("split must be train or holdout")
    if not isinstance(curriculum, dict) or not isinstance(predictions, list):
        raise ValueError("curriculum must be an object and predictions an array")
    if curriculum.get("schema") != "ezfea.real_structural_curriculum.v1":
        raise ValueError("unrecognized native curriculum schema")
    if curriculum.get("training_geometry_disjoint_from_holdout") is not True:
        raise ValueError("geometry separation not established")
    cases = curriculum.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("native curriculum has no cases")
    ids = set()
    geometries = {"train": set(), "holdout": set()}
    targets = {}
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("malformed native specimen")
        case_id = case.get("case_id")
        case_split = case.get("split")
        geometry = case.get("geometry_key")
        if not isinstance(case_id, str) or not case_id or case_id in ids:
            raise ValueError("duplicate or invalid native specimen ID")
        ids.add(case_id)
        if case_split not in geometries or not isinstance(geometry, str) or not geometry:
            raise ValueError("invalid specimen split or geometry")
        if geometry in geometries[case_split]:
            raise ValueError("duplicate specimen geometry")
        geometries[case_split].add(geometry)
        if case_split != split:
            continue
        if case.get("status") != "measured" or case.get("test_origin") != "native_step_gmsh_calculix_c3d10":
            raise ValueError("unverified native measurement in evaluation split")
        observed = case.get("native_measured")
        if type(observed) not in (int, float) or not math.isfinite(observed) or observed <= 0:
            raise ValueError("invalid native measurement")
        metric = case.get("target_metric")
        if not isinstance(metric, str) or not metric:
            raise ValueError("missing native metric")
        targets[case_id] = (float(observed), metric)
    if geometries["train"] & geometries["holdout"]:
        raise ValueError("train/holdout geometry leakage")
    if not targets:
        raise ValueError("no measured specimens in requested split")
    submitted = {}
    for prediction in predictions:
        if not isinstance(prediction, dict) or set(prediction) != {"case_id", "predicted_value"}:
            raise ValueError("prediction must contain only case_id and predicted_value")
        case_id = prediction["case_id"]
        value = prediction["predicted_value"]
        if not isinstance(case_id, str) or case_id in submitted:
            raise ValueError("duplicate or invalid prediction ID")
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError("predicted_value must be finite and positive")
        submitted[case_id] = float(value)
    if set(submitted) != set(targets):
        raise ValueError("predictions must exactly cover measured specimens in requested split")
    results = []
    for case_id in sorted(targets):
        actual, metric = targets[case_id]
        relative_error = abs(submitted[case_id] - actual) / actual
        results.append({
            "case_id": case_id,
            "target_metric": metric,
            "relative_error": relative_error,
            "score": 1.0 / (1.0 + relative_error),
        })
    return {
        "schema": "ezfea.native_agent_feedback.v1",
        "split": split,
        "measurement_origin": "native_step_gmsh_calculix_c3d10",
        "specimens_scored": len(results),
        "mean_score": sum(row["score"] for row in results) / len(results),
        "results": results,
        "model_learning_verified": False,
    }
