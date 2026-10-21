"""Minimal FastAPI proxy for a deployed A2A agent (Agent Runtime, agents-cli 1.1.0+).

The browser talks ONLY to this proxy (same origin, no CORS, no GCP creds in the
browser). The proxy authenticates with Application Default Credentials and
forwards chat to the deployed agent over the A2A protocol, returning replies as
structured parts the chat UI knows how to show:

  * {"kind": "text", "text": ...}  -> a normal chat bubble
  * {"kind": "a2ui", "data": ...}  -> one A2UI message (beginRendering /
    surfaceUpdate); static/index.html renders these as a card.

Why A2A: agents-cli 1.1.0 (GA) deploys ADK agents to Agent Runtime as A2A agents
and no longer registers the reasoning-engine operation schema the old
`agent_engines.get(...).stream_query()` path relied on (operation_schemas() comes
back empty). The container serves the A2A protocol over the Agent Engine HTTP
passthrough, so this proxy fetches the agent's card and sends messages with the
a2a-sdk client (the same path `agents-cli run --mode a2a` uses). This works for
both A2A and plain ADK 1.1.0 deployments (the container serves A2A either way).

Run:
  pip install -r requirements.txt
  export AGENT_ENGINE_RESOURCE_NAME="projects/.../locations/.../reasoningEngines/..."
  export AGENT_DIRECTORY="app"   # your agent's app directory (agents-cli-manifest.yaml)
  python main.py                 # -> http://localhost:8080
"""

import json
import os
import uuid

import google.auth
import google.auth.transport.requests
import httpx
from a2a.client import ClientConfig, create_client
from a2a.types import (
    Message,
    Part,
    Role,
    SendMessageRequest,
)
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

def _get_resource_name() -> str:
    if res := os.environ.get("AGENT_ENGINE_RESOURCE_NAME"):
        return res
    meta_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "deployment_metadata.json",
    )
    if os.path.exists(meta_path):
        try:
            with open(meta_path) as f:
                data = json.load(f)
                if runtime_id := data.get("remote_agent_runtime_id"):
                    return runtime_id
        except Exception:
            pass
    return "projects/1077991826923/locations/us-east1/reasoningEngines/3171636947831488512"


RESOURCE = _get_resource_name()
# The agent's app directory (matches agent_directory in agents-cli-manifest.yaml).
AGENT_DIRECTORY = os.environ.get("AGENT_DIRECTORY", "app")
# Location is embedded in the resource name: projects/<p>/locations/<loc>/reasoningEngines/<id>.
LOCATION = RESOURCE.split("/locations/")[1].split("/")[0]

# A2A endpoint for an Agent Runtime deployment, via the Agent Engine HTTP
# passthrough. The card lives at the well-known path under this base.
A2A_BASE = (
    f"https://{LOCATION}-aiplatform.googleapis.com/reasoningEngines/v1/"
    f"{RESOURCE}/api/a2a/{AGENT_DIRECTORY}"
)
A2A_CARD_URL = f"{A2A_BASE}/.well-known/agent-card.json"

# The agent tags its A2UI data parts with this mime type.
_A2UI_MIME = "application/json+a2ui"

# One set of ADC credentials, refreshed per request (access tokens expire ~1h).
_creds, _ = google.auth.default(
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)


def _auth_headers() -> dict[str, str]:
    _creds.refresh(google.auth.transport.requests.Request())
    return {
        "Authorization": f"Bearer {_creds.token}",
        "Content-Type": "application/json",
    }


app = FastAPI()


@app.exception_handler(Exception)
async def _json_errors(request: Request, exc: Exception):
    # Always return JSON so the browser never receives a plain-text 500 page
    # (which shows up in the chat as "Unexpected token 'I', "Internal S"... is
    # not valid JSON"). Any server-side failure now surfaces as a readable
    # message in the chat bubble instead.
    return JSONResponse(
        status_code=200,
        content={
            "parts": [{"kind": "text", "text": f"Error: {type(exc).__name__}: {exc}"}]
        },
    )


# Reuse ONE A2A context per user so the agent remembers the conversation.
_contexts: dict[str, str] = {}


def _extract_parts(parts: list) -> list[dict]:
    """Turn A2A response parts into structured parts for the chat UI.

    Text parts pass through as {"kind": "text"}. A2UI data parts (tagged
    application/json+a2ui) become {"kind": "a2ui", "data": <message>} so the UI
    renders the card; each data part is one A2UI message (beginRendering or
    surfaceUpdate).
    """
    out: list[dict] = []
    for p in parts:
        root = getattr(p, "root", p)
        text = getattr(root, "text", None)
        if isinstance(root, dict):
            text = root.get("text")
        if text:
            out.append({"kind": "text", "text": text})
            continue

        data = getattr(root, "data", None)
        if isinstance(root, dict):
            data = root.get("data")
        if data is not None:
            meta = getattr(root, "metadata", None) or {}
            mime = meta.get("mimeType") if isinstance(meta, dict) else None
            if not mime or mime == _A2UI_MIME:
                out.append({"kind": "a2ui", "data": data})
            continue

        raw = getattr(root, "raw", None)
        if raw:
            try:
                decoded = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
                out.append({"kind": "text", "text": decoded})
            except Exception:
                pass
    return out


@app.post("/chat")
async def chat(req: Request):
    body = await req.json()
    message = body.get("message", "")
    user_id = body.get("user_id") or "web-user"
    parts: list[dict] = []

    async with httpx.AsyncClient(headers=_auth_headers(), timeout=120) as client:
        a2a_client = await create_client(
            A2A_BASE,
            client_config=ClientConfig(httpx_client=client),
        )

        msg = Message(
            message_id=str(uuid.uuid4()),
            role=Role.ROLE_USER,
            parts=[Part(text=message)],
            context_id=_contexts.get(user_id),
        )
        req_obj = SendMessageRequest(message=msg)

        status_parts: list[dict] = []
        artifact_parts: list[dict] = []
        async for event in a2a_client.send_message(req_obj):
            if event.HasField("artifact_update"):
                artifact_parts.extend(_extract_parts(event.artifact_update.artifact.parts))
            elif event.HasField("status_update"):
                su = event.status_update
                if su.context_id:
                    _contexts[user_id] = su.context_id
                if su.status.HasField("message"):
                    status_parts.extend(_extract_parts(su.status.message.parts))
            elif event.HasField("task"):
                if event.task.context_id:
                    _contexts[user_id] = event.task.context_id
            elif event.HasField("message"):
                status_parts.extend(_extract_parts(event.message.parts))

        parts = artifact_parts if artifact_parts else status_parts

    if not parts:
        # The turn produced no text or UI (e.g. the agent only ran tools, or a
        # tool stalled). Be honest rather than silent.
        parts = [{"kind": "text", "text": "(The agent didn't return a reply.)"}]
    return JSONResponse({"parts": parts})


STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
# Serve the chat UI (keep this mount last so /chat wins).
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
