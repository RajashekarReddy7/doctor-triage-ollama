# doctor_agent.py
import requests
from utils import OLLAMA_URL, MODEL_NAME
import json
import re

SYSTEM_PROMPT = """You are a compassionate general practice physician.
Your replies must be short, clear, and focused — no more than 3–4 sentences.
Ask open-ended questions first, then clarifying questions.
Use empathetic, non-alarming language. Avoid jargon or explain it simply.
Do not give a definitive diagnosis — focus on understanding symptoms, severity, timing, and red flags.
When provided a triage_context, deliver it clearly and explain next steps.
Avoid unnecessary repetition or filler words.
"""

def _call_ollama(prompt, max_tokens=180):  # reduced from 400
    url = f"{OLLAMA_URL}/api/generate"
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "max_tokens": max_tokens,
        "temperature": 0.25,
        "stream": False
    }
    r = requests.post(url, json=payload, timeout=60)
    r.raise_for_status()
    resp = r.json()

    if isinstance(resp, dict) and "response" in resp:
        return resp["response"]

    return json.dumps(resp)

def _shorten_reply(text, max_sentences=4):
    """Trim reply to a set number of sentences without cutting mid-sentence."""
    sentences = re.split(r'(?<=[.!?]) +', text.strip())
    if len(sentences) > max_sentences:
        sentences = sentences[:max_sentences]
    return " ".join(sentences).strip()

def build_prompt(message_history, triage_context=None):
    prompt = SYSTEM_PROMPT + "\n\n"
    for m in message_history:
        role = "Patient" if m["role"] == "user" else "Doctor"
        prompt += f"{role}: {m['content']}\n"
    prompt += "\nDoctor:"
    if triage_context:
        prompt += f"\n\n[TRIAGE_CONTEXT]: {triage_context}\n"
    return prompt

def doctor_reply(message_history, triage_context=None):
    prompt = build_prompt(message_history, triage_context)
    raw_reply = _call_ollama(prompt)
    return _shorten_reply(raw_reply)