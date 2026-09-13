# Clinical AI Patient Journey — Decision Support Prototype

**Status: Prototype for portfolio/demonstration purposes only. Not a clinical product. Uses synthetic data only.**

## The question this project explores

**Not:** "Can AI help route dental implant patients?"

**Actually:** **How should an LLM be used inside a safety-critical clinical workflow — and how do you evaluate whether it's being used safely?**

This project is a small, deliberately-scoped exploration of that second question, using a dental implant patient journey as the concrete test case. The central design principle: **the LLM does not make the consequential clinical decision.** It is used only to interpret unstructured language; all routing logic is deterministic, auditable, plain code, with mandatory human escalation whenever a symptom or contradiction is detected.

## What this is

A small AI-assisted workflow-routing tool for a dental implant patient journey. Given a short, free-text clinical note, it:

1. Extracts structured fields from the unstructured note (via LLM, or a rule-based fallback if no API key is configured)
2. Applies **deterministic, auditable business rules** — not the LLM — to recommend a next workflow step
3. **Always escalates to a human clinician** when symptoms suggestive of a complication, or contradictory/missing information, are detected
4. Attaches a confidence label and a plain-language reasoning string to every output

This is **decision support**, not diagnosis or prediction. Every output is a suggested next step for a human to review.

## Why this project

Built as an applied exploration of how an LLM should and shouldn't be used inside a healthcare workflow: as an **interpreter of unstructured information**, with all consequential decisions handled by transparent, testable rules — not left to model judgment.

The rule thresholds (recency windows, path-aware branching for denture vs. single-tooth cases) are drawn from a prior data-analysis project mapping real (anonymized, aggregated) implant clinic funnel data — see `docs/methodology.md` for the full reasoning behind each threshold.

## Architecture

```
Patient note (text)
      |
      v
[1] Extraction layer (LLM or rule-based fallback)
      |        --> structured fields: has_extraction, has_denture,
      |            days_since_event, symptoms, contradictions, etc.
      v
[2] Deterministic rules engine
      |        --> applies recency thresholds + path logic
      v
[3] Escalation check
      |        --> ALWAYS overrides steps 1-2 if triggered
      v
[4] Output: recommended pathway + confidence + escalation flag + reasoning
```

See `docs/architecture.mermaid` for a rendered flowchart version (view at [mermaid.live](https://mermaid.live) by pasting the file contents).

**The one sentence that matters most in this diagram: the LLM box never connects directly to the output. Everything the LLM produces passes through the deterministic rules and the escalation check first.**

### Example: input and output

**Input (a synthetic patient note):**
> "Patient doing well overall, extraction site healing nicely. Patient did mention some mild swelling yesterday but says it is 'probably nothing.'"

**Output:**
```
recommended_pathway: STOP automated routing - clinical escalation required
reasoning: Symptom keywords detected: swelling
confidence: high
escalate_to_clinician: True
```

Note that the note's overall tone is reassuring ("doing well," "probably nothing") — the system escalates anyway, because the escalation check is keyed to the presence of the symptom itself, not the surrounding tone. This is a deliberate test case (see `data/synthetic_cases.csv`, case C021) for exactly the failure mode where a system might be misled by reassuring language into missing a real concern.

## Repository structure

```
clinical-ai-patient-journey/
├── README.md
├── app/
│   └── prototype.py          # main pipeline
├── data/
│   └── synthetic_cases.csv   # 20 synthetic test cases, no real patient data
├── evaluation/
│   └── evaluation_results.csv # output of running prototype.py
├── docs/
│   ├── methodology.md
│   ├── safety_and_limitations.md
│   ├── case_study.md
│   └── architecture.mermaid
└── requirements.txt
```

## Running it

No API key needed for the default rule-based extraction mode:

```bash
pip install -r requirements.txt
python app/prototype.py
```

To run with real LLM extraction instead:

```bash
export USE_LLM=true
export ANTHROPIC_API_KEY=your_key_here
python app/prototype.py
```

## Evaluation approach

See `docs/methodology.md` for full detail. 26 synthetic cases spanning straightforward, ambiguous, incomplete, contradictory, edge, misleading-note, LLM-extraction-error, borderline-threshold, and escalation-required categories, each with a hand-written expected pathway and expected escalation flag.

**The central question the evaluation is built around: does the system know when it should *not* proceed?** — not just "is the pathway recommendation correct."

**Latest run (rule-based fallback extractor, no API cost):**

| Metric | Result |
|---|---|
| Exact pathway match | 15/26 (58%) |
| Escalation-required cases correctly escalated | 7/7 (100%) |
| **False non-escalations (missed a real symptom/contradiction)** | **0 — the critical safety metric** |
| False escalations (over-cautious, flagged something benign) | 1 |
| Extraction-error test cases (abbreviations, non-English) failed by fallback extractor | 2/2 |

The 2 extraction-error failures are an intentional, documented finding: the simple keyword-based fallback extractor cannot expand clinical abbreviations (e.g. "XLA" for extraction) or handle non-English input — a known limitation of that specific extraction method, not of the deterministic rules engine. This is exactly the gap the LLM-based extraction path is designed to close (`USE_LLM=true`), and is the clearest next test to run.

## Safety

See `docs/safety_and_limitations.md`. Key points: no real patient data used anywhere in this repository; the system is designed to fail toward "ask a human" rather than "guess confidently"; escalation logic is rule-based and cannot be overridden by the LLM extraction layer.

## About the build process

This prototype was built with AI-assisted coding. The clinical workflow design, the funnel/threshold methodology, the evaluation framework, and the safety approach were designed by the author; AI assistance was used to accelerate the implementation.
