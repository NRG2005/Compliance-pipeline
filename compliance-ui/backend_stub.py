"""
compliance_pipeline/api.py
--------------------------
Minimal FastAPI server that the React frontend connects to.
Run with:  uvicorn compliance_pipeline.api:app --reload --port 8000

The frontend calls two endpoints:
  POST /api/transactions/stream  — SSE, real-time layer events
  POST /api/transactions         — synchronous fallback
  GET  /api/results/{tx_id}      — fetch stored result from Cosmos DB
  GET  /api/health               — liveness probe
"""

import asyncio
import hashlib
import json
import time
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI(title="Compliance Pipeline API")

# ── CORS ────────────────────────────────────────────────────────────────────
# In production, replace "*" with your Static Web App URL.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://<your-static-web-app>.azurestaticapps.net"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request schema (mirrors frontend Transaction type) ───────────────────────
class Transaction(BaseModel):
    tx_id: str
    timestamp: str
    channel: str
    amount_inr: float
    sender_account_id: str
    sender_name: str
    sender_bank: str
    sender_ifsc: str
    sender_vpa: str | None = None
    receiver_name: str
    receiver_account_external: str
    receiver_bank: str
    receiver_state: str
    receiver_city: str
    tx_location_state: str
    tx_location_city: str
    purpose_code: str
    device_id: str
    tx_status: str


# ── SSE helper ───────────────────────────────────────────────────────────────
def sse(data: dict) -> str:
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(data)}\n\n"


# ── Main streaming endpoint ──────────────────────────────────────────────────
@app.post("/api/transactions/stream")
async def stream_transaction(tx: Transaction):
    """
    Runs the full L0–L7 pipeline and streams layer events as Server-Sent Events.

    Each message is one of:
      {"type": "layer_start",    "layer": 0}
      {"type": "layer_complete", "event": { LayerEvent }}
      {"type": "result",         "result": { PipelineResult }}
      {"type": "error",          "message": "..."}
    """

    async def generate() -> AsyncIterator[str]:
        start = time.monotonic()
        layer_events = []

        try:
            # ── L0: Event ingestion ──────────────────────────────────────────
            yield sse({"type": "layer_start", "layer": 0})
            t0 = time.monotonic()
            # TODO: publish to Azure Service Bus and wait for ack
            await asyncio.sleep(0.05)  # simulate
            l0_event = {
                "layer": 0,
                "status": "pass",
                "chip_label": "Ingested",
                "detail": "Message locked on tx-events topic · pipeline sub routed",
                "sub_checks": [],
                "sub_scores": [],
                "latency_ms": int((time.monotonic() - t0) * 1000),
            }
            layer_events.append(l0_event)
            yield sse({"type": "layer_complete", "event": l0_event})

            # ── L1: Orchestrator ─────────────────────────────────────────────
            yield sse({"type": "layer_start", "layer": 1})
            t0 = time.monotonic()
            # TODO: call your L1 LangGraph orchestrator
            # from compliance_pipeline.l1_orchestrator import orchestrate
            # l1_result = await orchestrate(tx.model_dump())
            l1_result = {"cache_hit": False, "route": "full_pipeline"}
            await asyncio.sleep(0.08)
            l1_event = {
                "layer": 1,
                "status": "pass" if l1_result["cache_hit"] else "flag",
                "chip_label": "Short-circuit" if l1_result["cache_hit"] else "No cache hit",
                "detail": "Case memory miss — routing to full L2/L3 pipeline",
                "sub_checks": [],
                "sub_scores": [],
                "latency_ms": int((time.monotonic() - t0) * 1000),
            }
            layer_events.append(l1_event)
            yield sse({"type": "layer_complete", "event": l1_event})

            if l1_result["cache_hit"]:
                # Short-circuit: skip L2–L5, jump to L6
                for layer_idx in [2, 3, 4, 5]:
                    skip = {
                        "layer": layer_idx, "status": "skip",
                        "chip_label": "Skipped", "detail": "L1 short-circuit",
                        "sub_checks": [], "sub_scores": [],
                    }
                    layer_events.append(skip)
                    yield sse({"type": "layer_complete", "event": skip})
            else:
                # ── L2: Transaction monitor ──────────────────────────────────
                yield sse({"type": "layer_start", "layer": 2})
                t0 = time.monotonic()
                # TODO: call your T1–T4 Azure Functions in parallel
                # from compliance_pipeline.l2_monitor import run_checks
                # l2_result = await run_checks(tx.model_dump())
                l2_result = {
                    "composite_score": 0.81,
                    "flagged": True,
                    "checks": [
                        {"label": "T1 structuring", "result": "fail"},
                        {"label": "T2 watchlist: clear", "result": "pass"},
                        {"label": "T3 risk: medium", "result": "fail"},
                        {"label": "T4 geo: match", "result": "pass"},
                    ],
                }
                await asyncio.sleep(0.09)
                l2_event = {
                    "layer": 2,
                    "status": "flag" if l2_result["flagged"] else "pass",
                    "chip_label": f"Composite {l2_result['composite_score']:.2f}",
                    "detail": "T1 velocity check fired · score above routing threshold",
                    "sub_checks": l2_result["checks"],
                    "sub_scores": [],
                    "latency_ms": int((time.monotonic() - t0) * 1000),
                }
                layer_events.append(l2_event)
                yield sse({"type": "layer_complete", "event": l2_event})

                # ── L3: Regulation interpreter ───────────────────────────────
                yield sse({"type": "layer_start", "layer": 3})
                t0 = time.monotonic()
                # TODO: call your L3 GPT-5.1 legal reasoning
                # from compliance_pipeline.l3_interpreter import interpret
                # l3_result = await interpret(tx.model_dump(), l2_result)
                l3_result = {
                    "composite_score": 0.84,
                    "band": "file_review",
                    "sub_scores": [
                        {"key": "Retrieval match",      "value": 0.91, "weight": 0.30},
                        {"key": "Rule applicability",   "value": 0.88, "weight": 0.35},
                        {"key": "Evidence sufficiency", "value": 0.79, "weight": 0.25},
                        {"key": "Precedent confidence", "value": 0.72, "weight": 0.10},
                    ],
                    "regulatory_basis": ["PMLA Rule 3", "RBI AML/CTR circular", "FIU-IND STR guidelines"],
                    "verdict": "str_filed",
                }
                await asyncio.sleep(1.3)
                l3_event = {
                    "layer": 3,
                    "status": "str" if l3_result["band"] in ("auto_file", "file_review") else "flag",
                    "chip_label": f"Confidence {l3_result['composite_score']:.2f}",
                    "detail": "PMLA Rule 3 — deliberate splitting below ₹50K threshold",
                    "sub_checks": [],
                    "sub_scores": l3_result["sub_scores"],
                    "latency_ms": int((time.monotonic() - t0) * 1000),
                }
                layer_events.append(l3_event)
                yield sse({"type": "layer_complete", "event": l3_event})

                # ── L4: Report generator ─────────────────────────────────────
                should_file = l3_result["composite_score"] >= 0.70
                if should_file:
                    yield sse({"type": "layer_start", "layer": 4})
                    t0 = time.monotonic()
                    # TODO: call your Jinja2 + lxml STR generator
                    # from compliance_pipeline.l4_report import generate_str
                    # l4_result = await generate_str(tx.model_dump(), l3_result)
                    await asyncio.sleep(0.3)
                    l4_event = {
                        "layer": 4,
                        "status": "str",
                        "chip_label": "STR generated",
                        "detail": "goAML XML · lxml XSD validation: pass · written to submission Blob",
                        "sub_checks": [],
                        "sub_scores": [],
                        "latency_ms": int((time.monotonic() - t0) * 1000),
                    }
                    layer_events.append(l4_event)
                    yield sse({"type": "layer_complete", "event": l4_event})
                else:
                    skip = {"layer": 4, "status": "skip", "chip_label": "Skipped",
                            "detail": "Confidence below 0.70 — no auto-file", "sub_checks": [], "sub_scores": []}
                    layer_events.append(skip)
                    yield sse({"type": "layer_complete", "event": skip})

                # ── L5: Human review ─────────────────────────────────────────
                needs_review = 0.50 <= l3_result["composite_score"] < 0.90
                if needs_review:
                    l5_event = {
                        "layer": 5,
                        "status": "flag",
                        "chip_label": "Queued for review",
                        "detail": "Evidence dossier created · 7-day FIU-IND deadline started",
                        "sub_checks": [], "sub_scores": [],
                    }
                    layer_events.append(l5_event)
                    yield sse({"type": "layer_complete", "event": l5_event})
                else:
                    skip = {"layer": 5, "status": "skip", "chip_label": "Skipped",
                            "detail": "Auto-filed — no human review needed", "sub_checks": [], "sub_scores": []}
                    layer_events.append(skip)
                    yield sse({"type": "layer_complete", "event": skip})

            # ── L6: Audit logger ─────────────────────────────────────────────
            yield sse({"type": "layer_start", "layer": 6})
            t0 = time.monotonic()
            await asyncio.sleep(0.02)
            l6_event = {
                "layer": 6,
                "status": "pass",
                "chip_label": "Logged",
                "detail": "SHA-256 block appended · immutable Blob written · GRS replicated",
                "sub_checks": [], "sub_scores": [],
                "latency_ms": int((time.monotonic() - t0) * 1000),
            }
            layer_events.append(l6_event)
            yield sse({"type": "layer_complete", "event": l6_event})

            # ── L7: Regulatory watch — cron, not per-tx ──────────────────────
            l7_skip = {
                "layer": 7, "status": "skip", "chip_label": "Cron-based",
                "detail": "Runs every 6h independently — not transaction-triggered",
                "sub_checks": [], "sub_scores": [],
            }
            layer_events.append(l7_skip)
            yield sse({"type": "layer_complete", "event": l7_skip})

            # ── Final result ─────────────────────────────────────────────────
            total_ms = int((time.monotonic() - start) * 1000)
            block_data = f"{tx.tx_id}:{total_ms}:{time.time()}"
            audit_hash = hashlib.sha256(block_data.encode()).hexdigest()

            result = {
                "tx_id": tx.tx_id,
                "verdict": l3_result.get("verdict", "clean"),
                "verdict_label": "STR auto-filed",
                "verdict_detail": "PMLA Rule 3 — structuring pattern confirmed by L3",
                "confidence_band": l3_result.get("band", "n_a"),
                "composite_score": l3_result.get("composite_score"),
                "sub_scores": l3_result.get("sub_scores", []),
                "l2_checks_fired": l2_result.get("checks", []) if not l1_result["cache_hit"] else [],
                "regulatory_basis": l3_result.get("regulatory_basis", []),
                "audit_block_hash": audit_hash,
                "processing_time_ms": total_ms,
                "layer_events": layer_events,
            }
            yield sse({"type": "result", "result": result})

        except Exception as exc:
            yield sse({"type": "error", "message": str(exc)})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disables Nginx buffering
        },
    )


# ── Synchronous fallback ─────────────────────────────────────────────────────
@app.post("/api/transactions")
async def submit_transaction(tx: Transaction):
    """Non-streaming version — collect all events and return at once."""
    events = []
    async for chunk in (await stream_transaction(tx)).body_iterator:
        if chunk.startswith(b"data:"):
            msg = json.loads(chunk[5:].strip())
            if msg["type"] == "result":
                return msg["result"]
            events.append(msg)
    return {"error": "Pipeline did not produce a result"}


# ── Health ───────────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {"status": "ok", "layers": list(range(8))}


# ── Result fetch (from Cosmos DB) ────────────────────────────────────────────
@app.get("/api/results/{tx_id}")
async def get_result(tx_id: str):
    # TODO: query Cosmos DB cases container
    # from compliance_pipeline.cosmos_client import get_case
    # return await get_case(tx_id)
    return {"error": "not implemented — wire up your Cosmos DB client here"}
