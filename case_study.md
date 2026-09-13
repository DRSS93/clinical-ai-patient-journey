# Case Study: Designing Safer LLM-Based Clinical Workflow Decision Support

## The question

**How should an LLM be used inside a safety-critical clinical workflow — and how do you evaluate whether it's being used safely?**

This is not a project about whether AI can help dental implant patients specifically. The dental implant patient journey is the concrete test case used to explore a more general question about safe AI system design in healthcare: keep the LLM's role narrow (interpreting unstructured language) and keep every consequential decision in transparent, testable, human-auditable logic — then evaluate the system specifically on whether it knows when *not* to proceed, not just whether its recommendations look reasonable.

## Summary

This project explores how an AI language model can be safely integrated into a healthcare workflow — not as a decision-maker, but as an interpreter of unstructured clinical notes, feeding into a transparent, rule-based system that a human clinician ultimately reviews. It was built as a small working prototype, evaluated against a deliberately constructed set of adversarial test cases, and documented with the same rigor as the underlying clinical/data reasoning it draws from.

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

**Method:** 26 synthetic (entirely made-up, no real patient data) case notes were written to deliberately cover:
- Straightforward cases
- Ambiguous cases (a genuinely unclear fact)
- Incomplete cases (missing information)
- Contradictory cases (conflicting statements)
- Edge cases (fast-track same-day treatment, external referrals, self-pay patients, incomplete history)
- **Misleading notes** (a genuine symptom stated in reassuring, minimizing language — e.g., "probably nothing")
- **LLM extraction error tests** (clinical abbreviations, non-English input — designed to test the limits of the extraction layer specifically)
- **Borderline threshold cases** (exactly at a day-count cutoff)
- Escalation-required cases (symptoms suggesting a possible complication)

Each case has a hand-written "expected outcome" — what a human reviewer would want the system to conclude. The system's actual output is then compared against that expectation.

**The central evaluation question:** not "is the pathway recommendation correct," but **"does the system know when it should not proceed?"** — a system that is occasionally wrong about a routine case is a usability problem; a system that is confidently wrong about a risky case is a safety problem. The evaluation is designed to separate these two failure types explicitly.

**What's measured**, beyond simple right/wrong:
- **False non-escalation** — a real symptom or contradiction present, but the system did not flag it. This is the single most important number in the entire evaluation.
- **False escalation** — the system escalated something that didn't need it. Costly (adds clinician workload) but not unsafe.
- **Extraction-layer failure rate** — errors specifically attributable to the text-interpretation step (abbreviations, language), isolated from the decision-rules layer.
- **Appropriate caution** — did unclear cases correctly resolve to "needs more information" rather than a guess?

**Result (rule-based fallback extractor, no AI model called — zero cost):**

| Metric | Result |
|---|---|
| Exact pathway match | 15/26 (58%) |
| Escalation-required cases correctly escalated | 7/7 (100%) |
| **False non-escalations** | **0** |
| False escalations | 1 |
| Extraction-error test cases failed | 2/2 |

Zero false non-escalations, including on the two "misleading note" cases specifically designed to bury a real symptom inside reassuring language — the system escalated correctly even when the overall tone of the note sounded fine. The two extraction-error failures are a specific, isolated, and expected finding: the simple keyword extractor cannot expand clinical abbreviations or handle non-English text. That is a property of the extraction method used for this test run, not of the decision-rules engine — and is precisely the gap a real LLM-based extraction pass is designed to close.

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

## 7. Next steps for this prototype

- Run the same 26 cases through the real AI-extraction path and compare results directly against the keyword-based baseline above.
- Expand to 50-100 synthetic cases with deliberately engineered coverage gaps.
- Validate the time thresholds against real (properly governed, anonymized) patient timing data before treating them as final.
- Add a second independent clinical reviewer to the expected-outcome labels, and measure agreement between reviewers.

## 8. What would be required before any real-world use

This prototype is several steps removed from anything usable on real patients. A credible path forward would require: a larger, properly consented clinical dataset; multi-clinician adjudication of expected outcomes (not one person's judgment); prospective validation on new cases rather than retrospective synthetic ones; formal adversarial safety testing well beyond 26 cases; ongoing model/version monitoring; privacy and security controls appropriate to real patient data; a genuine, workflow-integrated human override mechanism; a regulatory classification and approval assessment; and continued monitoring for failure modes no synthetic test set can fully anticipate. Naming this gap explicitly is itself part of the point of the project — a credible healthcare AI prototype should be as clear about what it hasn't yet proven as about what it has.
