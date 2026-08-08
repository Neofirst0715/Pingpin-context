# 🤖 Pingpin — Etsy Multi-Agent Listing System

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![LangGraph](https://img.shields.io/badge/LangGraph-Agent%20Orchestration-purple)
![DashScope](https://img.shields.io/badge/DashScope-Qwen--Plus-orange)
![FastAPI](https://img.shields.io/badge/FastAPI-Deployed-teal)
![License](https://img.shields.io/badge/License-MIT-yellow)

A multi-agent pipeline for generating Etsy listing copy, built as **Condition C** of a controlled experiment testing whether AI assistance improves listing performance for non-native-English Etsy sellers.

> **Status: end-to-end working and verified live, with two human-in-the-loop checkpoints.** A product concept is compliance-screened, market signals are extracted, copy is drafted, audited (with its own retry loop), and shown to a human for final approval before it's considered shipped; rejection at that final step routes back to drafting with the human's specific feedback. The full two-checkpoint flow (`POST /generate` → interrupt → `POST /resume` → interrupt → `POST /resume` → complete) has been exercised end-to-end against the live deployment on Alibaba Cloud ECS, not just locally — see the API section below. As of 2026-07-06, human-sourced corrections that fail the hard gate are routed straight back for another human review instead of being silently discarded into an automatic AI regeneration — see Known Issues for the fix history. The pipeline runs on Alibaba DashScope cloud Qwen (`qwen-plus`).

## Background

Most Etsy copywriting tools assume the seller already understands the platform's rules around what counts as "handmade," "designed by," or "curated" — and assume English fluency. Non-native-English sellers sourcing finished goods (e.g. from wholesale markets) often don't know these distinctions exist until a listing gets flagged.

This project treats that as the first problem to solve, not an edge case: before any copy gets generated, the system checks whether the *selling concept itself* is compliant with Etsy's seller policies — based on Etsy's actual published Creativity Standards, not assumptions.

## Experiment context

This pipeline is one of three conditions in a live A/B/C test run on a real Etsy shop:

| Condition | Approach |
|---|---|
| A | Fully human-written copy (baseline) |
| B | Batch generation, fixed prompt template |
| C | **This repo** — stateful LangGraph multi-agent system with compliance pre-screening, market-signal synthesis, and a hybrid (rule-based + LLM) critic loop |

Primary metric: favorites rate, compared across conditions with significance testing (scipy.stats).

## Architecture

> This diagram reflects the current implementation, including the compliance-reject branch, the hard-gate/soft-score audit loop, the human correction checkpoint, and Agent 5's final delivery approval step — verified end-to-end on the live deployment as of 2026-07-06.

Five-agent pipeline, diagrammed before any code was written.

![Five-agent pipeline: compliance gate, SEO extraction, drafting, two-layer audit with human correction, and final delivery approval](Architecture-diagram)

| Agent | Role | Status |
|---|---|---|
| **Agent 1** | Etsy compliance pre-screening — RAG sub-graph (`call_model ⇄ tool_node` loop) + structured `ComplianceVerdict` | ✅ Implemented |
| **Agent 2** | Quality gate + structured SEO signal extraction from manually-pasted competitor listings (sanitize noise → extract deduplicated keywords / selling points via a Pydantic contract). Manual paste, not scraped — Etsy's ToS prohibits automated collection for AI use. | ✅ Implemented |
| **Agent 3** | Drafting agent — fuses A2 market signals + user's stated product concept + tone into a title/description, with a feedback-aware retry loop driven by A4's audit results | ✅ Implemented |
| **Agent 4** | Two-layer critic — Python hard-gate (pass/fail) before LLM soft-scoring (0–20) on tone, selling points, naturalness, differentiation | ✅ Implemented |
| **Agent 5** | Deliver & archive — format, log to CSV (with prompt versions), then hold for a final human approval before ending | ✅ Implemented |

## Agent 1 — Compliance Pre-Screening

Etsy requires every listing to be filed under one of four categories (Made by a Seller / Designed by a Seller / Sourced by a Seller / Curated set of purchased goods), each with different requirements. Agent 1 checks a seller's product concept against this before any copy is generated.

**Pipeline:**
1. Loads Etsy seller policy documents (PDF) from a local policy folder
2. Tags each chunk with a category (`Seller_Standards`, `Production_Partners`, `Shop_Policies`, `General_Help`) based on source filename
3. Splits and embeds into a Chroma vector store (`text-embedding-v3` via DashScope)
4. Exposes a `retriever_tool` that the agent calls to ground its compliance judgment in retrieved policy text — rather than guessing from the model's own (often outdated or hallucinated) sense of platform rules

**Design choice — why retrieval is split from judgment:** the retriever's only job is to report what it found (or honestly report that it found nothing). The compliance verdict is not decided by free-text LLM judgment alone; after the retrieval loop, a `with_structured_output(ComplianceVerdict)` step forces a typed `{is_compliant: bool, reason: str}` output, so the verdict is auditable rather than a vague paragraph.

**Implementation — function calling / tool-use, not a single chat completion:** A1 is not a single unstructured prompt-in, text-out call — it implements genuine tool-use. `retriever_tool` is exposed to the model as a callable tool via `llm.bind_tools(tools)`; `tools_condition` is the LangGraph routing primitive that lets the model decide, per turn, whether it needs to call the tool or is ready to finalize a verdict. This runs as its own compiled sub-graph — a `call_model ⇄ tool_node` loop — invoked from the main graph's `compliance_check` node, rather than inline prompt-stuffing: the model can iteratively request more grounding before committing to a compliance decision, and that decision is a real branching point in the graph, not a hardcoded step. Tool invocation is verified at runtime, not assumed: a known failure mode of local/smaller models is *narrating* a tool call in free text while `tool_calls` comes back empty, so a diagnostic print inside `retriever_tool` confirms the tool was actually invoked.

## Agent 2 — Quality Gate + SEO Signal Extraction

Users paste competitor listing text that is often noisy — marketing fluff, social links, malformed or poorly structured fragments. Passing that raw text to Agent 3 would degrade the generated copy ("garbage in, garbage out"). Agent 2's job is to **sanitize first, then extract**, so only clean, structured signals reach the generation stage.

**Design choice — structured output over manual `if`-gates:** rather than hard-coding rules to strip specific words (unmaintainable, and prone to over-stripping high-value modifiers like "Personalized"), the agent uses an LLM constrained by a Pydantic contract (`CompetitorSignal`) to do semantic categorization:

- `is_valid: bool` — quality gate; noise / no product attributes → `False`
- `keywords: List[str]` — deduplicated
- `selling_points: List[str]` — material, size, use-case
- `reasoning: str` — audit trail for why the input passed or failed

**Design choice — no vector store for Agent 2:** competitor input is a single short pasted listing, not a corpus to search, so it goes straight into the LLM's context window. ChromaDB is reserved for Agent 1's retrieval use case (hundreds of policy pages).

**Current limitation:** there is no file-import mechanism yet. "own data" in A2 currently just refers to the user's typed product concept (user_ideas), not ingested historical shop data, and competitor input is manual-paste text only. The data-priority design (own data as ground truth over competitor signals) is the intended direction once real historical data ingestion exists — tracked as LocalDataSourceManager in the backlog.

## Agent 3 — Drafting Agent (with feedback loop)

Agent 3 is where every upstream signal converges into an actual title + description. It reads A2's cleaned keywords/selling points, the user's stated product concept (user_ideas), the tone preference, and the Etsy constraints, then synthesizes the copy. (Note: "own sales data" as a distinct historical-data input doesn't exist yet — see Agent 2's Current Limitation note above.)
**Design choice — one base prompt + conditional append, not two prompts.** The standard the copy must meet is *identical* on the first pass and on a retry — what changes is the material on hand, not the strictness. So `construct_draft_prompt` maintains one base prompt (rules + tone + signals, written once) and, only when `retry_count >= 1`, appends a feedback block: the previous draft plus A4's `system_feedback`, with an instruction to revise the flagged parts. Single source of truth for the Etsy-rules block.

**Design choice — state is the memory, so A1/A2 never re-run.** When A4 rejects a draft and routes back to A3, A3 re-reads `keyword_list` / `selling_point` / etc. straight from shared state. The retry edge is `A4 → A3`, not `A4 → A1`, so a revision costs one A3 call, not a full pipeline re-execution.

**Design choice — structured output + regex split.** A Pydantic `BaseModel` plus `re` cleanly separates the title and description, and XML-tagged prompt structure guides the model toward parseable output.

**Tone handling:** if the user supplied a `tone_preference`, it's folded into the prompt; if blank, the model self-determines a market-appropriate tone. The branch is decided in Python, not by the model.

## Agent 4 — Two-Layer Audit (hard gate + soft scoring)

Agent 4 decides whether A3's draft ships or gets sent back to revise. It runs in two layers, cheapest and most reliable first.

**Layer 1 — hard gate (pure Python, pass/fail, no LLM).** `check_hard_rules()` checks the objective things: description word count (100–150), a banned-word blacklist match, and presence of at least one use-case signal. Any failure rejects the draft immediately — it never reaches the LLM.

**Layer 2 — soft scoring (LLM, only after the hard gate passes).** An `AuditResult` Pydantic contract carries the subjective dimensions — `tone_match`, `selling_points`, `naturalness`, `differentiation` (each 0–5) and `feedback_points`.

**Design choice — the score is computed in Python, not trusted from the model.** The final score is the **sum of the four sub-scores**, computed in Python. (The model's self-reported total was found to be unreliable — it would report a total that didn't match its own sub-scores, e.g. sub-scores summing to 18 while the model reported 4, falsely rejecting good copy.) Whether that summed score clears the threshold is also a plain Python `if` — deterministic arithmetic and threshold decisions belong in Python, not the LLM.

**Design choice — rules live in `audit_config.py`, not in the function.** `BANNED_WORDS`, `USE_CASE_SIGNALS`, and the word-count bounds are config constants, separated from logic. The blacklist is kept deliberately narrow — context-dependent words like "best"/"authentic" are left for the LLM layer to judge, to avoid false positives on legitimate copy.

**On reject**, `audit_node` increments `retry_count` and writes the reason into `system_feedback` for A3's next pass. The retry-cap → human-intervention decision lives in the graph router, not inside the node.

**Routing distinguishes agent-authored vs human-authored rejections.** A `last_edit_source` state field (`"agent"` | `"human"`) is set by `listing_draft` and `human_intervention_node` respectively. When a human-supplied correction fails the hard gate, the router checks this field first and sends it straight back to `human_intervention` — regardless of remaining retry budget — instead of silently discarding it into A3's automatic regeneration loop.

## Product-Category Truth Source (cross-cutting fix, A1 + A2 + state)

**The bug:** the agent would sometimes take a standalone electronic device (e.g. a MacBook) and, pulled by popularity-weighted Etsy search terms, generate copy as if the product were an *accessory for* that device — a sleeve or case — rather than the device itself. This isn't a cosmetic error; mis-classifying a restricted electronics listing as an accessory is exactly the kind of category slip Agent 1 exists to prevent.

**Root cause:** there was no single field acting as ground truth for "what this product actually is." Category was being inferred fresh (and inconsistently) at different points in the pipeline, so nothing forced later steps to agree with the user's original stated intent.

**Fix — `category` promoted to a first-class, shared state field.** `PingPinGoState` now carries `category: str`, decided once and read everywhere downstream instead of re-guessed per agent.

**A2 — "PRODUCT TYPE LOCK".** The `seo_extraction_node` prompt now explicitly instructs the model: if the input describes a standalone hardware device, the category **must** be Electronics/Hardware — it must not hallucinate the product into an accessory/case/sleeve just because those terms trend on Etsy. The user's own stated product info is the source of truth, not popularity-driven association.

**A1 — compliance tied to category accuracy, not just policy text.** `ComplianceVerdict` gained `product_type_accuracy: bool`; `compliance_node` checks the assigned `category` for logical consistency against the user's original idea. The final `system_feedback` is a **joint condition** — `is_compliant AND product_type_accuracy` — so a listing that passes policy text search but was mis-categorized still fails, and the failure message states which check it failed.

## Agent 5 — Deliver, Archive, and Final Human Approval

Agent 5 has two parts: `final_delivery_node` (format + archive + log) and, new as of 2026-07-04, `human_delivery_approval_node` — a second human-in-the-loop checkpoint that sits between "passed A4's audit" and "actually shipped."

**Why a second checkpoint, on top of A4's audit:** A4 measures the copy against rules and a rubric; it doesn't capture "does the seller actually like this." Passing automated audit and being acceptable to the human aren't guaranteed to be the same thing, so the final say is deliberately left to a person rather than inferred from A4's score alone.

**`final_delivery_node`:** unchanged in spirit from the original design — a pure formatting + archiving step. No content is changed here (the copy was finalized by A4); it reads `is_compliance`, `keyword_list`, `audit_result`, etc. straight from shared state (no importing other agents) and appends one row to `logs/listing_archive.csv` (header auto-written on first run via `DictWriter`). Fields include the final copy, SKU id, compliance flag, keywords/selling points, audit scores, `retry_count`, timestamp, and **prompt versions** (`a2_prompt_version` / `a3_prompt_version` / `a4_prompt_version`) — the reproducibility anchor, so any archived listing can be traced to the exact prompt versions that produced and scored it.

**`human_delivery_approval_node`:** surfaces the final title/description via `interrupt({"preview": {...}})` and pauses the graph. A human reviews it and responds either "approved" or with specific feedback on what's wrong. On approval, the graph ends. **On rejection, it is not a dead end** — the graph routes back to `listing_draft` (A3) with the human's actual complaint written into `system_feedback`, so the revision is targeted, not a blind retry with no new information.

**Design note — this reopens (in a controlled way) something earlier design notes deliberately closed off.** An open-ended "human polish → back to A3" loop was previously rejected as a risk to Condition C's reproducibility (an unstandardized human variable polluting the causal comparison between conditions). The distinction here: this checkpoint is a **fixed, single approval gate** at a known point in the pipeline — not an unbounded editing loop — so every archived listing still went through the same fixed sequence of checkpoints; what varies is only whether a given SKU needed a revision pass, which itself is a loggable, analyzable fact about that SKU rather than an untracked source of variation.

## Graph wiring (`main.py`)

All five agents are compiled into one LangGraph workflow, with two human-in-the-loop pause points:

- **Entry:** `compliance_check` (A1 sub-graph)
- `compliance_check` → conditional edge on `is_compliance` (`True` → `seo_extraction`; `False` → `END`)
- `seo_extraction` → `listing_draft`
- `listing_draft` → `audit`
- `audit` → conditional edge: `Passed` → `delivery`; `retry_count < 2` → back to `listing_draft` (revise); else → `human_intervention`
- `human_intervention` → `audit` (re-checks after a human-supplied correction)
- `delivery` → `final_delivery_approval`
- `final_delivery_approval` → conditional edge: `approved` → `END`; anything else → back to `listing_draft` (revise, carrying the human's specific feedback)

**Human-in-the-loop mechanics:** both `human_intervention` (A4) and `human_delivery_approval_node` (A5) pause execution via the global `interrupt()` function (not a `Command(...)` constructor call — that pattern conflicted with the current `langgraph` version). A `MemorySaver` checkpointer, keyed by SKU (`thread_id`), lets the graph actually suspend at an interrupt and later resume via `Command(resume=...)`. `main.py`'s driver loop is a single generic `while` loop over `state_snapshot.tasks`: it inspects the shape of the pending interrupt's payload (a `"preview"` key means the final-delivery approval; anything else means an audit rejection) and routes to the right human-input flow — one control loop handling two distinct kinds of checkpoints, instead of duplicating resume logic per interrupt type.

## API server (`agents/api.py`)

The compiled graph from `main.py` is wrapped in a FastAPI app so it can be driven over HTTP, including both human-in-the-loop pause points — not just invoked once as a script. This is what's running on the Alibaba Cloud ECS deployment, verified end-to-end on 2026-07-05.

- **`GET /`** — health check. Returns `{"status": "running", "service": "Pingpin Agent", "deployed_on": "Alibaba Cloud ECS"}`.
- **`POST /generate`** — body: `{"sku": str, "user_ideas": str, "competitor_data": str, "tone_preference": str, "product_category": str}`. `sku` is required and doubles as the LangGraph `thread_id`, so a later `/resume` call knows which run it belongs to. Starts (or restarts) a run. If the thread already has a pending interrupt, returns **409** telling the caller to call `/resume` instead — prevents accidentally kicking off a duplicate run mid-review.
- **`POST /resume`** — body: `{"thread_id": str, "resume_payload": dict}`. Feeds a human decision back into a paused graph and continues from where it stopped. Returns **409** if that thread has no pending interrupt to resume. The shape of `resume_payload` depends on which checkpoint is paused (see below).

**Both endpoints return one of two response shapes:**
- `{"status": "interrupted", "thread_id": ..., "data": {...}}` — the graph paused at a human checkpoint; `data` is the raw interrupt payload the caller needs to act on.
- `{"status": "complete", "thread_id": ..., "result": {...}}` — the graph reached `END`; `result` has the final `final_title`, `final_description`, `audit_result`, `is_compliance`, `system_feedback`.

**The two checkpoints produce different `data` shapes**, which the caller distinguishes by which keys are present:
- **A4 human correction** (`human_intervention_node`): `{"reason": str, "current_title": str, "current_description": str}`. Resume with `{"final_title": str, "final_description": str}`.
- **A5 final approval** (`human_delivery_approval_node`): `{"preview": {"title": str, "description": str}}`. Resume with either `{"final_approval": "approved"}` or `{"final_approval": "revise", "system_feedback": "<reason>"}` (revise routes back to `listing_draft`).

**Verified live on 2026-07-05** with a real end-to-end run (`sku: TEST-001`): a first draft rejected by the hard gate (over word count) auto-retried once, then paused for human correction; a correction that itself failed the hard gate (accidentally too short) fell through to another automatic A3 regeneration rather than immediately re-prompting the human — a routing gap identified during this test and fixed the following day (see Known Issues); a corrected, properly-sized draft passed the hard gate and soft scoring (17/20), reached the final delivery approval pause, and completing with `{"final_approval": "approved"}` returned `"status": "complete"` with the full result payload.

## Tech stack

- LangGraph / LangChain — agent orchestration
- **DashScope cloud Qwen** (`qwen-plus` via the OpenAI-compatible endpoint) — inference; `text-embedding-v3` — embeddings
- LangGraph `MemorySaver` checkpointer + `interrupt()` — pause/resume for the two human-in-the-loop checkpoints (A4 correction, A5 final approval)
- FastAPI / Uvicorn — HTTP layer over the compiled graph
- Pydantic — structured-output contracts for agent I/O
- ChromaDB — vector store (Agent 1 only)
- Python (`re` for parsing, `csv` for archiving)

> The pipeline was originally built on local Ollama (`qwen2.5:7b` + `nomic-embed-text`) for zero-cost reproducible development, then migrated to DashScope cloud Qwen on 2026-07-02 for higher output quality and for the Qwen Hackathon deployment. The code still follows the same structure; only the client and embeddings changed.

## Setup

**Deployment:** Live on Alibaba Cloud ECS (US Virginia) — `http://47.85.88.45`

```bash
pip install -r requirements.txt
```

Set your DashScope API key in `agents/.env` (git-ignored). Note: if you use an **international** DashScope account, the `dashscope` SDK defaults to the domestic China endpoint and will 401 on embeddings — point it at the intl endpoint explicitly with `dashscope.base_http_api_url = "https://dashscope-intl.aliyuncs.com/api/v1"`.

Agent 1 expects Etsy policy PDFs in a local folder referenced by `folder_path` in `agents/a1_compliance_agent.py` (currently a hardcoded absolute path — make it relative before running elsewhere).

### Running the pipeline directly

```bash
cd agents
python main.py
```

Runs the graph once against the hardcoded `initial_state` sample in `main.py` and prints the final state.

### Running the API server

For a quick foreground test:

```bash
cd agents
uvicorn api:api --host 0.0.0.0 --port 80
```

For the actual deployment (survives closing the SSH session):

```bash
cd agents
nohup uvicorn api:api --host 0.0.0.0 --port 80 > app.log 2>&1 &
```

Then:

```bash
curl http://localhost/

curl -X POST http://localhost/generate \
  -H "Content-Type: application/json" \
  -d '{"sku": "SKU-001", "user_ideas": "A cute enamel pin of a sleeping cat, designed for daily wear.", "competitor_data": "High quality cat pin, fast shipping, perfect gift.", "tone_preference": "", "product_category": ""}'

# If the response is {"status": "interrupted", ...}, act on data.reason / data.current_title / data.current_description
# (A4 correction) or data.preview (A5 final approval), then:
curl -X POST http://localhost/resume \
  -H "Content-Type: application/json" \
  -d '{"thread_id": "SKU-001", "resume_payload": {"final_approval": "approved"}}'
```

## Known issues / next steps

**Routing — fixed 07-06, verified live on ECS**
- [x] ~~A human-sourced correction that fails the hard gate silently falls into A3's automatic retry loop instead of immediately re-prompting the human.~~ **Fixed:** added `last_edit_source: "agent" | "human"` to state, set by `listing_draft` and `human_intervention_node` respectively; `should_continue_after_audit` now checks `last_edit_source == "human"` before the `retry_count < 2` check, so human-sourced rejections route straight back to `human_intervention` regardless of remaining retry budget. Verified live: a deliberately-invalid human correction was echoed back unchanged (with the correct failure reason) instead of being discarded into a fresh A3 regeneration. **Deployment note:** the first two verification attempts still showed the old behavior even though the fix was confirmed present in the server's code (`git log` + `grep`) — the running `uvicorn` process simply hadn't been restarted, so it was still executing the pre-fix code from memory. Killing the stale process and relaunching resolved it. Lesson: a successful `git pull` on the server is not evidence a fix is live; the process must be restarted, and since the checkpointer (`MemorySaver`) is in-memory-only, any in-flight `thread_id` from before the restart is lost and testing must resume with a fresh `sku`.

**Deployment / ops**
- [ ] API server currently runs as a bare `nohup` background process — move to a `systemd` service so it survives an ECS reboot
- [ ] Clean up `requirements.txt`: it's a straight `pip freeze` export with exact (`==`) pins on everything, including base libraries like `numpy` and `onnxruntime` — these should use range constraints (`>=`) so installs don't fail on mirrors that lag the latest PyPI releases (hit this exact issue deploying on Aliyun's mirror)

**Performance / hardening**
- [x] ~~Chroma rebuilds the vector store on every run~~ **Fixed:** now checks whether the persisted store directory already has content and loads it directly if so, only rebuilding from PDFs when no existing store is found
- [x] ~~`folder_path` / `persist_directory` are hardcoded absolute paths~~ **Fixed:** both now use relative paths (`"Etsy_Policy"`, `"Etsy_Policy/persist_directory"`)
- [ ] Move `SOFT_THRESHOLD` into `audit_config.py` with the other rule constants
- [ ] Add keyword-coverage check to `check_hard_rules()` as a threshold (e.g. ≥80%), not all-or-nothing
- [ ] Add attribute-consistency check (draft vs SKU data) to the hard gate

**Product / data**
- [ ] Build `LocalDataSourceManager` — scan a local file directory to import competitor/product data, replacing the current manual-paste input for A2
- [ ] A3's prompt should treat `tone_preference` (e.g. "funny", "very cool") as a top-priority instruction — currently it's one fused signal among several and can get diluted
- [ ] Further CSV log schema refinement — tie each archived row to which HITL checkpoints fired and what feedback was given, for full-chain traceability

## Project context

Part of a larger experiment comparing human-written, pipeline-generated, and agent-generated Etsy listing copy. Full experimental design, pricing/COGS analysis, and compliance research are documented separately as part of the broader portfolio project.
