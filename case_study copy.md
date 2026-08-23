# Case Study: AI-Assisted Clinical Workflow Decision Support for Dental Implant Patient Journeys

## Summary

This project explores how an AI language model can be safely integrated into a healthcare workflow — not as a decision-maker, but as an interpreter of unstructured clinical notes, feeding into a transparent, rule-based system that a human clinician ultimately reviews. It was built as a small working prototype, evaluated against a deliberately constructed set of test cases, and documented with the same rigor as the underlying clinical/data reasoning it draws from.

---

## 1. The problem

In a multi-clinic dental implant practice, a patient's journey — extraction, consult, implant placement, restoration, or extraction, denture, overdenture — unfolds over months to years and is scattered across separate visits and billing events. Two practical problems make it hard to manage this well at scale:

1. **Unstructured information.** Much of what actually matters about a patient's status lives in free-text clinical notes, not clean database fields.
2. **Time ambiguity.** A patient who "hasn't converted to the next step yet" looks identical, in a simple snapshot, to a patient who has genuinely dropped out of the funnel — unless you account for how much time has realistically passed since their last recorded event.

This project asks: can an AI system help triage and route these cases, while remaining safe, transparent, and appropriately cautious?

## 2. Approach

The system is built as a four-stage pipeline, deliberately separating what the AI is allowed to do from what it isn't:

```
Patient note (free text)
        |
        v
[1] Extraction — AI reads the note and pulls out structured facts only
        (has an extraction happened? a denture? symptoms mentioned? etc.)
        v
[2] Deterministic rules — plain, auditable logic applies time thresholds
        and path logic to those facts (not the AI)
        v
[3] Escalation check — always runs, cannot be skipped, flags anything
        symptom-related straight to a human
        v
[4] Output — a suggested next step, a confidence level, and a plain-
        English reason, for a human to review
```

**The key design decision:** the AI model never recommends a treatment or next step directly. It only extracts facts from text. All consequential decisions are made by ordinary, readable code — the kind of logic anyone could step through line by line and understand. This means an AI misreading a note can, at worst, lead to an "unclear, ask a human" outcome — never an unsafe recommendation acted on directly.

The time-based thresholds used in the rules layer (e.g., how long to wait before treating "no implant yet" as a real drop-off rather than "just not due yet") were derived from a prior analysis of real, anonymized clinic-level funnel data — reasoning through realistic healing, scheduling, and insurance-reimbursement timelines for different treatment paths (a fast single-tooth case vs. a longer denture-to-overdenture case). That prior analysis used structured billing codes and dates (the Dutch NZa dental code system — e.g., J010 for implant consult, J040/J041 for implant placement, P020-P022 for conventional dentures, J080-J082 for implant-retained overdentures).

**Why build this around free-text notes instead of structured codes?** Where clean codes and dates already exist, no AI is needed — the same threshold logic can be applied directly via a database query. This prototype deliberately targets the layer that structured data doesn't cover: free-text notes, referral letters, and patient messages, which are common in real clinical settings but aren't reducible to a billing code. That is the layer where an LLM adds genuine value; applying AI to already-structured data would not demonstrate anything AI is actually needed for.

## 3. Evaluation

Rather than just building something that looks impressive in a demo, the project treats evaluation as the central piece of work.

**Method:** 20 synthetic (entirely made-up, no real patient data) case notes were written to deliberately cover:
- Straightforward cases
- Ambiguous cases (a genuinely unclear fact)
- Incomplete cases (missing information)
- Contradictory cases (conflicting statements)
- Edge cases (fast-track same-day treatment, external referrals, self-pay patients, incomplete history)
- Escalation-required cases (symptoms suggesting a possible complication)

Each case has a hand-written "expected outcome" — what a human reviewer would want the system to conclude. The system's actual output is then compared against that expectation.

**What's measured**, beyond simple right/wrong:
- **Escalation sensitivity** — did every symptom-flagged case correctly stop and escalate? (The single most important safety metric.)
- **False reassurance** — did the system ever sound confident about a case that was actually ambiguous or risky?
- **Appropriate caution** — did unclear cases correctly resolve to "needs more information" rather than a guess?
- **Consistency** — do similar cases get treated the same way?

**Result:** Using the simplest possible extraction method (keyword matching, no AI model called at all), the system correctly escalated all 3 symptom-flagged cases and correctly flagged both contradictory cases — zero missed escalations, which is the metric that matters most from a safety standpoint. Several straightforward cases were routed to "insufficient information" rather than their specific expected pathway, which is a known limitation of the simple keyword extractor, not the decision rules themselves — and points directly to where a real AI-based extraction step should improve results next.

## 4. Safety approach

- **No real patient data anywhere in this project.** All test cases are fabricated.
- **The AI's role is bounded.** It extracts facts; it does not decide.
- **Escalation cannot be overridden.** The symptom check runs first and always wins, regardless of what any other part of the system concludes.
- **The system defaults to caution.** When information is missing or contradictory, the output is "ask a human" — never a confident guess dressed up as an answer.
- **Every output explains itself.** No bare label is ever returned without a plain-language reason attached, so a reviewer can quickly sanity-check it.

## 5. Honest limitations

- The time thresholds are reasoned estimates, not yet validated against real, verified conversion-timing data.
- The keyword-based extraction method used for the evaluation above is simple by design; a production system would rely on the AI-based extraction step, evaluated separately.
- 20 cases is enough to demonstrate the evaluation approach, not enough for statistically confident accuracy claims.
- Expected outcomes were authored by one person with clinical background, not independently verified by multiple reviewers.
- This is a prototype for demonstration purposes — not a validated clinical tool, and not intended for use on real patients in its current form.

## 6. What this demonstrates

Not "an AI that makes clinical decisions" — instead, a worked example of how to build an AI-assisted tool for a healthcare workflow so that the AI's role stays narrow and bounded, the decision logic stays transparent and testable, safety-critical escalation can't be silently skipped, and the whole system is judged against explicit, named success and failure criteria rather than how convincing the demo looks.

## 7. Next steps

- Run the same 20 cases through the real AI-extraction path and compare results directly against the keyword-based baseline above.
- Expand to 50-100 synthetic cases with deliberately engineered coverage gaps.
- Validate the time thresholds against real (properly governed, anonymized) patient timing data before treating them as final.
- Add a second independent clinical reviewer to the expected-outcome labels, and measure agreement between reviewers.
