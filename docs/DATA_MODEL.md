# Data model

SQLite uses WAL, foreign keys, transactions, indexed IDs/hash/timestamps and a schema version. Core entities are:

- settings/profile: `app_settings`, `player_profile` (never API keys).
- imports/jobs: `demo_files`, `parse_jobs`.
- normalized match data: `matches`, `match_players`, `rounds`, `kills`, `damages`, `bomb_events`, `grenade_events`, `player_round_stats`.
- analysis: `metric_definitions`, `metric_values`, `issue_instances`, `strength_instances`, `review_rounds`, `analyses`, `analysis_matches`, `analysis_reports`, `training_goals`.
- capabilities/versioning: `benchmark_versions`, `map_capabilities`.

Null means unknown/not observed and is never coerced to zero. Every metric stores status, sample size, confidence, calculation version, context and evidence references. Match capability values are `available`, `estimated`, `partial`, `unavailable`, or `invalid`.

Parquet is partitioned by match under `parsed/<match_id>/` for ticks, positions, shots and trajectories. JSON reports are immutable snapshots under `reports/<analysis_id>.json`; SQLite stores their status, versions and path.
