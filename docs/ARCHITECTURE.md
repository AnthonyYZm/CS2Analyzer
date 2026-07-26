# Architecture

```text
React/Vite UI
  │ Tauri invoke + events (no secret reads)
Rust/Tauri host
  ├─ file dialogs and validated local paths
  ├─ Windows Credential Manager
  └─ supervised stdin/stdout JSONL
Python sidecar
  ├─ import/hash/parse jobs
  ├─ Awpy + demoparser2 -> normalized domain model
  ├─ metrics -> issues/strengths/review candidates
  ├─ deterministic or validated LLM report
  └─ SQLite metadata + Parquet dense data
```

The Rust process owns the sidecar lifecycle and application data path. A single sidecar worker serializes parsing by default. Requests receive immediate IDs/results; progress and terminal status are emitted as events. The sidecar has a method allowlist and never opens a local HTTP port.

Parser adapters expose `probe`, `parse_core`, `parse_events`, and `parse_ticks`. The composite parser treats demoparser2 as a supplement, not an independent fallback. Each capability is recorded independently so Level A core events can survive Level B/C failure.

Relational entities and aggregates live in SQLite with foreign keys and WAL. Dense ticks, positions, shots and trajectories use per-match Parquet files. Reports are immutable versioned JSON snapshots; deleting a source match marks dependent reports stale.

AI receives only bounded aggregate metrics, comparisons, candidates and compact round timelines. It never recomputes metrics. Output passes strict schema and reference validation; invalid output is repaired at most twice, then replaced by the deterministic report.
