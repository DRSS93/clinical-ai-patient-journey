# Methodology

## 1. Problem framing

In a real-world implant clinic, a patient's journey (extraction → consult → placement → restoration, or extraction → denture → overdenture) is tracked across many separate billing/clinical events over months or years. Two practical problems arise when trying to support staff in managing this:

1. **Unstructured notes.** Not everything is captured in clean structured fields — free-text notes often carry the actual status of a patient's journey.
2. **Recency ambiguity.** A patient who "hasn't converted yet" and a patient who "has genuinely dropped out of the funnel" look identical in a simple snapshot unless you account for how much time has realistically passed since their last event.

This prototype addresses both: an LLM (or rule-based fallback) handles the unstructured-text problem; a deterministic rules engine handles the recency-ambiguity problem.

**A note on why this is note-based rather than structured-data-based.** In practice, much of a patient's implant journey is already captured in structured Practice Management System (PMS) billing codes and dates — for example, in the Netherlands, codes such as J010 (implant consult), J040/J041 (implant placement), J057 (implant material cost), P020-P022 (conventional dentures), and J080-J082 (implant-retained overdentures), each with an associated date of service. A prior analysis using exactly this kind of structured, code-and-date data (aggregated and anonymized, at the clinic level) was used to derive the recency thresholds referenced in Section 3 below.

Where structured codes and dates are available, no AI is needed at all — a database query or spreadsheet formula can apply the same threshold logic directly. This prototype deliberately targets the *unstructured* layer instead — free-text notes, referral letters, patient messages — because that is where an LLM provides genuine, non-redundant value: turning messy, human-written information into the same clean fields the deterministic rules engine already knows how to act on. Building an AI system around data that's already structured would not demonstrate anything an AI is actually needed for.

## 2. Why separate the LLM from the decision

The LLM in this system is restricted to **field extraction only** — converting a free-text note into structured yes/no/date fields. It is explicitly instructed not to recommend a pathway or diagnose.

This separation matters for two reasons:
- **Auditability.** The actual routing decision is plain, readable Python logic that can be inspected, tested, and explained line by line — not a black-box model output.
- **Containment, not elimination, of extraction errors.** Separating extraction from routing helps contain and identify errors, but an extraction failure could still affect downstream routing — for example, if the extractor fails to detect a symptom or contradiction in the first place, the rules engine has no way to know it was missed. This is why the extraction layer requires its own independent evaluation (see Section 4), and why all outputs remain subject to human review regardless of the system's confidence label.

## 3. Threshold design (recency logic)

The deterministic rules use time-based thresholds to distinguish "hasn't had time to convert yet" from "did not convert." These were derived from reasoning about realistic clinical/administrative timelines, then intentionally kept conservative:

| Transition | Threshold | Rationale |
|---|---|---|
| Extraction → Implant (single-tooth) | 90 days | Approximate minimum healing window before placement is clinically feasible |
| Extraction → Implant (denture/full-arch track) | 360 days | Longer, staged treatment plan; still measures the surgical milestone, not the restorative one |
| Consult → Implant (cost) | 90 days | Booking/scheduling lag only |
| Denture → Overdenture (restoration) | 450 days | Reimbursement documentation + healing + restorative fitting — the slowest step in the journey |

These thresholds are **provisional working estimates**, not empirically fitted values. A production version of this system would validate them against the actual distribution of real conversion lag times (i.e., for patients who did convert, what was the actual days-elapsed distribution?) before treating them as fixed. This is a known limitation, documented here rather than hidden.

## 4. Evaluation framework

### 4.1 Synthetic dataset

26 synthetic cases (`data/synthetic_cases.csv`) were hand-written to cover:
- **Straightforward** cases (clear single path, no ambiguity)
- **Ambiguous** cases (note is genuinely unclear about a key fact)
- **Incomplete** cases (missing data needed to route confidently)
- **Contradictory** cases (conflicting statements in the same or related notes)
- **Edge cases** (left-censored history, fast-track same-day placement, external referral, self-pay entry)
- **Misleading notes** (a real symptom stated in reassuring/minimizing language)
- **LLM extraction error tests** (clinical abbreviations, non-English text — designed to stress-test the extraction layer specifically, independent of the decision rules)
- **Borderline threshold cases** (exactly at a day-count cutoff, to check boundary behavior)
- **Escalation-required** cases (symptoms suggestive of infection, implant failure, or nerve injury)

No real patient data is used anywhere in this dataset.

### 4.2 What is measured

For each case, the system's `recommended_pathway` and `escalate_to_clinician` flag are compared against a hand-written `expected_pathway` / `expected_escalation`. This produces a simple match/review outcome per case (see `evaluation/evaluation_results.csv`).

Beyond raw accuracy, the categories above allow measuring specific failure modes separately:
- **Escalation sensitivity**: did every symptom-flagged case correctly escalate? (This is the single most safety-critical metric — a missed escalation is worse than any other error type.)
- **False reassurance**: did any case produce a confident, non-escalated recommendation when the underlying situation was actually ambiguous or risky?
- **Appropriate caution**: did ambiguous/incomplete cases correctly resolve to "insufficient information" rather than a confident guess?
- **Consistency**: do structurally similar cases (e.g., two different denture-track patients past the same threshold) receive the same pathway?

### 4.3 Observed result (rule-based fallback extractor)

Running the default (no-API-key) rule-based extractor against all 26 synthetic cases: 15/26 exact pathway matches (58%), and — the metric that matters most — **7/7 escalation-required cases correctly triggered escalation, with zero false non-escalations.** This held even for the two "misleading note" cases specifically designed to bury a real symptom inside reassuring language, confirming the escalation check is correctly keyed to the presence of a symptom rather than the tone of the surrounding text.

The two "LLM extraction error test" cases (clinical abbreviations and non-English text) both failed under the simple keyword extractor — an expected, deliberately-surfaced finding, since this extractor was never designed to expand abbreviations or translate text. This is a genuine limitation of the simple keyword-based fallback extractor specifically, not the rules engine, and is exactly the kind of gap a real LLM extraction pass (`USE_LLM=true`) is expected to close. This distinction — rules-engine correctness vs. extraction-layer limitations — is itself a useful evaluation finding, and is the reason the two layers are architecturally separated: an extraction failure degrades to "insufficient information," never to an unsafe confident answer.

## 5. What would come next in a real build

- Replace/supplement the rule-based fallback with systematic LLM-extraction evaluation (run with `USE_LLM=true`, compare against the same expected pathways)
- Expand the synthetic dataset to 50-100 cases with deliberate coverage gaps filled in
- Add inter-rater comparison (have a second clinician independently label expected pathways, measure agreement)
- Validate thresholds against real (properly anonymized, governed) lag-time data before treating them as final
- **Build a hybrid version**: use structured PMS codes and dates directly wherever they exist (no AI needed), and reserve the LLM extraction layer only for filling gaps from unstructured notes — reducing AI usage, cost, and risk to exactly where it is actually needed, rather than applying it uniformly to every case

## Note on billing code system

The specific billing codes referenced in this document (J010, J040, J041, J049, J057, P020-P022, J080-J082, H11, H16, H35, R34) follow the Dutch (Netherlands) NZa dental billing code system. This prototype's logic is not tied to this specific code system — the underlying pattern (an event code plus a date of service, per treatment stage) generalizes to other countries' dental/medical billing systems (e.g., CDT codes in the US), with the code list swapped accordingly.
