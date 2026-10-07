# Interview Templates

What each template focuses on. Read only the one in use.

## grill_product

The Requester is a PM. Grill from the product side: who the user is, the concrete scenario, the value, what is in and out of scope, and testable acceptance criteria. Use the glossary, ADRs and specs to catch fuzzy or conflicting terms and contradictions with documented decisions. Keep to product decisions; implementation belongs to RD.

## grill_technical

The Requester is an FAE who knows the repo and the Observ architecture. Grill like grill_product, and also go into how the middleware works: which flow, gate, router or job is affected, what the current behaviour actually is, and the edge cases the glossary and ADRs reveal. Treat the Requester's claims about current behaviour as Premises to check against the Knowledge Source before relying on them.

## quick_bug

A bug report from a PM. Be quick: one-line summary, environment, reproduction steps, expected vs actual result, impact (who / how many / how often). At most two rounds unless something essential is missing.

## quick_bug_technical

A bug report from someone technical. Collect summary, environment (Deployment Environment, version, camera / task / vendor ids), reproduction steps, expected vs actual, logs, impact, and the suspected module. Use the glossary to sharpen questions (「是在 Ensemble Gate 之前還是之後失敗？」).

## clarify

The Requester (usually RD) already wrote their current understanding and the questions they want someone else (usually a PM) to answer. First round:

1. Split the input into **Premises** (statements about how things are now) and questions.
2. Check every Premise against the Knowledge Source; under each, note the supporting glossary entry or ADR, or the contradiction you found.
3. Add the questions the Requester missed, and rewrite each so the intended Respondent can answer it, offering options where natural. Leave out recommendations: these questions will be handed off.
4. Show the result to the Requester to edit, then produce the Handoff message.

Later rounds ask follow-ups only as extensions of the answers that came back.
