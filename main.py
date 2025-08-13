# main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import os
import time

from doctor_agent import doctor_reply
from symptom_extractor import extract_structured
from triage_engine import evaluate_triage
from guideline_verifier import verify
from utils import log_session, APP_PORT

app = FastAPI()

# Serve /static folder (CSS, JS, HTML)
app.mount("/static", StaticFiles(directory="static"), name="static")

SESSIONS = {}

# Serve index.html at root
@app.get("/")
def serve_home():
    index_path = os.path.join("static", "index.html")
    return FileResponse(index_path)

# Avoid favicon 404 spam
@app.get("/favicon.ico")
def favicon():
    return JSONResponse(content={}, status_code=200)

class ChatRequest(BaseModel):
    session_id: str
    message: str

@app.post("/api/chat")
async def chat(req: ChatRequest):
    sid = req.session_id
    if sid not in SESSIONS:
        SESSIONS[sid] = []
    SESSIONS[sid].append({"role": "user", "content": req.message})

    # Doctor agent reply
    reply = doctor_reply(SESSIONS[sid])
    SESSIONS[sid].append({"role": "assistant", "content": reply})

    # Extract structured data
    conv_text = "\n".join([f"{m['role']}: {m['content']}" for m in SESSIONS[sid]])
    structured = extract_structured(conv_text)
    raw_triage = evaluate_triage(structured)

    top_diagnoses = []  
    verified = verify(raw_triage, top_diagnoses)

    # Urgent/Emergency handling
    if verified["level"] in ("Emergency", "Urgent"):
        context = (
            f"{verified['level']} — {verified['reason']}. Recommended action: "
            f"{'go to the nearest emergency department immediately' if verified['level']=='Emergency' else 'seek urgent medical attention'}."
        )
        final = doctor_reply(SESSIONS[sid], triage_context=context)
        SESSIONS[sid].append({"role": "assistant", "content": final})
        out_reply = final
    else:
        out_reply = reply

    # Log session
    log_session(sid, {
        "session": SESSIONS[sid],
        "structured": structured,
        "triage": verified,
        "ts": time.time()
    })

    return {"reply": out_reply, "triage": verified, "structured": structured}
