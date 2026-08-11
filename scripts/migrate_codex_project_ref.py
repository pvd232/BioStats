#!/usr/bin/env python3
"""Update local Codex project/thread references after moving a project folder.

Default migration:
    /Users/machina/Documents/Bio Stats
    -> /Users/machina/Documents/ChatGPT/BioStats

The script updates local ChatGPT/Codex desktop state: Codex thread cwd rows,
saved thread-log session metadata, and the desktop file-picker path. It backs up
changed state files under ~/.codex/backups before writing.

Quit the ChatGPT desktop app before a real run so it does not rewrite these
files from stale in-memory state.

Preview:
    ./scripts/migrate_codex_project_ref.py --dry-run --allow-missing

Run the default migration:
    ./scripts/migrate_codex_project_ref.py --create-target

Run a future migration:
    ./scripts/migrate_codex_project_ref.py --old "/old/path" --new "/new/path"
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


DEFAULT_OLD_PATH = "/Users/machina/Documents/Bio Stats"
DEFAULT_NEW_PATH = "/Users/machina/Documents/ChatGPT/BioStats"


@dataclass(frozen=True)
class SqliteUpdate:
    db_path: Path
    table: str
    column: str
    where: str
    params: tuple[str, ...]


def default_codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()


def default_sqlite_home(codex_home: Path) -> Path:
    return Path(os.environ.get("CODEX_SQLITE_HOME", codex_home / "sqlite")).expanduser()


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def backup_file(path: Path, backup_dir: Path, dry_run: bool) -> Path | None:
    if not path.exists():
        return None
    backup_path = backup_dir / path.name
    if dry_run:
        print(f"Would back up {path} -> {backup_path}")
        return backup_path
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup_path)
    print(f"Backed up {path} -> {backup_path}")
    return backup_path


def sqlite_count(db_path: Path, table: str, column: str, value: str) -> int:
    if not db_path.exists():
        return 0
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {column} = ?",
            (value,),
        ).fetchone()
    return int(row[0])


def matching_rollout_paths(state_db: Path, old_path: str) -> list[Path]:
    if not state_db.exists():
        return []
    with sqlite3.connect(state_db) as conn:
        rows = conn.execute(
            "SELECT rollout_path FROM threads WHERE cwd = ? ORDER BY updated_at DESC",
            (old_path,),
        ).fetchall()
    return [Path(row[0]) for row in rows if row and row[0]]


def sqlite_replace_exact(update: SqliteUpdate, new_path: str, dry_run: bool) -> int:
    if not update.db_path.exists():
        print(f"Skipping missing database: {update.db_path}")
        return 0

    with sqlite3.connect(update.db_path) as conn:
        count = conn.execute(
            f"SELECT COUNT(*) FROM {update.table} WHERE {update.where}",
            update.params,
        ).fetchone()[0]
        if dry_run:
            print(
                f"Would update {count} row(s) in "
                f"{update.db_path}:{update.table}.{update.column}"
            )
            return int(count)
        conn.execute(
            f"UPDATE {update.table} SET {update.column} = ? WHERE {update.where}",
            (new_path, *update.params),
        )
        conn.commit()
        print(
            f"Updated {count} row(s) in "
            f"{update.db_path}:{update.table}.{update.column}"
        )
        return int(count)


def update_rollout_session_meta(
    rollout_paths: list[Path],
    old_path: str,
    new_path: str,
    backup_dir: Path,
    dry_run: bool,
) -> int:
    changed = 0
    for rollout_path in rollout_paths:
        if not rollout_path.exists():
            print(f"Skipping missing rollout log: {rollout_path}")
            continue

        try:
            lines = rollout_path.read_text(encoding="utf-8").splitlines(keepends=True)
        except UnicodeDecodeError as exc:
            print(f"Skipping non-UTF-8 rollout log {rollout_path}: {exc}", file=sys.stderr)
            continue

        if not lines:
            continue

        try:
            first_event = json.loads(lines[0])
        except json.JSONDecodeError as exc:
            print(f"Skipping rollout log with invalid first event {rollout_path}: {exc}", file=sys.stderr)
            continue

        payload = first_event.get("payload")
        if first_event.get("type") != "session_meta" or not isinstance(payload, dict):
            continue
        if payload.get("cwd") != old_path:
            continue

        if dry_run:
            print(f"Would update session_meta cwd in {rollout_path}")
            changed += 1
            continue

        backup_file(rollout_path, backup_dir, dry_run=False)
        payload["cwd"] = new_path
        lines[0] = json.dumps(first_event, ensure_ascii=False, separators=(",", ":")) + "\n"
        rollout_path.write_text("".join(lines), encoding="utf-8")
        print(f"Updated session_meta cwd in {rollout_path}")
        changed += 1

    return changed


def update_preferences_last_directory(
    preferences_path: Path,
    old_path: str,
    new_path: str,
    backup_dir: Path,
    dry_run: bool,
) -> bool:
    if not preferences_path.exists():
        print(f"Skipping missing preferences file: {preferences_path}")
        return False

    try:
        data = json.loads(preferences_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"Skipping preferences file; it is not valid JSON: {exc}", file=sys.stderr)
        return False

    selectfile = data.get("selectfile")
    if not isinstance(selectfile, dict):
        print("No selectfile.last_directory preference found.")
        return False

    last_directory = selectfile.get("last_directory")
    if not isinstance(last_directory, str) or not last_directory.startswith(old_path):
        print("No matching selectfile.last_directory value to update.")
        return False

    updated_directory = new_path + last_directory[len(old_path) :]
    if dry_run:
        print(
            "Would update selectfile.last_directory: "
            f"{last_directory} -> {updated_directory}"
        )
        return True

    backup_file(preferences_path, backup_dir, dry_run=False)
    selectfile["last_directory"] = updated_directory
    preferences_path.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(
        "Updated selectfile.last_directory: "
        f"{last_directory} -> {updated_directory}"
    )
    return True


def path_arg(value: str) -> str:
    return str(Path(value).expanduser())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migrate local Codex refs from one project path to another.",
    )
    parser.add_argument(
        "--old",
        default=DEFAULT_OLD_PATH,
        type=path_arg,
        help=f"Old project path. Default: {DEFAULT_OLD_PATH}",
    )
    parser.add_argument(
        "--new",
        default=DEFAULT_NEW_PATH,
        type=path_arg,
        help=f"New project path. Default: {DEFAULT_NEW_PATH}",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing anything.",
    )
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Allow the new path to be missing.",
    )
    parser.add_argument(
        "--create-target",
        action="store_true",
        help="Create the new target directory if it is missing.",
    )
    parser.add_argument(
        "--skip-rollout-logs",
        action="store_true",
        help="Do not update saved thread-log session metadata.",
    )
    parser.add_argument(
        "--codex-home",
        type=Path,
        default=default_codex_home(),
        help="Codex home directory. Default: CODEX_HOME or ~/.codex.",
    )
    parser.add_argument(
        "--app-support",
        type=Path,
        default=Path.home() / "Library/Application Support/Codex",
        help="ChatGPT/Codex desktop app support directory.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    old_path = args.old.rstrip("/")
    new_path = args.new.rstrip("/")
    new_path_obj = Path(new_path)
    codex_home = args.codex_home.expanduser()
    sqlite_home = default_sqlite_home(codex_home)
    backup_dir = codex_home / "backups" / f"migrate-codex-project-ref-{timestamp()}"

    if old_path == new_path:
        print("Old and new paths are identical; nothing to do.")
        return 0

    if not new_path_obj.exists():
        if args.create_target:
            if args.dry_run:
                print(f"Would create target directory: {new_path_obj}")
            else:
                new_path_obj.mkdir(parents=True, exist_ok=True)
                print(f"Created target directory: {new_path_obj}")
        elif not args.allow_missing:
            print(
                f"New path does not exist: {new_path_obj}\n"
                "Move/create it first, or rerun with --create-target or --allow-missing.",
                file=sys.stderr,
            )
            return 2

    state_db = codex_home / "state_5.sqlite"
    catalog_db = sqlite_home / "codex-dev.db"
    preferences = args.app_support.expanduser() / "Default" / "Preferences"

    print(f"Old path: {old_path}")
    print(f"New path: {new_path}")
    print(f"Backup directory: {backup_dir}")
    rollout_paths = matching_rollout_paths(state_db, old_path)

    updates = [
        SqliteUpdate(
            db_path=state_db,
            table="threads",
            column="cwd",
            where="cwd = ?",
            params=(old_path,),
        ),
        SqliteUpdate(
            db_path=catalog_db,
            table="local_thread_catalog",
            column="cwd",
            where="cwd = ?",
            params=(old_path,),
        ),
        SqliteUpdate(
            db_path=catalog_db,
            table="automations",
            column="cwds",
            where="cwds = ?",
            params=(json.dumps([old_path]),),
        ),
        SqliteUpdate(
            db_path=catalog_db,
            table="automation_runs",
            column="source_cwd",
            where="source_cwd = ?",
            params=(old_path,),
        ),
    ]

    dbs_to_backup = sorted({update.db_path for update in updates if update.db_path.exists()})
    for db_path in dbs_to_backup:
        backup_file(db_path, backup_dir, args.dry_run)

    total_rows = 0
    for update in updates:
        total_rows += sqlite_replace_exact(update, new_path, args.dry_run)

    rollout_count = 0
    if args.skip_rollout_logs:
        print("Skipping rollout log metadata updates.")
    else:
        rollout_count = update_rollout_session_meta(
            rollout_paths=rollout_paths,
            old_path=old_path,
            new_path=new_path,
            backup_dir=backup_dir,
            dry_run=args.dry_run,
        )

    update_preferences_last_directory(
        preferences_path=preferences,
        old_path=old_path,
        new_path=new_path,
        backup_dir=backup_dir,
        dry_run=args.dry_run,
    )

    old_remaining = sqlite_count(state_db, "threads", "cwd", old_path)
    new_total = sqlite_count(state_db, "threads", "cwd", new_path)
    print(f"state_5.sqlite old-path thread rows remaining: {old_remaining}")
    print(f"state_5.sqlite new-path thread rows: {new_total}")
    print(f"Total SQLite rows matched for update: {total_rows}")
    print(f"Rollout log metadata files matched for update: {rollout_count}")

    if args.dry_run:
        print("Dry run complete; no files were changed.")
    else:
        print("Migration complete. Restart the ChatGPT desktop app before testing it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
