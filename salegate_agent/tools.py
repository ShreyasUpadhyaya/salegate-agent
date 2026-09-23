"""Thin, typed wrappers over the Salegate API. One function per endpoint.

Every tool here is read-only except score_lead, which only triggers a scoring
run (POST /api/leads/{id}/score) and edits no field on the lead itself.
Submitting a sale (POST /api/leads/{id}/submit) and writing an override
(POST /api/check-results/{id}/override) are deliberately not exposed: those
are human decisions this agent surfaces, never makes on its own.

Docstrings double as the tool descriptions ADK shows the model, so they say
what a human would want to know, not just the HTTP mechanics. Each return
value is a plain JSON-serializable dict, trimmed to what the model needs to
reason over and cite as evidence.
"""

from __future__ import annotations

from typing import Any

import httpx

from salegate_agent.config import get_settings


def _client() -> httpx.Client:
    settings = get_settings()
    return httpx.Client(base_url=settings.salegate_api_base, timeout=settings.request_timeout_s)


def _error_dict(status_code: int, lead_or_id: str, detail: str) -> dict[str, Any]:
    """A structured error the model can read and relay in plain language,
    instead of a raw HTTP exception."""
    if status_code == 404:
        message = f"{lead_or_id} was not found."
    elif status_code == 409:
        message = f"{lead_or_id} cannot be actioned right now: {detail}"
    else:
        message = f"Salegate API returned {status_code}: {detail}"
    return {"error": True, "status_code": status_code, "message": message}


def get_score(lead_id: str) -> dict[str, Any]:
    """Get the latest score for a lead: the gate decision and every check
    result with its status, confidence, reason and evidence (transcript
    utterance, speaker, timestamp). Use this to explain why a lead passed,
    failed or needs review, always citing the check_id and evidence.

    Args:
        lead_id: the Salegate lead id, e.g. "L-DEMO-1".
    """
    with _client() as client:
        response = client.get(f"/api/leads/{lead_id}/score")
    if response.status_code == 404:
        return _error_dict(404, lead_id, "no score yet, call score_lead first")
    if response.status_code >= 400:
        return _error_dict(response.status_code, lead_id, response.text)

    body = response.json()
    return {
        "lead_id": body["lead_id"],
        "decision": body["decision"],
        "sampled_for_qa": body["sampled_for_qa"],
        "scored_at": body["scored_at"],
        "checks": [
            {
                "check_id": r["check_id"],
                "status": r["status"],
                "effective_status": r["effective_status"],
                "confidence": r["confidence"],
                "reason": r["reason"],
                "evidence": [
                    {
                        "speaker": e.get("speaker"),
                        "start_s": e.get("start_s"),
                        "text": e.get("text_redacted"),
                    }
                    for e in r.get("evidence", [])
                ],
            }
            for r in body["results"]
        ],
    }


def get_gate(lead_id: str) -> dict[str, Any]:
    """Get just the gate decision for a lead and which critical checks drove
    it: HELD_TL (a critical check failed), QA_REVIEW (a critical check is
    unresolved, or the lead was sampled), or AUTO_SUBMIT (every critical check
    passed). Use this for a quick status check; use get_score for the full
    reasoning behind it.

    Args:
        lead_id: the Salegate lead id, e.g. "L-DEMO-1".
    """
    with _client() as client:
        response = client.get(f"/api/leads/{lead_id}/gate")
    if response.status_code == 404:
        return _error_dict(404, lead_id, "no score yet, call score_lead first")
    if response.status_code >= 400:
        return _error_dict(response.status_code, lead_id, response.text)

    body = response.json()
    return {
        "lead_id": body["lead_id"],
        "decision": body["decision"],
        "sampled_for_qa": body["sampled_for_qa"],
        "critical_fails": body["critical_fails"],
        "critical_reviews": body["critical_reviews"],
    }


def get_transcript(lead_id: str) -> dict[str, Any]:
    """Get the call transcript for a lead: every utterance with its speaker,
    start and end time in seconds, and the (redacted) text. Use this to quote
    exactly what was said, or to find the moment a specific claim was made.

    Args:
        lead_id: the Salegate lead id, e.g. "L-DEMO-1".
    """
    with _client() as client:
        response = client.get(f"/api/leads/{lead_id}/transcript")
    if response.status_code == 404:
        return _error_dict(404, lead_id, "this lead has no recording yet")
    if response.status_code >= 400:
        return _error_dict(response.status_code, lead_id, response.text)

    body = response.json()
    return {
        "lead_id": body["lead_id"],
        "duration_s": body["duration_s"],
        "utterances": [
            {
                "speaker": u["speaker"],
                "start_s": u["start_s"],
                "end_s": u["end_s"],
                "text": u["text_redacted"],
            }
            for u in body["utterances"]
        ],
    }


def score_lead(lead_id: str) -> dict[str, Any]:
    """Score (or rescore) a lead's most recent recording. Only call this when
    the user explicitly asks to score or rescore a lead, or when get_score
    reports the lead has never been scored and the user wants it scored now.
    This does not submit the sale and edits no CRM field; it only runs the
    checks and records the result.

    Args:
        lead_id: the Salegate lead id, e.g. "L-DEMO-1".
    """
    with _client() as client:
        response = client.post(f"/api/leads/{lead_id}/score")
    if response.status_code == 409:
        return _error_dict(409, lead_id, response.json().get("detail", "cannot be scored"))
    if response.status_code >= 400:
        return _error_dict(response.status_code, lead_id, response.text)

    body = response.json()
    return {
        "lead_id": body["lead_id"],
        "decision": body["decision"],
        "checks_scored": len(body["results"]),
    }


def list_overrides(check_result_id: int) -> dict[str, Any]:
    """Get the full override history for one check result: every time an
    auditor changed its effective status, oldest first, with who did it, the
    old and new status, and their reason. Overrides are append-only, so this
    is the complete audit trail for that check. check_result_id comes from a
    check entry returned by get_score (not shown by default; ask the API
    directly if you need the numeric id for a specific check).

    Args:
        check_result_id: the numeric id of one check result.
    """
    with _client() as client:
        response = client.get(f"/api/check-results/{check_result_id}/overrides")
    if response.status_code == 404:
        return _error_dict(404, str(check_result_id), "no such check result")
    if response.status_code >= 400:
        return _error_dict(response.status_code, str(check_result_id), response.text)

    return {"check_result_id": check_result_id, "overrides": response.json()}


def get_agent_rollup() -> dict[str, Any]:
    """Get the per-agent rollup: how many leads each agent has had scored,
    the breakdown across AUTO_SUBMIT / QA_REVIEW / HELD_TL, their first pass
    yield (share auto submitted) and critical fail rate. Use this for
    questions about a specific agent's or the team's overall performance.
    """
    with _client() as client:
        response = client.get("/api/dashboards/agents")
    if response.status_code >= 400:
        return _error_dict(response.status_code, "agent rollup", response.text)

    return {"agents": response.json()}
