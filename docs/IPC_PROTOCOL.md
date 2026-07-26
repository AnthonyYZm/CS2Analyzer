# IPC protocol

Transport is UTF-8 JSONL over sidecar stdin/stdout. Every line is one object. Protocol version is `1`; stdout contains no ordinary log text.

Request: `{"protocol_version":1,"id":"uuid","method":"health","params":{}}`

Success: `{"protocol_version":1,"id":"uuid","result":{...}}`

Failure: `{"protocol_version":1,"id":"uuid","error":{"code":"DEMO_NOT_FOUND","message":"...","details":{}}}`

Event: `{"protocol_version":1,"event":"job.progress","data":{"job_id":"uuid","stage":"parsing_core","progress":30,"message":"..."}}`

Allowed methods: `health`, `initialize`, `get_settings`, `update_profile`, `scan_demos`, `import_demos`, `list_demos`, `parse_demo`, `cancel_job`, `list_jobs`, `list_matches`, `relink_demo`, `create_analysis`, `get_analysis`, `delete_report`, `delete_match_data`, `shutdown`.

The host enforces request timeouts and correlates response IDs. Sidecar restart changes running jobs to `interrupted`; paid AI jobs are never auto-retried. Error codes are stable and technical details belong in redacted stderr/file logs.
