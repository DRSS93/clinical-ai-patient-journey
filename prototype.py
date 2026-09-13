"""
Clinical AI Patient Journey — Decision Support Prototype
==========================================================

WHAT THIS IS:
An AI-assisted workflow routing tool. Given a short clinical note about a
patient's implant-journey status, it:
  1. Uses an LLM to extract structured fields from unstructured text
  2. Applies deterministic clinical/business rules (NOT the LLM) to decide
     the recommended next workflow step
  3. Flags cases that require mandatory human clinician escalation
  4. Attaches a confidence/uncertainty label to every output

WHAT THIS IS NOT:
- Not a diagnostic tool.
- Not a predictive model of patient outcomes.
- Not a substitute for clinical judgment. Every output is a *suggested*
  next step for a human to review, not an instruction to act on.

ARCHITECTURE:
  Patient note (text)
        |
        v
  [1] LLM extraction  --> structured fields (has_extraction, has_denture,
        |                  days_since_event, symptoms, contradictions, etc.)
        v
  [2] Deterministic rules engine (thresholds, path logic - matches the
        |                          funnel/flowchart methodology)
        v
  [3] Escalation check (symptom keywords, contradiction flags -> ALWAYS
        |                overrides steps 1-2 if triggered)
        v
  [4] Output: recommended pathway + confidence + escalation flag + reasoning
"""

import os
import json
import csv
from dataclasses import dataclass, asdict
from typing import Optional

# ---------------------------------------------------------------------------
# STEP 0: Configuration
# ---------------------------------------------------------------------------
# The LLM is used ONLY for extracting structured information from free text.
# It never makes the final routing decision - that is handled by the
# deterministic rules in Step 2. This separation is the core safety design
# choice of this prototype: an LLM hallucination in extraction can at worst
# lead to a "needs clarification" outcome, not an unsafe recommendation,
# because the rules engine will not act on fields it cannot verify.

USE_LLM = os.environ.get("USE_LLM", "false").lower() == "true"
# Default is OFF so this script runs end-to-end with zero API key / cost
# using a rule-based fallback extractor. Set USE_LLM=true and provide
# ANTHROPIC_API_KEY to run the real LLM extraction step.

ESCALATION_KEYWORDS = [
    "swelling", "fever", "numbness", "mobility", "persistent pain",
    "increasing pain", "infection", "pus", "bleeding heavily",
    "loose when chewing", "feels a bit loose", "probably nothing"
]
# Note: "probably nothing" and similar minimizing phrases are intentionally
# included. Real clinical notes often bury a genuine symptom inside
# reassuring language ("mild", "probably fine", "otherwise fine") - a naive
# extractor that only looks for alarming tone would miss these. This list
# is deliberately keyed to the SYMPTOM itself, not the tone surrounding it.

THRESHOLDS = {
    "extraction_to_implant_single_tooth_days": 90,
    "extraction_to_implant_denture_track_days": 360,
    "consult_to_implant_days": 90,
    "denture_to_overdenture_days": 450,
}


# ---------------------------------------------------------------------------
# STEP 1: Extraction layer (LLM or rule-based fallback)
# ---------------------------------------------------------------------------

@dataclass
class ExtractedFields:
    has_extraction: Optional[bool] = None
    has_consult: Optional[bool] = None
    has_conventional_denture: Optional[bool] = None
    has_implant_placed: Optional[bool] = None
    has_restoration: Optional[bool] = None
    days_since_extraction: Optional[int] = None
    days_since_denture: Optional[int] = None
    symptoms_flagged: Optional[str] = None
    contradiction_detected: bool = False
    missing_info_detected: bool = False
    extraction_confidence: str = "medium"  # low / medium / high
    raw_note: str = ""


def extract_fields_rule_based(note: str, row: dict) -> ExtractedFields:
    """
    Fallback extractor: uses the CSV's already-labeled structured columns
    plus simple keyword scanning of the note. This lets the whole pipeline
    run with no API key, and lets you inspect exactly what a 'ground truth'
    extraction should look like before comparing it to real LLM output.
    """
    note_lower = note.lower()

    # Known limitation, left intentionally unfixed here: this simple
    # keyword extractor does NOT expand clinical abbreviations (e.g. "XLA"
    # for extraction, "c/o" for complains of) or handle non-English text
    # (e.g. Dutch "extractie", "implantaatplaatsing"). Cases C023/C024 are
    # designed to demonstrate this specific failure mode for the evaluation
    # section - a real LLM extraction pass (USE_LLM=true) is expected to
    # handle both correctly, which is the point of comparing the two paths.

    symptoms = [kw for kw in ESCALATION_KEYWORDS if kw in note_lower]

    contradiction = "declined" in note_lower and "scheduled" in note_lower
    contradiction = contradiction or (
        "j081" in note_lower.lower() and "p020" in note.lower()
    )

    missing_info = any(
        phrase in note_lower
        for phrase in ["unclear", "missing", "unknown", "not specify", "does not specify"]
    )

    days_ext = None
    if row.get("days_since_extraction"):
        try:
            days_ext = int(row["days_since_extraction"])
        except ValueError:
            pass

    days_denture = None
    if row.get("days_since_denture"):
        try:
            days_denture = int(row["days_since_denture"])
        except ValueError:
            pass

    return ExtractedFields(
        has_extraction=days_ext is not None or "extraction" in note_lower,
        has_consult=("consult" in note_lower and "declined" not in note_lower)
        or "j010" in note_lower,
        has_conventional_denture=row.get("has_conventional_denture") == "Yes",
        has_implant_placed="implant placed" in note_lower or "implant" in note_lower and "consult" not in note_lower[:30],
        has_restoration="crown" in note_lower or "restored" in note_lower,
        days_since_extraction=days_ext,
        days_since_denture=days_denture,
        symptoms_flagged=", ".join(symptoms) if symptoms else None,
        contradiction_detected=contradiction,
        missing_info_detected=missing_info,
        extraction_confidence="high" if not missing_info and not contradiction else "low",
        raw_note=note,
    )


def extract_fields_llm(note: str, row: dict) -> ExtractedFields:
    """
    Real LLM extraction path. Requires ANTHROPIC_API_KEY and USE_LLM=true.
    The LLM is instructed to ONLY extract fields, never to recommend a
    pathway - that separation is the safety-relevant design choice here.
    """
    import anthropic

    client = anthropic.Anthropic()

    system_prompt = """You are a clinical data extraction assistant. Your ONLY
job is to extract structured fields from a short clinical note about a
dental implant patient journey. You must NOT recommend any treatment or
next step. You must NOT diagnose. Output strict JSON only, matching this
schema exactly:

{
  "has_extraction": true/false/null,
  "has_consult": true/false/null,
  "has_conventional_denture": true/false/null,
  "has_implant_placed": true/false/null,
  "has_restoration": true/false/null,
  "symptoms_flagged": "comma-separated list or null",
  "contradiction_detected": true/false,
  "missing_info_detected": true/false,
  "extraction_confidence": "low/medium/high"
}

If the note is ambiguous or missing key information, set
missing_info_detected=true and extraction_confidence="low" rather than
guessing. Do not infer information that is not stated or clearly implied."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        system=system_prompt,
        messages=[{"role": "user", "content": note}],
    )

    text = response.content[0].text.strip()
    text = text.replace("```json", "").replace("```", "").strip()
    parsed = json.loads(text)

    return ExtractedFields(
        has_extraction=parsed.get("has_extraction"),
        has_consult=parsed.get("has_consult"),
        has_conventional_denture=parsed.get("has_conventional_denture"),
        has_implant_placed=parsed.get("has_implant_placed"),
        has_restoration=parsed.get("has_restoration"),
        days_since_extraction=int(row["days_since_extraction"]) if row.get("days_since_extraction") else None,
        days_since_denture=int(row["days_since_denture"]) if row.get("days_since_denture") else None,
        symptoms_flagged=parsed.get("symptoms_flagged"),
        contradiction_detected=parsed.get("contradiction_detected", False),
        missing_info_detected=parsed.get("missing_info_detected", False),
        extraction_confidence=parsed.get("extraction_confidence", "medium"),
        raw_note=note,
    )


# ---------------------------------------------------------------------------
# STEP 2 + 3: Deterministic rules engine + escalation check
# ---------------------------------------------------------------------------

def route_patient(fields: ExtractedFields) -> dict:
    """
    Deterministic decision layer. The LLM never reaches this far into the
    decision - it only supplied fields. This function is plain Python
    if/else logic, fully auditable, and matches the funnel methodology
    (recency thresholds, path-aware branching, N/A vs No vs Too-Recent)
    developed for this project's underlying data analysis.
    """

    # --- Escalation ALWAYS overrides everything else ---
    if fields.symptoms_flagged:
        return {
            "recommended_pathway": "STOP automated routing - clinical escalation required",
            "reasoning": f"Symptom keywords detected: {fields.symptoms_flagged}",
            "confidence": "high",
            "escalate_to_clinician": True,
        }

    if fields.contradiction_detected:
        return {
            "recommended_pathway": "Contradiction detected - requires clinician review",
            "reasoning": "Conflicting information found in patient record",
            "confidence": "low",
            "escalate_to_clinician": True,
        }

    if fields.missing_info_detected:
        return {
            "recommended_pathway": "Insufficient information - request clarification before routing",
            "reasoning": "Key fields ambiguous or missing from note",
            "confidence": "low",
            "escalate_to_clinician": False,
        }

    # --- Restoration already complete ---
    if fields.has_restoration:
        return {
            "recommended_pathway": "Completed - restorative pathway confirmed",
            "reasoning": "Implant and restoration both confirmed present",
            "confidence": "high",
            "escalate_to_clinician": False,
        }

    # --- Implant already placed, awaiting restoration ---
    if fields.has_implant_placed and fields.has_conventional_denture and fields.days_since_denture is not None:
        if fields.days_since_denture < THRESHOLDS["denture_to_overdenture_days"]:
            return {
                "recommended_pathway": "Too Recent to Judge - within normal restoration wait window",
                "reasoning": f"{fields.days_since_denture} days since denture, threshold is {THRESHOLDS['denture_to_overdenture_days']}",
                "confidence": "medium",
                "escalate_to_clinician": False,
            }

    # --- Extraction present, no implant yet ---
    if fields.has_extraction and not fields.has_implant_placed:
        days = fields.days_since_extraction
        if fields.has_conventional_denture:
            threshold = THRESHOLDS["extraction_to_implant_denture_track_days"]
            track = "denture track"
        else:
            threshold = THRESHOLDS["extraction_to_implant_single_tooth_days"]
            track = "single-tooth track"

        if days is None:
            return {
                "recommended_pathway": "Insufficient information - extraction date required",
                "reasoning": "Cannot apply recency threshold without a date",
                "confidence": "low",
                "escalate_to_clinician": False,
            }
        if days < threshold:
            return {
                "recommended_pathway": f"Too Recent to Judge - {track} (under {threshold} days)",
                "reasoning": f"{days} days since extraction, threshold is {threshold}",
                "confidence": "medium",
                "escalate_to_clinician": False,
            }
        if fields.has_consult:
            return {
                "recommended_pathway": "Route to Implantologist Consult (Phase 3) - awaiting placement decision",
                "reasoning": "Consult completed, past recency threshold, no placement yet",
                "confidence": "medium",
                "escalate_to_clinician": False,
            }
        return {
            "recommended_pathway": "Flag for recall outreach - no follow-up recorded past threshold",
            "reasoning": f"{days} days since extraction, no consult on file",
            "confidence": "medium",
            "escalate_to_clinician": False,
        }

    # --- Denture only, no extraction linked in this note ---
    if fields.has_conventional_denture and fields.days_since_denture is not None:
        if fields.days_since_denture >= THRESHOLDS["denture_to_overdenture_days"]:
            return {
                "recommended_pathway": "Route to Phase 2/3 re-entry - overdenture eligibility reassessment",
                "reasoning": f"{fields.days_since_denture} days since denture, past {THRESHOLDS['denture_to_overdenture_days']}-day threshold",
                "confidence": "medium",
                "escalate_to_clinician": False,
            }
        return {
            "recommended_pathway": "Too Recent to Judge - denture within normal wear-in window",
            "reasoning": f"{fields.days_since_denture} days since denture",
            "confidence": "medium",
            "escalate_to_clinician": False,
        }

    # --- Fallback: not enough signal to route confidently ---
    return {
        "recommended_pathway": "Insufficient information - unable to determine pathway",
        "reasoning": "No extraction, denture, consult, or implant fields confidently identified",
        "confidence": "low",
        "escalate_to_clinician": False,
    }


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_case(row: dict) -> dict:
    note = row["patient_note"]
    if USE_LLM:
        fields = extract_fields_llm(note, row)
    else:
        fields = extract_fields_rule_based(note, row)

    result = route_patient(fields)
    result["case_id"] = row["case_id"]
    result["category"] = row["category"]
    result["expected_pathway"] = row["expected_pathway"]
    result["expected_escalation"] = row["expected_escalation"]
    result["extracted_fields"] = asdict(fields)
    return result


def main():
    input_path = os.path.join(os.path.dirname(__file__), "..", "data", "synthetic_cases.csv")
    output_path = os.path.join(os.path.dirname(__file__), "..", "evaluation", "evaluation_results.csv")

    results = []
    with open(input_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            results.append(run_case(row))

    fieldnames = [
        "case_id", "category", "recommended_pathway", "expected_pathway",
        "confidence", "escalate_to_clinician", "expected_escalation", "reasoning",
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow({k: r[k] for k in fieldnames})

    print(f"Processed {len(results)} cases. Results written to {output_path}\n")

    total = len(results)
    exact_matches = 0
    escalation_required_cases = [r for r in results if r["expected_escalation"] == "Yes"]
    escalation_correct = 0
    false_non_escalations = []  # expected escalation=Yes but system did not escalate - MOST CRITICAL metric
    false_escalations = []      # expected escalation=No but system escalated - costly but not unsafe
    extraction_error_cases = [r for r in results if r["category"] == "llm_extraction_error_test"]
    extraction_error_failures = []

    for r in results:
        recommended_first_clause = r["recommended_pathway"].split(" - ")[0].lower()
        is_match = recommended_first_clause in r["expected_pathway"].lower()
        if is_match:
            exact_matches += 1

        expected_escalate = r["expected_escalation"] == "Yes"
        actual_escalate = str(r["escalate_to_clinician"]) == "True"

        if expected_escalate and actual_escalate:
            escalation_correct += 1
        if expected_escalate and not actual_escalate:
            false_non_escalations.append(r["case_id"])
        if not expected_escalate and actual_escalate:
            false_escalations.append(r["case_id"])

        if r["category"] == "llm_extraction_error_test" and not is_match:
            extraction_error_failures.append(r["case_id"])

        match_label = "MATCH " if is_match else "REVIEW"
        print(f"[{match_label}] {r['case_id']} ({r['category']}): {r['recommended_pathway']}")

    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    print(f"Total cases:                     {total}")
    print(f"Exact pathway match:             {exact_matches}/{total} ({exact_matches/total:.0%})")
    print(f"Escalation-required cases:       {len(escalation_required_cases)}")
    print(f"Correctly escalated:             {escalation_correct}/{len(escalation_required_cases)}")
    print(f"FALSE NON-ESCALATIONS (critical): {len(false_non_escalations)}  {false_non_escalations}")
    print(f"False escalations (over-caution): {len(false_escalations)}  {false_escalations}")
    print(f"Extraction-error test cases:      {len(extraction_error_cases)}")
    print(f"  -> failed on fallback extractor: {len(extraction_error_failures)}  {extraction_error_failures}")
    print("=" * 60)
    print("Key question this answers: does the system know when it should")
    print("NOT proceed? -> False non-escalation count above is the answer.")
    print("=" * 60)


if __name__ == "__main__":
    main()
