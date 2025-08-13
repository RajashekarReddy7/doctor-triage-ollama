# guideline_verifier.py
import json, os

GUIDELINE_PATH = "data/guidelines.json"

def load_guidelines():
    if not os.path.exists(GUIDELINE_PATH):
        return {}
    with open(GUIDELINE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

GUIDELINES = load_guidelines()

def verify(triage_result, top_diagnoses=[]):
    """
    triage_result: {"level":..., "reason":...}
    top_diagnoses: list of strings
    Returns possibly adjusted triage_result
    """
    # Very simple: if any diagnosis in top_diagnoses maps to a more severe level, upgrade
    level_priority = {"Emergency": 3, "Urgent": 2, "Routine": 1}
    level = triage_result["level"]
    for d in top_diagnoses:
        doc = GUIDELINES.get(d.lower())
        if doc:
            recommended = doc.get("recommended_triage", "Routine")
            if level_priority.get(recommended, 1) > level_priority.get(level, 1):
                return {"level": recommended, 
                        "reason": f"Upgraded per guideline for {d}: {doc.get('note','')}"}
    return triage_result
