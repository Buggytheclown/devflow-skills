#!/usr/bin/env python3
"""Create an isolated review journal using the user's Devflow configuration."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import secrets
import sys


REVIEWERS = {
    "bugs-impl": ["bugs", "impl"],
    "arch-quality": ["architecture", "quality"],
    "docs-tests": ["docs", "tests", "comments"],
    "adversarial": ["adversarial"],
    "deployment": ["deployment"],
}
PROFILES = {
    "full": {role: "gpt-6.1-sol" for role in (*REVIEWERS, "validator")},
    "light": {
        "bugs-impl": "gpt-6.1-sol",
        "docs-tests": "gpt-6.1-terra",
        "validator": "gpt-6.1-terra",
    },
}


def pr_id(value):
    if not value.isascii() or not value.isdecimal():
        raise argparse.ArgumentTypeError("PR ID must contain only digits")
    return value


def create_run(config_path, pr, mode="full"):
    if mode not in PROFILES:
        raise ValueError(f"unknown review mode: {mode}")
    models = PROFILES[mode]
    config = json.loads(config_path.read_text(encoding="utf-8"))
    root_value = config.get("review_logs_root") if isinstance(config, dict) else None
    if not isinstance(root_value, str) or not root_value.strip():
        raise ValueError("config must define a non-empty review_logs_root string")
    root = Path(root_value).expanduser()
    if not root.is_absolute():
        raise ValueError("review_logs_root must be absolute (or start with ~)")
    skill_dir = Path(__file__).resolve().parent.parent
    instruction_names = ["SKILL.md", "references/logging.md", "references/report.md"] + [
        f"lenses/{lens}.md" for lenses in REVIEWERS.values() for lens in lenses
    ]
    instructions = {
        name: (skill_dir / name).read_text(encoding="utf-8")
        for name in instruction_names
    }
    root.mkdir(parents=True, exist_ok=True)
    prefix = f"PR-{pr}" if pr else "DIFF"
    for _ in range(10):
        uid = f"{secrets.randbelow(10**18):018d}"
        run_dir = root / f"{prefix}-{uid}"
        try:
            run_dir.mkdir(mode=0o700)
            break
        except FileExistsError:
            continue
    else:
        raise ValueError("could not allocate a unique review directory")

    participants = {"coordinator": [], **REVIEWERS, "validator": []}
    metadata = {
        "schema_version": 1,
        "run_id": uid,
        "subject": {"kind": "pr" if pr else "diff", "pr_id": pr, "url": None},
        "status": "running",
        "mode": mode,
        "profile": mode,
        "previous_run": None,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
        "config_path": str(config_path.resolve()),
        "skill": {
            "path": str(skill_dir),
            "instruction_sha256": {
                name: hashlib.sha256(contents.encode("utf-8")).hexdigest()
                for name, contents in instructions.items()
            },
            "instructions": instructions,
        },
        "request": None,
        "snapshot": None,
        "context": [],
        "participants": [
            {
                "role": role,
                "lenses": lenses,
                "agent_id": None,
                "requested_model": models.get(role),
                "reported_model": None,
                "parameters": {"reasoning_effort": "high"} if role in models else {},
                "status": (
                    "running" if role == "coordinator"
                    else "pending" if role in models else "not_requested"
                ),
                "started_at": None,
                "finished_at": None,
                "usage": None,
            }
            for role, lenses in participants.items()
        ],
    }
    try:
        with (run_dir / "run.json").open("x", encoding="utf-8") as stream:
            json.dump(metadata, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        for role, lenses in REVIEWERS.items():
            status = "pending" if role in models else "not_requested"
            for lens in lenses:
                with (run_dir / f"{lens}.md").open("x", encoding="utf-8") as stream:
                    stream.write(f"# {lens}\n\nstatus: {status}\nreviewer: {role}\n")
        for filename, title in [("validation.md", "Валидация"), ("result.md", "Результат")]:
            with (run_dir / filename).open("x", encoding="utf-8") as stream:
                stream.write(f"# {title}\n\nstatus: pending\n")
    except OSError as exc:
        raise OSError(f"incomplete journal at {run_dir}: {exc}") from exc
    return run_dir


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr", type=pr_id, help="Canonical numeric PR ID; omit for a local diff")
    parser.add_argument("--config", type=Path, default=Path.home() / ".devflow/config.json")
    parser.add_argument("--mode", choices=PROFILES, default="full", help="Review mode (default: full)")
    args = parser.parse_args()
    try:
        run_dir = create_run(args.config.expanduser(), args.pr, args.mode)
    except (OSError, ValueError) as exc:
        print(f"Cannot create review journal: {exc}", file=sys.stderr)
        return 1
    print(run_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
