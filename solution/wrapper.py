"""YOUR mitigation + observability layer. The simulator calls mitigate() around the
opaque agent (a REAL LLM) for every request. This is the ONLY place observability can
live -- the agent is silent. Legal moves: retry / cache / route / guardrail / sanitize
/ fallback / session-reset / PROMPT ROUTING, plus your own logging/tracing/metrics.
"""
from __future__ import annotations
import time
import re
import os
import json

# Automatically load environment variables from .env if present
if os.path.exists(".env"):
    with open(".env", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()

from telemetry.logger import logger, new_correlation_id, set_correlation_id
from telemetry.cost import cost_from_usage

from telemetry.redact import redact_value, redact
from telemetry.tracing import Tracer

tracer = Tracer()

def sanitize_question(question: str) -> str:
    # Spot and neutralize prompt injection inside order notes (GHI CHÚ / Note)
    pattern = r'(ghi\s*chú|ghi\s*chu|note|notes)\s*[:\-]\s*(.*)'
    match = re.search(pattern, question, re.IGNORECASE)
    if match:
        prefix = question[:match.start()]
        label = match.group(1)
        # We replace the note content to avoid any injected instructions
        return f"{prefix}{label}: [Sanitized note content]"
    return question

def fix_total_format(answer: str) -> str:
    # Chuẩn hóa dòng Tong cong: để bỏ dấu phẩy/chấm phân cách ngàn.
    def clean_number(m):
        num_str = m.group(1).replace(',', '').replace('.', '')
        return f"Tong cong: {num_str} VND"
    
    answer = re.sub(
        r'Tong\s*cong:\s*([\d.,]+)\s*VND',
        clean_number,
        answer,
        flags=re.IGNORECASE
    )
    return answer

def mitigate(call_next, question, config, context):
    qid = context.get("qid", "unknown")
    session_id = context.get("session_id", "unknown")
    turn_index = context.get("turn_index", 0)
    
    # Establish correlation ID for request tracing
    cid = f"req-{qid}-{session_id}"
    set_correlation_id(cid)
    
    t0 = time.time()
    
    # Sanitization
    clean_q = sanitize_question(question)
    
    # Caching
    q_key = clean_q.strip().lower()
    with context["cache_lock"]:
        if config.get("cache", {}).get("enabled", True) and q_key in context["cache"]:
            cached_res = context["cache"][q_key]
            if logger:
                logger.log_event("CACHE_HIT", {
                    "qid": qid,
                    "session_id": session_id,
                    "question": question,
                    "answer": cached_res.get("answer"),
                })
            return cached_res

    # Tracing & Execution with Retry
    with tracer.start_span("mitigate_call", qid=qid, session_id=session_id) as span:
        max_attempts = config.get("retry", {}).get("max_attempts", 3)
        backoff_ms = config.get("retry", {}).get("backoff_ms", 100)
        
        res = None
        for attempt in range(max_attempts):
            try:
                res = call_next(clean_q, config)
                if res.get("status") == "ok":
                    break
                if res.get("status") in ("loop", "max_steps") and attempt < max_attempts - 1:
                    time.sleep(backoff_ms / 1000.0)
                    continue
            except Exception as e:
                if attempt < max_attempts - 1:
                    time.sleep(backoff_ms / 1000.0)
                else:
                    raise e
        
        if res is None:
            res = {
                "answer": "Xin lỗi, hệ thống đang gặp sự cố. Vui lòng thử lại sau.",
                "status": "wrapper_error",
                "steps": 0,
                "trace": [],
                "meta": {}
            }
            
        if res.get("answer"):
            res["answer"] = fix_total_format(res["answer"])
            
        # PII Redaction on response
        if config.get("redact_pii", True) and res.get("answer"):
            res["answer"] = redact_value(res["answer"])
            
        # Cache the result
        if config.get("cache", {}).get("enabled", True) and res.get("status") == "ok":
            with context["cache_lock"]:
                context["cache"][q_key] = res
                
        # Observability Logging
        wall_ms = int((time.time() - t0) * 1000)
        meta = res.get("meta", {}) or {}
        usage = meta.get("usage", {}) or {}
        cost = cost_from_usage(meta.get("model", ""), usage)
        
        span.set(
            status=res.get("status", "error"),
            wall_ms=wall_ms,
            reported_latency_ms=meta.get("latency_ms", 0),
            cost_usd=cost,
            tools_used=meta.get("tools_used", []),
            steps=res.get("steps", 0)
        )
        
        if logger:
            logger.log_event("AGENT_CALL", {
                "qid": qid,
                "session_id": session_id,
                "turn_index": turn_index,
                "status": res.get("status"),
                "reported_latency_ms": meta.get("latency_ms"),
                "wall_ms": wall_ms,
                "tokens": usage,
                "cost_usd": cost,
                "pii_removed": redact(res.get("answer") or "")[1] > 0,
                "tools_used": meta.get("tools_used", []),
                "steps": res.get("steps", 0),
            })
            
    return res
