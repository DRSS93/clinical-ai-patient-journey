# Clinical AI Patient Journey — Decision Support Prototype

**Status: Prototype for portfolio/demonstration purposes only. Not a clinical product. Uses synthetic data only.**

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
│   └── safety_and_limitations.md
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

See `docs/methodology.md` for full detail. In short: 20 synthetic cases spanning straightforward, ambiguous, incomplete, contradictory, edge, and escalation-required categories, each with a hand-written expected pathway. The script's output is compared against expected pathway per case, and failure modes are categorized (see evaluation results and methodology doc).

## Safety

See `docs/safety_and_limitations.md`. Key points: no real patient data used anywhere in this repository; the system is designed to fail toward "ask a human" rather than "guess confidently"; escalation logic is rule-based and cannot be overridden by the LLM extraction layer.

## About the build process

This prototype was built with AI-assisted coding. The clinical workflow design, the funnel/threshold methodology, the evaluation framework, and the safety approach were designed by the author; AI assistance was used to accelerate the implementation.
