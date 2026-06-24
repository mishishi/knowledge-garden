# Harness Minimal Demo

A real, runnable implementation of the agent harness described in
[Harness Engineering Chapter 10](../../books/harness-engineering/10-build-from-scratch/).

The chapter showed an 800-line reference implementation as pseudocode. This demo
takes the core loop from that chapter and shrinks it to **~200 lines of real Python**
that actually runs against the Anthropic API.

## What it demonstrates

The minimum viable harness that includes the 9 components from the book:

- **Agent loop** (ch 2) — `while not done` with cost + step ceiling
- **Tool design** (ch 3) — bash + read_file with allowlist + timeout
- **Context management** (ch 4) — message pruning at 80% window
- **Permissions / sandbox** (ch 5) — allowlist + subprocess non-root + cwd restriction
- **Observability** (ch 6) — trajectory logging to JSONL
- **Memory** (ch 7) — working memory only (episodic + semantic out of scope for minimal)
- **Failure recovery** (ch 8) — exponential backoff on rate limit + transient errors
- **Eval-driven** (ch 9) — `evals/golden_set.json` + `run_eval.py`

What's NOT included (deliberately, to stay under 250 lines):
- Multi-agent orchestration (single agent only)
- Vector DB / semantic memory
- Checkpoint + rollback (we trust the allowlist instead)
- Web UI / interactive confirmation

## File layout

```
demos/harness-minimal/
├── agent.py        # The 200-line minimal harness
├── demo.py         # Real demo: "summarize this README" with 2 tools
├── evals/
│   ├── golden_set.json   # 5 test cases
│   └── run_eval.py       # Run all cases, report pass rate
├── requirements.txt
└── README.md
```

## Setup

```bash
cd demos/harness-minimal
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-xxx
```

## Run the demo

```bash
python demo.py
```

The demo gives the agent this task:

> Read `demos/harness-minimal/README.md`, summarize the file in 3 bullets.

Expected output:

```
[step 1] LLM decided to call read_file(path='demos/harness-minimal/README.md')
[step 2] LLM decided to call bash(cmd='wc -l demos/harness-minimal/README.md')
[step 3] LLM produced final summary

Summary:
- Harness Minimal Demo: a 200-line runnable agent harness from ch 10
- Demonstrates 7 of 9 components (omits vector memory + checkpoint for brevity)
- Setup: pip install + export ANTHROPIC_API_KEY + python demo.py

Cost: $0.0082 | Steps: 3 | Status: completed
```

A real run lands within ±$0.005 of that cost and ±1 step. Trajectory is appended
to `trajectory.jsonl` for later analysis.

## Run the evals

```bash
python evals/run_eval.py
```

Runs 5 golden-set cases against the harness, reports pass rate per case and
overall. Currently 4/5 pass; the failing case is "long-context summarization"
which needs the real compact logic from ch 4 (this minimal demo only prunes).

## Why "minimal" instead of full

The book's ch 10 reference implementation is 800 lines. That's still a lot for
"hello world". This demo is the smallest possible thing that demonstrates the
concepts without becoming a maintenance burden. If you want to extend it:

- Add `episodic_memory.py` for SQLite episode storage
- Add `semantic_memory.py` for Chroma vector memory
- Add `checkpoint.py` for git-stash-based rollback
- Add a `tools/` package and split the 2 tools out of `agent.py`

Each extension is a separate exercise — they take you from 200 lines to
2000+ lines, the production-grade harness described in ch 10.
