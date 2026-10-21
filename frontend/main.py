"""FastAPI backend & proxy for IELTS Master Coach Web Chat UI.
Runs the local ADK agent with full domain tools, Memory Bank,
Cloud Storage chart generator, and A2UI presentation.
"""

import json
import logging
import os
import re
import sys
import uuid
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ielts-frontend")

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"
os.environ["GOOGLE_CLOUD_PROJECT"] = "qwiklabs-gcp-03-e3b544ecf171"
os.environ["GOOGLE_CLOUD_LOCATION"] = "us-east1"

from app.agent import app as adk_app
from app.app_utils import services
from google.adk.runners import Runner
from google.genai import types

# Initialize ADK Runner with Vertex AI Memory Bank and Session services
runner = Runner(
    app=adk_app,
    session_service=services.get_session_service(),
    artifact_service=services.get_artifact_service(),
    memory_service=services.get_memory_service(),
    auto_create_session=True,
)

app = FastAPI(title="IELTS Master Coach Frontend Proxy")
_sessions: dict[str, str] = {}


def _clean_markdown_json(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()


def _extract_ui_or_text(text: str) -> list[dict]:
    out = []
    if "<a2a_datapart_json>" in text:
        m = re.search(r"<a2a_datapart_json>(.*?)</a2a_datapart_json>", text, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(1).strip())
                out.append({"kind": "a2ui", "data": data})
                rest = text.replace(m.group(0), "").strip()
                if rest:
                    out.append({"kind": "text", "text": rest})
                return out
            except Exception:
                pass

    stripped = _clean_markdown_json(text)
    if (stripped.startswith("[") or stripped.startswith("{")) and (
        "card" in stripped or "surfaceUpdate" in stripped or "beginRendering" in stripped
    ):
        try:
            data = json.loads(stripped)
            out.append({"kind": "a2ui", "data": data})
            return out
        except Exception:
            pass

    out.append({"kind": "text", "text": text})
    return out


@app.exception_handler(Exception)
async def _global_exc_handler(_req: Request, exc: Exception):
    logger.exception("Chat handler error: %s", exc)
    return JSONResponse(
        status_code=200,
        content={
            "parts": [{"kind": "text", "text": f"Error: {type(exc).__name__}: {exc}"}]
        },
    )


@app.post("/chat")
async def chat(req: Request):
    body = await req.json()
    message = body.get("message", "")
    user_id = body.get("user_id") or "web-user"
    session_id = _sessions.setdefault(user_id, f"sess-{uuid.uuid4().hex[:8]}")

    parts: list[dict] = []
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=types.Content(
            role="user",
            parts=[types.Part.from_text(text=message)],
        ),
    ):
        if event.content and event.content.parts:
            for p in event.content.parts:
                if p.text:
                    extracted = _extract_ui_or_text(p.text)
                    parts.extend(extracted)

    if not parts:
        parts = [{"kind": "text", "text": "(The agent didn't return a reply.)"}]

    return JSONResponse({"parts": parts})


STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
