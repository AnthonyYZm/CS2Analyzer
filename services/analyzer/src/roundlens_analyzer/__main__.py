from __future__ import annotations

import argparse
import importlib.metadata
import json
import logging
import sys
from pathlib import Path

from roundlens_analyzer import PROTOCOL_VERSION, __version__
from roundlens_analyzer.app.config import AppPaths
from roundlens_analyzer.ipc.server import JsonlServer


def configure_stdio() -> None:
    """Keep the JSONL transport UTF-8 even on Chinese Windows code pages."""
    for stream, errors in ((sys.stdout, "strict"), (sys.stderr, "backslashreplace")):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(
                encoding="utf-8",
                errors=errors,
                newline="\n",
                write_through=True,
            )


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="RoundLens local analyzer sidecar")
    result.add_argument("--data-dir", type=Path, default=None)
    result.add_argument("--health-check", action="store_true")
    result.add_argument("--version", action="store_true")
    return result


def main() -> int:
    configure_stdio()
    args = parser().parse_args()
    if args.version:
        print(__version__)
        return 0
    paths = AppPaths.create(args.data_dir)
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    if args.health_check:
        try:
            from awpy import Demo as AwpyDemo  # type: ignore[import-untyped]
            from demoparser2 import DemoParser

            del AwpyDemo, DemoParser
            parser_versions = {
                "awpy": importlib.metadata.version("awpy"),
                "demoparser2": importlib.metadata.version("demoparser2"),
            }
        except (ImportError, importlib.metadata.PackageNotFoundError) as exc:
            print(
                json.dumps(
                    {
                        "protocol_version": PROTOCOL_VERSION,
                        "status": "error",
                        "code": "PARSER_DEPENDENCY_MISSING",
                        "message": str(exc),
                    },
                    ensure_ascii=True,
                    separators=(",", ":"),
                )
            )
            return 1
        print(
            json.dumps(
                {
                    "protocol_version": PROTOCOL_VERSION,
                    "status": "ok",
                    "version": __version__,
                    "data_dir": str(paths.root),
                    "parsers": parser_versions,
                },
                ensure_ascii=True,
                separators=(",", ":"),
            )
        )
        return 0
    return JsonlServer(paths.root).run()


if __name__ == "__main__":
    raise SystemExit(main())
