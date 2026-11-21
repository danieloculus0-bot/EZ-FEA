"""Bounded JSON stdin/stdout interface for synthetic axial design decisions.

Run: python -m ezfea.axial_challenge_cli < request.json
This invokes the existing 1D finite-element solver, not BEAN Core or hardware.
"""
import json
import sys

from .axial_design_challenge import evaluate_axial_design, rank_axial_options

MAX_REQUEST_BYTES = 1_000_000


def handle_request(request):
    if not isinstance(request, dict):
        raise ValueError("request must be an object")
    if set(request) - {"action", "challenge", "proposal"}:
        raise ValueError("unexpected request fields")
    action = request.get("action")
    challenge = request.get("challenge")
    if action == "evaluate":
        if set(request) != {"action", "challenge", "proposal"}:
            raise ValueError("evaluate requires challenge and proposal")
        return {"action": action, "result": evaluate_axial_design(challenge, request["proposal"])}
    if action == "rank":
        if set(request) != {"action", "challenge"}:
            raise ValueError("rank requires challenge without proposal")
        return {"action": action, "results": rank_axial_options(challenge)}
    raise ValueError("action must be evaluate or rank")


def main():
    try:
        raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        if len(raw) > MAX_REQUEST_BYTES:
            raise ValueError("request exceeds 1 MB")
        request = json.loads(raw)
        receipt = {"ok": True, **handle_request(request)}
        output = json.dumps(receipt, sort_keys=True, allow_nan=False)
        status = 0
    except (ValueError, TypeError, OverflowError, KeyError, ZeroDivisionError) as exc:
        output = json.dumps({"ok": False, "error": str(exc)}, sort_keys=True)
        status = 2
    print(output)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
