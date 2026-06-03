"""
Flask REST interface for the AI Processing Engine.

Endpoints:
    POST /api/ai/jobs           – Submit a new job (returns 202 + job_id)
    GET  /api/ai/jobs/<job_id>  – Poll job status & result

Blueprint is registered in the Flask app factory.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

from flask import Blueprint, current_app, jsonify, request

from ai_engine.domain.models import AIJobType

ai_bp = Blueprint("ai", __name__, url_prefix="/api/ai")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_worker():
    """Retrieve the AIJobWorker stored on the Flask app context."""
    return current_app.extensions["ai_engine_worker"]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@ai_bp.route("/jobs", methods=["POST"])
def submit_job():
    """
    Submit a new AI job.

    Request body (JSON):
        {
            "job_type": "summarization" | "sentiment_analysis" | "dataset_profiling",
            "payload":  { … },
            "tags":     { "tenant": "acme" }   // optional
        }

    Response 202:
        { "job_id": "…", "status": "pending" }
    """
    body: dict[str, Any] = request.get_json(force=True, silent=True) or {}

    raw_type = body.get("job_type")
    if not raw_type:
        return jsonify({"error": "Missing 'job_type'."}), HTTPStatus.BAD_REQUEST

    try:
        job_type = AIJobType(raw_type)
    except ValueError:
        valid = [t.value for t in AIJobType]
        return (
            jsonify({"error": f"Unknown job_type '{raw_type}'. Valid: {valid}"}),
            HTTPStatus.BAD_REQUEST,
        )

    payload = body.get("payload", {})
    tags = body.get("tags", {})

    worker = _get_worker()
    job = worker._orchestrator.submit_job(job_type, payload, tags)
    worker.enqueue(job.job_id)

    return jsonify({"job_id": job.job_id, "status": job.status.value}), HTTPStatus.ACCEPTED


@ai_bp.route("/jobs/<string:job_id>", methods=["GET"])
def get_job(job_id: str):
    """
    Poll a job's status and result.

    Response 200:
        { "job_id": "…", "status": "…", "result": { … } | null, … }
    Response 404 when job not found.
    """
    worker = _get_worker()
    try:
        job = worker._orchestrator.get_job(job_id)
    except ValueError:
        return jsonify({"error": f"Job '{job_id}' not found."}), HTTPStatus.NOT_FOUND

    return jsonify(job.to_dict()), HTTPStatus.OK
