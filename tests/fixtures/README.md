# Local Demo fixtures

Do not commit real or unlicensed `.dem` files. Put personally supplied test files under `tests/fixtures/local/` (gitignored), then run the optional local regression test with an explicit path/environment variable. Record expected map, round count, score, players, kills and damage in a separate local file that contains no API key or Steam login data.

CI uses synthetic normalized events and mock parser frames only. A synthetic fixture is test data, never presented by the production UI as a parsed match.
