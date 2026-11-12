# Jev (System One model): where it could fit in the billing review workbench

Research note, 2026-11-11. Question: where could Jev be used in the Finance Engineer Cup II workbench, alongside or instead of LLM agents?

Conventions: **FACT** lines cite a URL or a repo path. **INFERENCE** marks my own reasoning. TypeSafe docs were fetched raw on 2026-11-11 (the `.md` form each docs page serves).

## Bottom line

Jev is TypeSafe AI's hosted decision model. It does not generate text. It answers closed-set questions (Choice, Score, Noul, and since 1.14, Box) about a supplied `state` and returns probabilities. It is not an Annuit product, and it is not a local library.

For this workbench, the one strong fit is a **semantic check on top of the existing word-for-word quote check**. The current check proves that a curated quote exists in the Amendment. Jev could also judge whether the quote's context supports the curated term and value, which is the pattern in TypeSafe's own "Double-checking citations" cookbook. A second, weaker fit is a **calibrated cross-check of each Finding's evidence**, run next to the LLM reviewer.

It does not fit the core work. TypeSafe's own docs say Jev "is not a calculator", is unreliable at date-window comparison ("accrual periods" is their example), and struggles with multi-hop reasoning. Those three things are exactly what expected-billing reconstruction and Error / Valid Explanation / Needs Info classification need.

The data set is also tiny: 30 Order Forms, 2 Amendments, and 10 Billing Messages. Jev's real advantages, roughly 100 ms latency and a price of $0.042 per million input tokens, buy nothing at that scale. Any Jev step would add a second vendor, a second API key, and a non-bit-exact model, so it must stay outside `make run` with committed outputs, exactly like the planned LLM agents.

**Verdict (inference):** Jev is optional. It earns its place only as a single, well-explained verifier with committed answers. Otherwise it costs STACK points ("Tool count ... alone do not earn points").

## 1. What Jev is

| | |
|---|---|
| Vendor | TypeSafe AI, Inc. Launched Sep 15, 2026 by Diogo Almeida, founder ([launch post](https://typesafe.ai/blog/introducing-system-one-models-and-jev)) |
| Name | Named after William Stanley Jevons: "We named Jev after William Stanley Jevons. We expect machine intelligence to follow a similar path to coal" ([launch post](https://typesafe.ai/blog/introducing-system-one-models-and-jev)) |
| "System One" | "The System One name comes from the concept Daniel Kahneman popularized in his book *Thinking, Fast and Slow*. System 1 thinking is fast and intuitive." ([system-one.md](https://docs.typesafe.ai/concepts/system-one.md)). So the user's Kahneman guess is right for the model class; the model name is from Jevons. |
| Shape | "System One models do not write replies, produce code, or generate explanations of their reasoning." It returns typed decisions plus probabilities ([system-one.md](https://docs.typesafe.ai/concepts/system-one.md)) |
| Endpoint | One hosted endpoint, `POST https://api.typesafe.ai/v1/systemone`, Bearer key ([api.md](https://docs.typesafe.ai/api.md)) |

**Confidence: high.** I found no other "Jev" model. A read-only search of `/Users/danielbank/workspace` found no file mentioning Jev, so there is no local Jev project there. Daniel's own prior notes (outside this repo) also identify it as TypeSafe's API.

### Capabilities and limits (current, 2026-11-11)

- **FACT.** Models: `jev-1.14.0` (from Oct 14, 2026) and `jev-1.13.0`. Both cost "$42 / $0.042" per Btok / Mtok of input, and "Output tokens are free". Context is 64k per request and 32k per question. Input is "Text, images" (PNG and JPEG). Box needs 1.14. The `jev-latest` alias currently points to `jev-1.14.0`. Source: [models.md](https://docs.typesafe.ai/models.md). This supersedes September write-ups that list text-only input and 1.13 as the only version.
- **FACT.** "An alias moves when a new release ships, so its answers can change without any change to your code ... send that version's ID instead of the alias" ([models.md](https://docs.typesafe.ai/models.md)).
- **FACT.** Answers are constrained to the options you supply: "never a value outside them". You must add a "none of the above" option yourself ([primitives.md](https://docs.typesafe.ai/primitives.md)).
- **FACT.** No `temperature` or `seed`; the model is "designed to return stable answers across repeated evaluations" ([how-to-build-with-system-one.md](https://docs.typesafe.ai/concepts/how-to-build-with-system-one.md)). It is still not bit-exact: in TypeSafe's own test, "a post's least stable decision changes 4.0% of the time on average ... and never more than 6.7%", compared with LLMs, which had posts flipping more than 10% of the time ([consistency_choice_cookbook.md](https://docs.typesafe.ai/cookbooks/consistency_choice_cookbook.md)).
- **FACT.** Calibration "is measured across groups of predictions; it does not guarantee that an individual answer is correct" ([system-one.md](https://docs.typesafe.ai/concepts/system-one.md)).
- **FACT.** Known failure modes, from the jaggedness page ([model-jaggedness.md](https://docs.typesafe.ai/model-jaggedness.md)):
  - Math: "Jev is not a calculator. We strongly recommend implementing any mathematical logic in code."
  - Dates: "Asking which of two dates comes first, how far apart they are, or whether one falls inside a window is unreliable. It gets worse with mixed formats, relative references and domain boundaries such as quarters, settlement windows, and accrual periods."
  - Indirection: "something that requires multiple hops of reasoning costs accuracy".
  - Literal reading, adversarial content in the state, and Choice option-order bias: "Jev leans toward the option that comes first".
  - Generation: "Jev is not trained to generate text ... extract possible options using regex or a generative model and let Jev pick the correct extraction."
- **FACT.** TypeSafe's own design rule: "Keep control flow, deterministic rules, and side effects in code" and "Avoid agent `while` loops when a software workflow can express the same behavior" ([how-to-build-with-system-one.md](https://docs.typesafe.ai/concepts/how-to-build-with-system-one.md)).

### Access, cost to run, data terms

- **FACT.** You need a key from `console.typesafe.ai/keys`. The SDK is `typesafe-sdk` on PyPI, and the quickstart shows `uv add typesafe-sdk`. The key is read from `TYPESAFE_API_KEY` ([quickstart.md](https://docs.typesafe.ai/introduction/quickstart.md)).
- **FACT.** Rate limits are per organization and shown in the console. A request over the limit returns 429 ([models.md](https://docs.typesafe.ai/models.md)).
- **Not found.** I found no free tier or trial credit on the docs pages I fetched. Treat judge access as "needs their own paid account" until shown otherwise.
- **FACT.** Not trained on customer data. Zero data retention is enterprise-only ([legal.md](https://docs.typesafe.ai/legal.md)). Governed by the Master Customer Agreement, last updated Sep 23, 2026 ([typesafe.ai/legal/mca](https://typesafe.ai/legal/mca)). The challenge data is fictional ("All people and records are fictional", `out/2026-10/extracted/billing_followups.txt`), so data terms are not a blocker here.
- **FACT.** TypeSafe's cookbooks use a committed-cache pattern. Responses are memoized to a JSON file, "True fills CACHE with the published answers, so the run makes no requests", and the client falls back to `api_key=os.environ.get("TYPESAFE_API_KEY", "cache-only")` ([citation_check.md](https://docs.typesafe.ai/cookbooks/citation_check.md)). **INFERENCE:** this is the same "outputs checked and committed" stance the workbench already plans for agents, so a judge can rerun without a key.
- **FACT.** `system-one-adapter` is "A drop-in replacement for `typesafe_sdk`'s `system_one` evaluation API, backed by LLM APIs instead of TypeSafe", with OpenAI, Anthropic, and Gemini extras ([README](https://raw.githubusercontent.com/typesafe-ai/system-one-adapter-python/main/README.md)). **INFERENCE:** questions written for Jev could run on Claude through the adapter, which gives an A/B comparison or a fallback, but not independence from LLMs.

## 2. The workbench, briefly

- **FACT.** The workbench is a deterministic `make run` pipeline: inputs, then Contract Terms, then Billing Messages, then books, then controls, then outputs. Amendment terms are curated in YAML with an exact quote, and "The run stops ... if a curated quote isn't in its PDF" (`README.md`). The check is a whitespace-normalized substring test, `if normalize(ch["quote"]) not in haystack` (`src/workbench/contracts.py:175`).
- **FACT.** Scale for October: 32 contract PDFs, of which 30 are Order Forms and 2 are Amendments (`data/raw/2026-10/contracts/`, `data/curated/2026-10/amendment_terms.yaml`). There are 10 Billing Messages (`out/2026-10/extracted/billing_followups.txt`), 30 Salesforce accounts, 124 Stripe invoices, and 1,925 usage rows (`data/raw/2026-10/*.csv`).
- **FACT.** Customer mapping uses explicit IDs. Salesforce carries `StripeCustomerId__c` and `NetSuiteCustomerInternalId__c` (`data/raw/2026-10/salesforce_accounts.csv`), and the brief says "Don't invent terms or force mappings" (`docs/CHALLENGE.md`).
- **FACT.** Judging weights: ACCT'G INTEL 25, BUILD 25, DATA 20, CONTROLS 15, STACK 15. START_HERE.pdf (intro, page 1) says "AI is welcome, but extracted terms and calculations must be reviewable" (`data/raw/2026-10/START_HERE.pdf`; verified by text extraction). The Notion brief adds "AI-extracted terms, calculations, and proposed actions need supporting evidence."
- **FACT.** The repo already dropped a tool for adding no independence and costing judges an install (`docs/adr/0001-no-ledger-engine.md`). Any Jev step faces the same deletion test.

## 3. Candidate uses

### A. Semantic quote check for Amendment terms (best fit)

**What it would do.** Keep the existing substring check as the hard gate. For each curated change that passes it, ask Jev one Choice over the Amendment's section text: does it **support**, **contradict**, or **say nothing about** the claim "`term` = `value`, effective `effective_from`"? Low confidence or a non-"supports" answer becomes a review flag in the report. This is TypeSafe's citation-check flow almost line for line: a string match first, then "a `Choice` question to read each surviving quote's context and decide whether it supports the claim", with confidence below 0.8 sent to a human ([citation_check.md](https://docs.typesafe.ai/cookbooks/citation_check.md)).

**Fit.**
- **INFERENCE.** It closes a real gap. Today a correct quote paired with a wrong `value` would pass, for example `45000` mistyped as `4500`, or the November-only `platform_invoice_amount` given the wrong `effective_from`.
- **INFERENCE, with a caveat.** Jev reads numbers worse than words ([model-jaggedness.md](https://docs.typesafe.ai/model-jaggedness.md)). Value equality like "45,000" against `45000` is better done in code after normalization. So Jev should judge only the *semantic* part: is this the right term, is it the amended (not the prior) value, and does the scope fit.
- **Effective dates stay in code**, because of the date-window failure mode.
- **INFERENCE.** With 2 Amendments and about 7 curated changes, a reviewer can read them all in minutes. The value here is mostly demonstrating a control that scales to a busier month, not saving effort in October.

**Determinism and reviewability.** Run it outside `make run` (a separate `make verify-terms` step, for example) with a pinned `jev-1.14.0`. Commit the answers (probabilities, confidence, model ID) as a cache or CSV. `make run` then reads the committed file and only displays it. CI stays green with no key.

**Judge rerun cost.** Zero if they only use the committed answers. A live rerun needs a TypeSafe account, a key, and `uv add typesafe-sdk`.

**Against the LLM-agent alternative.** It complements the agent, and the two fit well: the planned Claude agent *drafts* terms (generation, which Jev cannot do), and Jev *verifies* them. That is TypeSafe's own split: "extract possible options using regex or a generative model and let Jev pick" ([model-jaggedness.md](https://docs.typesafe.ai/model-jaggedness.md)), and the SDE cascade's "a cheap model extracts, Jev checks each field" ([sde_cascade.md](https://docs.typesafe.ai/cookbooks/sde_cascade.md)). **INFERENCE:** a second LLM call could do the same check. Jev's advantages are a calibrated number per check and a different model family from the drafter, which makes it a genuine second set of eyes.

### B. Calibrated evidence check on each Finding (complement to the Four-Eye reviewer)

**What it would do.** For each Finding, ask a few atomic Nouls against only that Finding's cited evidence (a Billing Message body, a contract section). Examples: "Does `message` approve a reduction to this customer's October usage consideration?" and "Does `message` state that credit note X was voided?" A low probability against the Finding's classification marks it as a disagreement in the report. This mirrors TypeSafe's "Verifying LLM answers against their source" cookbook, which uses three Nouls per answer and sends the doubtful ones to review ([llms.txt index](https://docs.typesafe.ai/llms.txt)).

**Fit.**
- **INFERENCE.** It works only if each question is atomic and its state is filtered to the cited evidence, per the "large state" and "indirection" failure modes. It must not try to decide Error / Valid Explanation / Needs Info itself, because that verdict combines amounts, dates, policy, and approvals in multiple hops, which Jev's docs warn against.
- **INFERENCE.** The Billing Messages carry exactly the judgment-shaped facts Jev is good at. "Approved: reduce Zephyr Grove October usage consideration by USD 100" and "created in error and voided before the NetSuite import" (`out/2026-10/extracted/billing_followups.txt`) are approval and status questions, not arithmetic. With only 10 messages, though, a deterministic hand-curated mapping from message to Finding (like `amendment_terms.yaml`) is more reviewable and nearly free.

**Against the LLM reviewer.** It complements, not replaces. The Four-Eye LLM reviewer can explain *why* it disagrees, and Jev cannot ("do not ... generate explanations"). Jev adds a number per atomic check and higher self-consistency. **INFERENCE:** if only one reviewer is built, the LLM is the better choice, because a written disagreement is what a Controller can act on.

### C. Classifying Findings as Error / Valid Explanation / Needs Info (poor fit)

A three-option Choice looks natural, but the inputs are expected-vs-actual amounts, effective-date windows, and approvals. Those hit three documented failure modes: math, dates, and indirection ([model-jaggedness.md](https://docs.typesafe.ai/model-jaggedness.md)). It would also put an unexplained model verdict in the place ACCT'G INTEL scores. **Keep it deterministic** (rules in code and SQL, citing evidence). Use B only as a check on that output.

### D. Usage anomaly flagging (does not fit)

Usage validation (duplicates, replaced records, batch controls) is numeric and structural, and the repo already does it in SQL controls. "Asking the model something code can compute exactly" is first on TypeSafe's avoid list ([model-jaggedness.md](https://docs.typesafe.ai/model-jaggedness.md)).

### E. Customer and account mapping suggestions (does not fit)

TypeSafe has an entity-alignment cookbook for fuzzy record matching ([llms.txt index](https://docs.typesafe.ai/llms.txt)). Here the mapping is by explicit system IDs (`salesforce_accounts.csv`), and the brief forbids forcing mappings. A probabilistic matcher adds risk and no information. The right control is a deterministic "every ID resolves" check.

### F. Order Form parsing or OCR (does not fit)

Order Forms are text PDFs parsed by regex against a template, and the run fails on any mismatch (`README.md`). Jev 1.14 can read images and do Box and OCR checks ([models.md](https://docs.typesafe.ai/models.md); [llms.txt index](https://docs.typesafe.ai/llms.txt)), but nothing here is scanned. **INFERENCE:** this only matters if a future month ships scanned contracts.

### G. Triage before a slower agent (does not fit at this scale)

TypeSafe's cascade pays off when most items can skip the expensive model ([sde_cascade.md](https://docs.typesafe.ai/cookbooks/sde_cascade.md)). With about 30 customers and a handful of Findings, the agent can review every item, and a triage layer only adds a step to explain.

## 4. Scoring the trade-off (inference)

| Criterion | Effect of adding Jev (A, optionally B) |
|---|---|
| CONTROLS 15 | Small plus. A visible, numeric "term supported by source" control and visible uncertainty. |
| ACCT'G INTEL 25 | Neutral. The accounting logic must stay deterministic either way. |
| BUILD 25 | Neutral if answers are committed and `make run` never calls out. Minus if a judge needs a key to rerun. |
| DATA 20 | Neutral. Mappings and dates stay deterministic. |
| STACK 15 | Plus only if the README explains *why* a second model (independence plus calibration) and keeps it to one step. Minus if it reads as tool collecting, by the same deletion test that removed rustledger (`docs/adr/0001-no-ledger-engine.md`). |

## 5. Recommendation (inference)

1. If Jev is used at all, use it for **A only**: a pinned `jev-1.14.0` verifier of LLM-drafted or hand-curated Amendment terms, with answers committed, run outside `make run`, and shown in the report as a control column.
2. Treat **B** as optional, behind the LLM Four-Eye reviewer, and only if the Findings' evidence is already split into atomic, per-Finding states.
3. Do not use Jev for classification, arithmetic, effective dates, usage validation, mapping, or triage.
4. Before building, confirm with a few live calls that Jev flags a deliberately wrong `value` and a prior-vs-amended swap. The fit in A rests on that, and TypeSafe's docs show citation checking but not numeric-term checking.

## Sources

TypeSafe (primary, fetched 2026-11-11):
- https://typesafe.ai/blog/introducing-system-one-models-and-jev
- https://docs.typesafe.ai/concepts/system-one.md
- https://docs.typesafe.ai/models.md
- https://docs.typesafe.ai/model-jaggedness.md
- https://docs.typesafe.ai/primitives.md
- https://docs.typesafe.ai/api.md
- https://docs.typesafe.ai/concepts/how-to-build-with-system-one.md
- https://docs.typesafe.ai/introduction/quickstart.md
- https://docs.typesafe.ai/legal.md and https://typesafe.ai/legal/mca
- https://docs.typesafe.ai/cookbooks/citation_check.md
- https://docs.typesafe.ai/cookbooks/sde_cascade.md
- https://docs.typesafe.ai/cookbooks/consistency_choice_cookbook.md
- https://docs.typesafe.ai/llms.txt (cookbook index and one-line summaries)
- https://raw.githubusercontent.com/typesafe-ai/system-one-adapter-python/main/README.md

Repo (main at b93ede8): `README.md`, `docs/CHALLENGE.md`, `GLOSSARY.md`, `docs/adr/0001-no-ledger-engine.md`, `src/workbench/contracts.py`, `src/workbench/messages.py`, `data/curated/2026-10/amendment_terms.yaml`, `data/raw/2026-10/`, `out/2026-10/extracted/billing_followups.txt`.
