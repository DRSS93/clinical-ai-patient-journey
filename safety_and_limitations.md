# Safety and Limitations

## This is a prototype, not a clinical product

Nothing in this repository should be used to make an actual clinical or treatment decision for a real patient. It is a demonstration of an architectural approach and an evaluation methodology.

## Data safety

- **No real patient data is used anywhere in this repository.** `data/synthetic_cases.csv` is entirely hand-written synthetic content.
- The methodology and thresholds referenced were informed by prior work on anonymized, aggregated clinic-level data (counts and rates only — no patient-identifiable information was ever part of that analysis or is part of this repository).
- If this approach were ever adapted to work with real patient data, it would require: a formal data governance and consent review, de-identification appropriate to the jurisdiction (e.g., GDPR in the Netherlands/EU context), and a clinical safety/regulatory review before any use beyond an internal, non-patient-facing prototype.

## Design choices made specifically for safety

1. **LLM is restricted to extraction only.** It cannot output a treatment recommendation directly. All routing decisions pass through deterministic, human-readable rules.
2. **Escalation logic cannot be overridden by lower layers.** If symptom keywords are detected, the system stops and returns an escalation flag regardless of what any other field says — this check runs first, before any pathway logic.
3. **The system fails toward asking a human, not guessing.** Ambiguous, incomplete, or contradictory information produces an explicit "insufficient information" or "requires clinician review" output rather than a confident-sounding but unsupported recommendation.
4. **Every output includes a plain-language reasoning string.** No output is a bare label — the system always states which fields drove the recommendation, so a human reviewer can quickly sanity-check it.
5. **Confidence labeling.** Every output carries a low/medium/high confidence tag tied to how much the extraction layer had to infer versus directly observe.

## Known limitations (honest list)

- **Thresholds are provisional, not empirically validated.** The 90/360/450-day windows are reasoned estimates based on plausible clinical/administrative timelines, not fitted to a real, verified conversion-lag distribution. See `docs/methodology.md` section 3.
- **The rule-based fallback extractor is simple and keyword-driven.** It is meant as a zero-cost way to run the pipeline end-to-end, not as a serious extraction method. Real deployment would rely on the LLM extraction path, with its own separate evaluation.
- **Small evaluation set.** 20 synthetic cases is enough to demonstrate the evaluation methodology, not enough to make statistically confident claims about accuracy. A production evaluation would need a substantially larger and more systematically constructed test set (see methodology.md, section 5).
- **No handling of multi-turn or evolving patient records.** Each case is treated as a single static note; a real system would need to handle updates over time and reconcile new information with prior extractions.
- **No clinical validation.** The expected pathways in the synthetic dataset were authored by a single person with clinical (dental) background, not independently verified by multiple clinicians. Real deployment would need multi-rater review of ground truth labels.
- **English-only, dental-implant-specific.** Not generalized to other specialties or languages.

## What this prototype is intended to demonstrate

Not "an AI that makes clinical decisions" — rather, a worked example of how to structure an AI-assisted workflow tool so that:
- the LLM's role is narrow and bounded,
- the consequential logic is transparent and testable,
- safety-critical escalation cannot be silently skipped, and
- the system is evaluated against explicit expected outcomes and named failure modes, rather than judged only by whether the demo "looks impressive."
