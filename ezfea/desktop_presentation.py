"""Small, testable presentation rules; never approximate solver physics."""
from __future__ import annotations

import math

PALETTE = {
    "background":"#050607",
    "panel":"#111519",
    "panel_high":"#171d20",
    "border":"#343c3e",
    "text":"#edf5f0",
    "muted":"#adbcb2",
    "accent":"#c5ff4a",
    "accent_hover":"#dcff8e",
    "danger":"#ffbd79",
}
DIRECTIONS = (
    "Down (−Y)", "Up (+Y)", "Right (+X)",
    "Left (−X)", "Forward (+Z)", "Back (−Z)",
)
DIRECTION_VECTORS = {
    "Down (−Y)":(0.,-1.,0.), "Up (+Y)":(0.,1.,0.),
    "Right (+X)":(1.,0.,0.), "Left (−X)":(-1.,0.,0.),
    "Forward (+Z)":(0.,0.,1.), "Back (−Z)":(0.,0.,-1.),
}


def force_components(magnitude, direction):
    """Turn a single force and plain-language direction into native XYZ N."""
    try:
        value=float(magnitude)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Enter a force magnitude in newtons") from exc
    if not math.isfinite(value) or value<=0:
        raise ValueError("Force magnitude must be finite and greater than zero")
    if direction not in DIRECTION_VECTORS:
        raise ValueError("Choose a valid force direction")
    return tuple(round(value*v,12) for v in DIRECTION_VECTORS[direction])


def brief_native_result(summary):
    """Never turn a reviewed/failed solver result into a green success label."""
    if summary["status"] not in ("completed","needs_review"):
        raise ValueError("Unknown native solver state")
    return {
        "state":"SOLVED" if summary["status"]=="completed" else "REVIEW",
        "headline":summary["headline"],
        "movement":summary["max_displacement"],
        "stress":summary["max_stress"],
        "balance":(
            "Force "+summary["force_balance"]+
            "   •   Moment "+summary["moment_balance"]
        ),
    }
