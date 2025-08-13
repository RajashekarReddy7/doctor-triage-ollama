# triage_engine.py
def evaluate_triage(struct):
    """
    Returns dict: {"level": "Emergency/ Urgent/ Routine", "reason": "..."}
    """
    cc = (struct.get("chief_complaint") or "").lower()
    assoc = [s.lower() for s in struct.get("associated_symptoms", []) or []]
    severity = (struct.get("severity") or "").lower()
    vitals = struct.get("vitals") or {}

    # Red flag keywords
    red_flags = ["chest pain", "shortness of breath", "severe bleeding", "unconscious", 
                 "sudden weakness", "slurred speech", "seizure", "altered mental", "difficulty breathing"]

    for rf in red_flags:
        if rf in cc or any(rf in s for s in assoc):
            return {"level": "Emergency", "reason": f"detected: '{rf}'."}

    # Basic vitals thresholds (if values present)
    try:
        hr = int(vitals.get("hr") or 0)
        sbp = int(vitals.get("sbp") or 0)
        temp = float(vitals.get("temp") or 0)
    except:
        hr, sbp, temp = 0, 0, 0.0

    if hr and hr > 130:
        return {"level": "Emergency", "reason": "Very high heart rate (tachycardia)."}

    if sbp and sbp < 90:
        return {"level": "Emergency", "reason": "Low blood pressure (hypotension)."}

    # Urgent cases
    if "severe" in severity or ("high fever" in severity or temp >= 39.0):
        return {"level": "Urgent", "reason": "High severity or fever present."}
    if any(s for s in assoc if "blood" in s or "fever" in s and "high" in s):
        return {"level": "Urgent", "reason": "Concerning associated symptoms."}

    # default
    return {"level": "Routine", "reason": "No red flags found; symptoms appear non-urgent."}
