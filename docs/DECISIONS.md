# Architecture decision records

## ADR-001: Tauri 2 desktop host

Accepted. Tauri provides a small Windows-native host, explicit permissions, WebView UI and bundling without embedding a full Chromium runtime. Rust owns filesystem, process and secret boundaries that must not be exposed to React.

## ADR-002: Python sidecar

Accepted. CS2 parsing and columnar/data-science libraries are Python-first. Packaging a supervised sidecar isolates parser failures and avoids reimplementing Awpy/demoparser2 logic in Rust.

## ADR-003: JSONL RPC instead of localhost HTTP

Accepted. stdin/stdout needs no port, firewall rule, authentication token or background daemon. Request IDs, progress events, timeouts and cancellation cover the MVP workload.

## ADR-004: SQLite plus Parquet

Accepted. SQLite gives transactional relations, history and migrations. Parquet avoids inflating SQLite with high-frequency tick, shot and trajectory rows and supports efficient column scans.

## ADR-005: Awpy primary, demoparser2 supplement

Accepted. Awpy provides the primary semantic parse and map ecosystem; demoparser2 exposes useful raw event/tick queries. They share underlying format risk, so the latter is a field supplement, not marketed as full disaster recovery.

## ADR-006: rule impact before ML win probability

Accepted. No licensed, representative and calibrated training corpus is available. A versioned, explainable rule score can prioritize review without falsely claiming exact win probability.

## ADR-007: no raw ticks sent to models

Accepted. Raw ticks are privacy-heavy, costly and encourage unverified arithmetic. Deterministic code computes metrics and candidates; the model only organizes a bounded, reference-valid report.

## ADR-008: PyInstaller one-dir

Accepted. Parser/Arrow libraries have large binaries and hidden imports. One-dir improves startup and diagnosability; Tauri bundles the directory so the end user still gets one installer.
