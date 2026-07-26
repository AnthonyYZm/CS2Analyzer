# Security and privacy

Trust boundaries are the user-selected filesystem, untrusted Demo contents, untrusted player/map strings, the sidecar JSONL boundary and optional third-party model endpoints.

- Canonicalize and validate `.dem` paths; accept only regular files with `.dem` suffix, stream hashes, and verify hashes when relinking.
- Sidecar methods are allowlisted and receive validated Pydantic parameters. No arbitrary shell command or local HTTP listener exists.
- Demo/tick/trajectory data remain local. AI payloads exclude absolute paths, Steam login data, names where not needed, raw tick sequences and full trajectories.
- Treat all imported strings as data. Strip control characters, serialize a strict JSON data block and tell the model never to obey embedded instructions.
- Store API keys only through Windows Credential Manager. The UI can set/clear a key but cannot retrieve it. Test builds may inject an in-memory implementation.
- Redact bearer tokens, common API-key formats and sensitive field names before stderr/file logging and again before log export.
- Tauri capabilities include only explicit application commands/dialog/event permissions. No broad filesystem or shell permission is exposed to React.
- Destructive operations require UI confirmation, remain inside the application data root and never touch the source `.dem`.
- No telemetry, advertising or tracking SDK is included.
