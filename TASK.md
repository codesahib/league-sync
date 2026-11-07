# Shared project requirements (applies to all three demos)

## Objective
You are implementing a technical interview case study for a software engineer who joins acquired SaaS companies, learns unfamiliar code, introduces existing AI-assisted engineering workflows, improves engineering productivity and reliability, and leaves maintainable systems behind. This is **not** a request to add a customer-facing chatbot, to build a generic LLM wrapper, or to pretend AI is necessary where deterministic software is better.

Build a self-contained full-stack demo and document **(a) product/process without AI, (b) bottleneck, (c) AI-supported engineering process, (d) improved process/product, (e) measured outcome**.

## Strict scope
- Work inside this repo only. Do not edit sibling repositories or the user's existing portfolio website.
- Use **React + TypeScript + Vite** frontend, **FastAPI + Python** backend, SQLite for local persistence, pytest for backend tests, and Playwright for an essential UI smoke test if feasible. Prefer simple architectures over Docker/microservice overhead.
- Do not require paid APIs, hosted AI services, credentials, or access to Beacon systems. Synthetic data only. No real customer names, emails, payment details, or protected information.
- Use existing AI coding tools (Codex itself) for analysis, feature development, bug investigation, and tests. Do **not** add AI in the runtime product unless it solves a clearly explained, indispensable workflow problem; approval is not needed for routine deterministic automation.
- Use a clean UI that visibly demonstrates the before/after workflow, not just a landing page.
- All commands documented for Ubuntu/WSL. Isolate local ports per task. Include `scripts/reset-demo.sh` and a deterministic seed dataset.
- Keep scope realistic for one repository. Focus on a narrow, fully working vertical slice instead of extensive placeholder features or architecture diagrams without code.

## Mandatory phase gates
1. **Baseline.** Implement a working, intentionally limited (but realistic) existing workflow. Document the limitation in `docs/01-baseline.md`. Commit it with message `baseline: working original workflow` and make Git tag `baseline-demo`. Avoid artificially sabotaging production logic just to manufacture dramatic results.
2. **Diagnosis.** Generate reproducible scenarios that expose the bottleneck. Write `docs/02-diagnosis.md` with observed behavior, suspected causes, and measurable target. Tests should distinguish expected behavior from known shortcomings.
3. **Improvement.** Use Codex-assisted code exploration, implementation and testing to add the smallest effective improvement. Prefer deterministic logic, existing libraries, database constraints, and tests. Commit with `improvement: ...`.
4. **Evaluation.** Run reproducible baseline/after tests or scripts against comparable synthetic data. Report exact metrics in `docs/03-results.md`, including methodology, sample sizes, limitations, and outcomes that did **not** improve. Never invent timings or report suggested targets as measured results.
5. **Handoff.** Produce `README.md`, `docs/04-ai-engineering-process.md`, `docs/05-tradeoffs.md`, `docs/demo-script.md`, and `portfolio/case-study.md`. Include links or paths to code/tests and a quickstart. Document changes and handoff guidance an existing small engineering team could follow.

## What the AI documentation must contain
- What Codex examined (file paths, schemas, logs/tests).
- What decisions it proposed and what was accepted/rejected after engineering review.
- Specific changes to code, tests, and operational workflow.
- Which parts of the final workflow are **ordinary deterministic automation**, which parts benefited from **AI-assisted development**, and which parts still require humans.
- Avoid invented accounts of elapsed human engineering time or fabricated comparisons to a human-only team. If it wasn't measured, say so.

## Quality bar
- Run backend tests and frontend typecheck/build. Run the UI smoke test when tooling permits; document any unavailable browser dependencies.
- Do not leave endpoints as TODOs or dashboards with fake metrics. If a metric is displayed, derive it from live seeded data or mark it clearly as an illustrative scenario.
- Include input validation, meaningful error messages, idempotency where relevant, a deterministic reset path, and at least one negative/edge-case test.
- README must include exact setup, install, test, seed/reset, run, demo, and troubleshooting commands.
- At end, summarize features built, commands actually executed, passing/failing tests, benchmark outputs, relevant Git commits, and known limitations. Never claim to have run a command that was not run.

## Reporting to the hiring manager
Lead with the existing operational/engineering process, not AI. Show why the specific improvement matters, the before/after workflow, and verified evidence. Present the work as **independent, synthetic, portfolio-company-inspired demonstrations**, never as Beacon production changes.

# PROJECT 1 — Club/League Integration Reliability Lab

## Story (not a claim about a real company)
Inspired by the category of sports registration and league-management businesses. Two acquired SaaS systems must share roster information. The goal is to show how an engineer joining unfamiliar systems can use an AI coding agent to understand data models, implement an integration safely, and establish tests and operational monitoring.

## Product WITHOUT AI / baseline workflow
- **Club Portal:** Register synthetic players, manage teams, record transfer to another team. Persists club-local identifiers and membership details.
- **League Portal:** Manage league teams and eligibility roster. Has its **own** identifiers and records, not a shared database representation.
- **Baseline integration:** Admin exports club roster CSV and uploads it to league portal to synchronize. Support staff check discrepancies manually. A transfer or duplicate update can leave stale or inconsistent rosters. Show this baseline visibly in the UI.

## Concrete problem to demonstrate
1. Repeated exports/imports consume manual actions.
2. Records use different IDs; naive imports create duplicates or stale assignments.
3. Partial failures are difficult to diagnose and retry.
4. Engineers adding an integration must reverse-engineer both systems, mappings and edge cases.

## AI-assisted engineering intervention
Use Codex **as the engineer's workflow tool**, not a customer-facing feature. Explore the baseline schemas/API contracts, propose a mapping design, implement a reliable service and generate tests. In `docs/04-ai-engineering-process.md`, include the reviewed design decisions and why deterministic synchronization is preferable to an LLM performing runtime roster updates.

## Improved workflow to implement
- Event/outbox-style or reliable queued synchronization from club to league, with a stable source-to-target identity map.
- Idempotent updates (same event replayed twice must not create duplicates); correct player transfer handling; retry status and safe resolution for failures; clear audit trail.
- Admin dashboard with sync events, failed jobs, pending status, reconciliation report, retry controls, and a visible before/after workflow selector or two pages.
- Clear ownership of authoritative fields; conflicting edits should not silently overwrite data.
- Simulate network failures and duplicate events; no external messaging broker required if a robust SQLite-backed queue works.

## Required demonstration scenario
- Seed 2 clubs, 4 teams, 20 synthetic players, and a league copy.
- Transfer a player on the club side. Baseline league copy remains stale until manual sync.
- Improved mode synchronizes, detects or avoids duplicate source events, and shows the correct league roster.
- Simulate a temporary sync failure and demonstrate safe retry + audit trail.
- Reset to a known state using one command.

## Real measurements
Provide executable scripts and output, with actual observed values, for at least:
- Number of manual operator actions required to update a transfer in baseline vs improved workflow.
- Reconciliation mismatches after a seeded batch and duplicate replay.
- Delivery/processing success count across an identical deterministic scenario; elapsed time if reliably measured, but do not claim human effort saved from machine timing alone.

## Tech / local ports
React + TypeScript + Vite frontend `5173`, FastAPI backend `8001`, SQLite local. Ports configurable through documented env vars. Keep Club and League logically separated in code/models; do not make them secretly share a mutable player database. Backend API may be a modular monolith for manageable scope.

## Deliberately out of scope
Actual PowerUp/E2E APIs, real identity data, payments, external notifications, distributed exactly-once guarantees, multi-tenant enterprise security.

## Case-study headline
"AI-Assisted Integration of Two Legacy SaaS Workflows: From Manual Roster Reconciliation to Reliable Synchronization"
