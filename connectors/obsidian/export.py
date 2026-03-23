#!/usr/bin/env python3
"""
Embedded → Obsidian Connector

Exports your voice memos as Obsidian-compatible Markdown files with
YAML frontmatter, organized by month.

Usage:
    python export.py --email you@example.com --vault-path ~/Obsidian/Vault/VoiceMemos
    python export.py --email you@example.com --vault-path ~/Vault --incremental
    python export.py --email you@example.com --vault-path ~/Vault --category Idea
    python export.py --email you@example.com --vault-path ~/Vault --dry-run
"""

import argparse
import getpass
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add repo root to path so we can import the shared client
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from embedded import EmbeddedClient, AuthError, APIError

LAST_EXPORT_FILE = ".last_export"


# ---------------------------------------------------------------------------
# Markdown generation
# ---------------------------------------------------------------------------

def _sanitize_filename(s: str) -> str:
    """Remove characters that are unsafe for filenames."""
    return re.sub(r'[\\/*?:"<>|]', "", s).strip()


def _parse_date(raw) -> datetime | None:
    """Best-effort parse of ISO timestamp string."""
    if not raw:
        return None
    if isinstance(raw, datetime):
        return raw
    try:
        text = str(raw).replace("Z", "+00:00")
        return datetime.fromisoformat(text)
    except (ValueError, TypeError):
        return None


def memo_to_markdown(memo: dict) -> str:
    """Convert a memo dict to an Obsidian-compatible Markdown string."""
    memo_id = memo.get("memo_id", "unknown")
    category = memo.get("category", "Other")
    summary = memo.get("summary", "")
    transcription = memo.get("transcription", "")
    audio_file = memo.get("audio_file_name", "")
    chunk_count = memo.get("chunk_count", 1)
    date_str = memo.get("created_at", "")

    tags = ["voice-memo", category.lower().replace(" ", "-")]
    user_tags_raw = memo.get("tags", "")
    if user_tags_raw:
        for t in str(user_tags_raw).split(","):
            t = t.strip().lower().replace(" ", "-")
            if t and t not in tags:
                tags.append(t)

    title_hint = summary[:60].replace("\n", " ").strip() if summary else category
    title = f"Voice Memo – {title_hint}"

    lines = [
        "---",
        f"title: \"{title}\"",
        f"date: {date_str}",
        f"category: {category}",
        "tags:",
    ]
    for t in tags:
        lines.append(f"  - {t}")
    lines += [
        f"memo_id: {memo_id}",
        f"audio_file: {audio_file}",
        f"embedding_chunks: {chunk_count}",
        "source: gray-matter",
        "---",
        "",
    ]

    if summary:
        lines += ["## Summary", "", summary.strip(), ""]

    if transcription:
        lines += ["## Transcription", "", transcription.strip(), ""]

    return "\n".join(lines)


def write_memo_file(memo: dict, vault_path: Path) -> Path:
    """Write a single memo as a Markdown file and return its path."""
    memo_id = memo.get("memo_id", "unknown")
    category = memo.get("category", "Other").lower().replace(" ", "-")
    dt = _parse_date(memo.get("created_at"))

    if dt:
        month_folder = dt.strftime("%Y-%m")
        date_prefix = dt.strftime("%Y-%m-%d")
    else:
        month_folder = "undated"
        date_prefix = "undated"

    short_id = memo_id[:8]
    filename = _sanitize_filename(f"{date_prefix}-{category}-{short_id}.md")

    folder = vault_path / month_folder
    folder.mkdir(parents=True, exist_ok=True)

    filepath = folder / filename
    filepath.write_text(memo_to_markdown(memo), encoding="utf-8")
    return filepath


# ---------------------------------------------------------------------------
# Incremental sync helpers
# ---------------------------------------------------------------------------

def read_last_export(vault_path: Path) -> str | None:
    marker = vault_path / LAST_EXPORT_FILE
    if marker.exists():
        return marker.read_text(encoding="utf-8").strip() or None
    return None


def write_last_export(vault_path: Path, timestamp: str):
    marker = vault_path / LAST_EXPORT_FILE
    marker.write_text(timestamp + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Export Embedded voice memos to Obsidian Markdown.",
    )
    parser.add_argument("--email", required=True, help="Your Embedded account email")
    parser.add_argument("--vault-path", required=True, help="Obsidian vault directory for memos")
    parser.add_argument("--incremental", action="store_true", help="Only export new memos since last run")
    parser.add_argument("--category", help="Filter by category (Meeting, Idea, ToDo, etc.)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing files")
    args = parser.parse_args()

    vault_path = Path(args.vault_path).expanduser().resolve()
    vault_path.mkdir(parents=True, exist_ok=True)

    password = getpass.getpass("Embedded password: ")

    # Authenticate
    client = EmbeddedClient()
    try:
        print(f"Signing in as {args.email}...")
        client.login(args.email, password)
        print("Authenticated successfully.")
    except AuthError as e:
        print(e)
        sys.exit(1)

    # Incremental check
    since = None
    if args.incremental:
        since = read_last_export(vault_path)
        if since:
            print(f"Incremental mode: fetching memos after {since}")
        else:
            print("No previous export found, performing full export.")

    # Fetch memos
    try:
        print("Fetching your memos...")
        memos = client.get_memos(since=since, category=args.category)
        print(f"Found {len(memos)} memo(s)")
    except (AuthError, APIError) as e:
        print(e)
        sys.exit(1)

    if not memos:
        print("Nothing to export.")
        return

    # Write or preview
    for memo in memos:
        if args.dry_run:
            dt = _parse_date(memo.get("created_at"))
            date_label = dt.strftime("%Y-%m-%d") if dt else "undated"
            print(f"  [dry-run] {date_label} | {memo['category']:12s} | {memo['memo_id'][:8]}...")
        else:
            fp = write_memo_file(memo, vault_path)
            print(f"  -> {fp.relative_to(vault_path)}")

    if args.dry_run:
        print(f"\nDry run complete. {len(memos)} memo(s) would be exported.")
        return

    # Update marker
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    write_last_export(vault_path, now)
    print(f"\nExported {len(memos)} memo(s) to {vault_path}")
    print(f"Last-export marker set to {now}")


if __name__ == "__main__":
    main()
