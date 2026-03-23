#!/usr/bin/env python3
"""
Embedded Smart Vault — Ingest Pipeline

Fetches your voice memos from Embedded and routes them into your
Obsidian vault by category, with automatic person detection and
1:1 file management.

Routing:
    Meeting / People → person 1:1 file (if detected) or Meetings folder
    Idea             → Ideas folder
    Budget           → Budget folder
    ToDo             → Inbox (with checkboxes)
    Other            → General folder

Usage:
    python ingest.py --email you@example.com --dry-run
    python ingest.py --email you@example.com --execute
    python ingest.py --email you@example.com --execute --incremental
    python ingest.py --email you@example.com --execute --category Meeting
"""

import argparse
import getpass
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import yaml

# Add repo root to path for shared client
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
from embedded import EmbeddedClient, AuthError, APIError

from normalize import normalize_person_file

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_FILE = SCRIPT_DIR / "config.yaml"

# Fix Windows console encoding
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------

def load_config() -> dict:
    """Load config.yaml and resolve paths."""
    if not CONFIG_FILE.exists():
        print("Config not found. Run setup.py first.")
        sys.exit(1)

    config = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8"))
    vault = Path(config["vault_path"])
    if not vault.exists():
        print(f"Vault path not found: {vault}")
        print("Run setup.py to configure your vault.")
        sys.exit(1)

    config["_vault"] = vault
    config["_folders"] = {
        k: vault / v for k, v in config.get("folders", {}).items()
    }
    return config


def load_people(config: dict) -> tuple[list[dict], dict, dict]:
    """Load people.yaml and build lookup indexes.

    Returns:
        (people_list, by_name, by_nickname)
    """
    people_file = Path(config.get("people_file", ""))
    if not people_file.exists():
        people_file = config["_vault"] / "people.yaml"
    if not people_file.exists():
        return [], {}, {}

    data = yaml.safe_load(people_file.read_text(encoding="utf-8")) or {}
    people = data.get("people", [])
    me_name = (data.get("me", {}).get("name", "") or "").lower()

    by_name = {}
    by_nickname = {}
    for person in people:
        name = person.get("name", "")
        by_name[name.lower()] = person
        for nick in person.get("nickname", []):
            by_nickname[nick.lower()] = person

    return people, by_name, by_nickname, me_name


# -------------------------------------------------------------------
# Person detection
# -------------------------------------------------------------------

def detect_people(
    text: str,
    by_name: dict,
    by_nickname: dict,
    me_name: str,
) -> list[dict]:
    """Detect people mentioned in text by full name or nickname."""
    found = {}
    text_lower = text.lower()

    # Full name matches (highest confidence)
    for name_lower, person in by_name.items():
        if name_lower in text_lower and name_lower != me_name:
            found[person["name"]] = person

    # Nickname matches (only if >= 3 chars, word boundary)
    for nick, person in by_nickname.items():
        if len(nick) < 3:
            continue
        if person["name"] in found:
            continue
        if person["name"].lower() == me_name:
            continue
        pattern = rf"\b{re.escape(nick)}\b"
        if re.search(pattern, text_lower):
            found[person["name"]] = person

    return sorted(found.values(), key=lambda p: p["name"])


# -------------------------------------------------------------------
# File formatting
# -------------------------------------------------------------------

def _sanitize_filename(s: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", s).strip()


def _parse_date(raw) -> datetime | None:
    if not raw:
        return None
    try:
        text = str(raw).replace("Z", "+00:00")
        return datetime.fromisoformat(text)
    except (ValueError, TypeError):
        return None


def _build_tags(memo: dict, extra: list[str] = None) -> list[str]:
    """Build a deduplicated tag list for frontmatter."""
    tags = ["voice-memo"]
    cat = memo.get("category", "Other").lower().replace(" ", "-")
    if cat and cat not in tags:
        tags.append(cat)
    for t in (extra or []):
        if t and t not in tags:
            tags.append(t)
    raw = memo.get("tags", "")
    if raw:
        for t in str(raw).split(","):
            t = t.strip().lower().replace(" ", "-")
            if t and t not in tags:
                tags.append(t)
    return tags


def _frontmatter(fields: dict) -> str:
    """Render YAML frontmatter block."""
    lines = ["---"]
    for key, val in fields.items():
        if isinstance(val, list):
            lines.append(f"{key}:")
            for item in val:
                lines.append(f"  - {item}")
        elif val is None or val == "":
            lines.append(f"{key}:")
        else:
            if isinstance(val, str) and ('"' in val or ":" in val or val.startswith("{")):
                lines.append(f'{key}: "{val}"')
            else:
                lines.append(f"{key}: {val}")
    lines.append("---")
    return "\n".join(lines)


def format_1on1_entry(memo: dict, people: list[dict]) -> str:
    """Format a memo as a meeting entry for appending to a person 1:1 file."""
    dt = _parse_date(memo.get("created_at"))
    date_str = dt.strftime("%Y-%m-%d") if dt else "undated"
    time_str = dt.strftime("%H:%M") if dt else ""
    category = memo.get("category", "Other")
    summary = memo.get("summary", "")
    transcription = memo.get("transcription", "")
    people_names = ", ".join(p["name"] for p in people)

    tags = f"#meeting/1on1 #source/embedded-voice"
    if people and people[0].get("team"):
        tags += f" #team/{people[0]['team'].lower().replace(' ', '-')}"

    lines = [
        f"### {date_str} - {category}",
        f"*Embedded Voice Memo - {time_str}* {tags}",
    ]
    if people:
        linked_names = ", ".join(f"[[{p['name']}]]" for p in people)
        lines.append(f"**People:** {linked_names}")
    lines.append("")

    if summary:
        lines.append(summary.strip())
        lines.append("")

    if transcription:
        lines.append("<details><summary>Full Transcription</summary>")
        lines.append("")
        lines.append(transcription.strip())
        lines.append("")
        lines.append("</details>")
        lines.append("")

    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def format_standalone_meeting(memo: dict, people: list[dict]) -> str:
    """Format a standalone meeting file with [[wiki-links]] to people."""
    dt = _parse_date(memo.get("created_at"))
    date_str = dt.strftime("%Y-%m-%d") if dt else "undated"
    category = memo.get("category", "Other")
    tags = _build_tags(memo)
    people_names = [p["name"] for p in people]

    fm = _frontmatter({
        "title": memo.get("summary", category)[:80].replace("\n", " ").strip() or category,
        "date": date_str,
        "category": category,
        "source": "embedded-voice-memo",
        "memo_id": memo.get("memo_id", ""),
        "tags": tags,
        "people": people_names or None,
    })

    parts = [fm, ""]

    # People links for graph view
    if people:
        linked = " · ".join(f"[[{p['name']}]]" for p in people)
        parts += [f"**People:** {linked}", ""]

    if memo.get("summary"):
        parts += ["## Summary", "", memo["summary"].strip(), ""]
    if memo.get("transcription"):
        parts += ["## Transcription", "", memo["transcription"].strip(), ""]

    return "\n".join(parts)


def format_idea(memo: dict) -> str:
    """Format an idea file (article-spark style)."""
    dt = _parse_date(memo.get("created_at"))
    date_str = dt.strftime("%Y-%m-%d") if dt else "undated"
    title = memo.get("summary", "")[:60].replace("\n", " ").strip() or "Voice Memo Idea"
    tags = _build_tags(memo, ["idea"])

    fm = _frontmatter({
        "title": title,
        "source": "embedded-voice-memo",
        "date": date_str,
        "tags": tags,
        "categories": ["idea"],
        "type": "voice-memo-idea",
        "memo_id": memo.get("memo_id", ""),
    })

    parts = [fm, "", f"# {title}", ""]
    parts += [f"> **Source:** Embedded Voice Memo", f"> **Date Captured:** {date_str}", "", "---", ""]
    if memo.get("summary"):
        parts += ["## Summary", "", memo["summary"].strip(), ""]
    if memo.get("transcription"):
        parts += ["## Transcription", "", memo["transcription"].strip(), ""]

    return "\n".join(parts)


def format_budget(memo: dict) -> str:
    """Format a budget note."""
    dt = _parse_date(memo.get("created_at"))
    date_str = dt.strftime("%Y-%m-%d") if dt else "undated"
    title = memo.get("summary", "")[:60].replace("\n", " ").strip() or "Budget Note"
    tags = _build_tags(memo, ["budget", "forecast"])

    fm = _frontmatter({
        "title": title,
        "source": "embedded-voice-memo",
        "date": date_str,
        "tags": tags,
        "category": "Budget",
        "memo_id": memo.get("memo_id", ""),
    })

    parts = [fm, "", f"# {title}", ""]
    parts += [f"> **Source:** Embedded Voice Memo", f"> **Date Captured:** {date_str}", "", "---", ""]
    if memo.get("summary"):
        parts += ["## Summary", "", memo["summary"].strip(), ""]
    if memo.get("transcription"):
        parts += ["## Transcription", "", memo["transcription"].strip(), ""]

    return "\n".join(parts)


def format_todo(memo: dict, max_items: int = 10) -> str:
    """Format a ToDo file with extracted action items."""
    dt = _parse_date(memo.get("created_at"))
    date_str = dt.strftime("%Y-%m-%d") if dt else "undated"
    tags = _build_tags(memo, ["todo"])

    fm = _frontmatter({
        "title": f"Voice ToDo - {date_str}",
        "date": date_str,
        "category": "ToDo",
        "source": "embedded-voice-memo",
        "memo_id": memo.get("memo_id", ""),
        "tags": tags,
    })

    # Extract action items from summary
    items = _extract_action_items(memo.get("summary", ""), max_items)

    parts = [fm, "", "## Action Items", ""]
    if items:
        for item in items:
            parts.append(f"- [ ] {item}")
    else:
        parts.append("- [ ] (review transcription for action items)")
    parts.append("")

    parts += ["## Context", ""]
    if memo.get("summary"):
        parts += [memo["summary"].strip(), ""]
    if memo.get("transcription"):
        parts += [
            "<details><summary>Full Transcription</summary>",
            "", memo["transcription"].strip(), "",
            "</details>", "",
        ]

    return "\n".join(parts)


def format_other(memo: dict) -> str:
    """Format a general voice memo file."""
    dt = _parse_date(memo.get("created_at"))
    date_str = dt.strftime("%Y-%m-%d") if dt else "undated"
    category = memo.get("category", "Other")
    tags = _build_tags(memo)

    fm = _frontmatter({
        "title": memo.get("summary", "")[:60].replace("\n", " ").strip() or f"Voice Memo - {category}",
        "date": date_str,
        "category": category,
        "source": "embedded-voice-memo",
        "memo_id": memo.get("memo_id", ""),
        "tags": tags,
    })

    parts = [fm, ""]
    if memo.get("summary"):
        parts += ["## Summary", "", memo["summary"].strip(), ""]
    if memo.get("transcription"):
        parts += ["## Transcription", "", memo["transcription"].strip(), ""]

    return "\n".join(parts)


def _extract_action_items(text: str, max_items: int = 10) -> list[str]:
    """Extract action items from an AI summary.

    Looks for explicit 'Action Items' or 'Next Steps' sections.
    """
    if not text:
        return []

    # Find the action items section
    patterns = [
        r"\*?\*?Action Items\*?\*?:?",
        r"\*?\*?Next Steps\*?\*?:?",
        r"## Action Items",
        r"## Next Steps",
    ]
    start_idx = -1
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            start_idx = m.end()
            break

    if start_idx == -1:
        return []

    # Parse bullet items until next section
    items = []
    for line in text[start_idx:].split("\n"):
        line = line.strip()

        # Stop at next heading or bold section header
        if line.startswith("#") or (line.startswith("**") and line.endswith("**")):
            break

        # Match bullet patterns
        m = re.match(r"^[-•*]\s*(?:\[.\]\s*)?(.*)", line)
        if m:
            item = m.group(1).strip()
            if len(item) > 10:
                items.append(item)
                if len(items) >= max_items:
                    break

    return items


# -------------------------------------------------------------------
# File writing
# -------------------------------------------------------------------

def write_file(path: Path, content: str, execute: bool) -> bool:
    """Write content to a file. Returns True if written."""
    if not execute:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def append_to_person_file(
    person: dict,
    entry_text: str,
    memo: dict,
    vault: Path,
    execute: bool,
) -> Path | None:
    """Append a meeting entry to a person's 1:1 file.

    Creates the file from template if it doesn't exist.
    Normalizes the file before and after insertion.
    """
    vault_path = person.get("vault_path", "")
    if not vault_path:
        return None

    file_path = vault / vault_path

    if not file_path.exists():
        if not execute:
            return file_path

        # Create from template
        file_path.parent.mkdir(parents=True, exist_ok=True)
        template = (
            f"---\nperson: \"{person['name']}\"\n"
            f"team: \"{person.get('team', '')}\"\n"
            f"role: \"{person.get('role', '')}\"\n"
            f"last_1on1:\n---\n\n"
            f"# {person['name']}\n\n"
            f"## Current Focus\n-\n\n"
            f"## Action Items\n- [ ] \n\n---\n\n"
            f"## Meeting Notes\n\n---\n\n"
            f"## Rapport\n#rapport\n\n"
            f"> [!note]- Personal Details (click to expand)\n> -\n"
        )
        file_path.write_text(template, encoding="utf-8")

    if not execute:
        return file_path

    # Read, normalize, insert
    content = file_path.read_text(encoding="utf-8")
    content = normalize_person_file(content)

    # Update last_1on1 in frontmatter
    dt = _parse_date(memo.get("created_at"))
    if dt:
        date_str = dt.strftime("%Y-%m-%d")
        content = re.sub(
            r"(last_1on1:).*",
            f"\\1 {date_str}",
            content,
        )

    # Insert after ## Meeting Notes
    marker = "## Meeting Notes"
    idx = content.find(marker)
    if idx != -1:
        insert_pos = idx + len(marker)
        # Skip to end of that line
        nl = content.find("\n", insert_pos)
        if nl != -1:
            content = content[:nl + 1] + "\n" + entry_text + content[nl + 1:]

    file_path.write_text(content, encoding="utf-8")
    return file_path


# -------------------------------------------------------------------
# Routing
# -------------------------------------------------------------------

def route_memo(
    memo: dict,
    config: dict,
    by_name: dict,
    by_nickname: dict,
    me_name: str,
    execute: bool,
) -> tuple[str, str]:
    """Route a single memo. Returns (action, destination)."""
    vault = config["_vault"]
    folders = config["_folders"]
    category = memo.get("category", "Other")
    text = f"{memo.get('summary', '')} {memo.get('transcription', '')}"
    people = detect_people(text, by_name, by_nickname, me_name)

    dt = _parse_date(memo.get("created_at"))
    date_str = dt.strftime("%Y-%m-%d") if dt else "undated"
    short_id = memo.get("memo_id", "unknown")[:8]
    cat_slug = category.lower().replace(" ", "-")

    if category in ("Meeting", "People"):
        # Try to route to a person's 1:1 file
        non_me = [p for p in people if p["name"].lower() != me_name]
        if len(non_me) == 1 and non_me[0].get("vault_path"):
            person = non_me[0]
            entry = format_1on1_entry(memo, non_me)
            path = append_to_person_file(person, entry, memo, vault, execute)
            return "append_1on1", str(path) if path else person["name"]

        # Standalone meeting file
        content = format_standalone_meeting(memo, people)
        filename = _sanitize_filename(f"{date_str}-{cat_slug}-{short_id}.md")
        path = folders.get("meetings", vault / "02_Voice_Memos/Meetings") / filename
        write_file(path, content, execute)
        return "create_meeting", str(path)

    elif category == "Idea":
        content = format_idea(memo)
        filename = _sanitize_filename(f"{date_str}-idea-{short_id}.md")
        path = folders.get("ideas", vault / "04_Resources/Ideas") / filename
        write_file(path, content, execute)
        return "create_idea", str(path)

    elif category == "Budget":
        content = format_budget(memo)
        filename = _sanitize_filename(f"{date_str}-budget-{short_id}.md")
        path = folders.get("budget", vault / "04_Resources/Budget") / filename
        write_file(path, content, execute)
        return "create_budget", str(path)

    elif category == "ToDo":
        max_items = config.get("max_action_items", 10)
        content = format_todo(memo, max_items)
        filename = _sanitize_filename(f"{date_str}-todo-{short_id}.md")
        path = folders.get("inbox", vault / "00_Inbox") / filename
        write_file(path, content, execute)
        return "create_todo", str(path)

    else:
        content = format_other(memo)
        filename = _sanitize_filename(f"{date_str}-{cat_slug}-{short_id}.md")
        path = folders.get("general", vault / "02_Voice_Memos/General") / filename
        write_file(path, content, execute)
        return "create_other", str(path)


# -------------------------------------------------------------------
# Dedup & incremental
# -------------------------------------------------------------------

def load_ingested(vault: Path) -> set[str]:
    log = vault / ".embedded_ingested.txt"
    if log.exists():
        return set(log.read_text(encoding="utf-8").strip().splitlines())
    return set()


def save_ingested(vault: Path, memo_ids: set[str]):
    log = vault / ".embedded_ingested.txt"
    existing = load_ingested(vault)
    all_ids = existing | memo_ids
    log.write_text("\n".join(sorted(all_ids)) + "\n", encoding="utf-8")


def read_last_sync() -> str | None:
    marker = SCRIPT_DIR / ".embedded_last_sync"
    if marker.exists():
        return marker.read_text(encoding="utf-8").strip() or None
    return None


def write_last_sync(timestamp: str):
    marker = SCRIPT_DIR / ".embedded_last_sync"
    marker.write_text(timestamp + "\n", encoding="utf-8")


# -------------------------------------------------------------------
# CLI
# -------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Embedded Smart Vault — ingest voice memos into Obsidian.",
    )
    parser.add_argument("--email", required=True, help="Your Embedded account email")
    parser.add_argument("--execute", action="store_true", help="Write files (default is dry run)")
    parser.add_argument("--incremental", action="store_true", help="Only fetch new memos since last run")
    parser.add_argument("--category", help="Filter by category")
    parser.add_argument("--memo-id", help="Process a single memo by ID")
    args = parser.parse_args()

    config = load_config()
    vault = config["_vault"]
    people, by_name, by_nickname, me_name = load_people(config)

    print(f"Vault: {vault}")
    print(f"People loaded: {len(people)}")
    if not args.execute:
        print("Mode: DRY RUN (pass --execute to write files)\n")
    else:
        print("Mode: EXECUTE\n")

    # Authenticate
    password = getpass.getpass("Embedded password: ")
    client = EmbeddedClient()
    try:
        print(f"Signing in as {args.email}...")
        client.login(args.email, password)
        print("Authenticated.\n")
    except AuthError as e:
        print(e)
        sys.exit(1)

    # Determine time window
    since = None
    if args.incremental:
        since = read_last_sync()
        if since:
            print(f"Incremental: fetching memos after {since}")
        else:
            print("No previous sync, fetching all memos.")

    # Fetch memos
    try:
        print("Fetching memos...")
        if args.memo_id:
            # Fetch all then filter client-side
            all_memos = client.get_memos(since=since, category=args.category)
            memos = [m for m in all_memos if m["memo_id"] == args.memo_id]
        else:
            memos = client.get_memos(since=since, category=args.category)
        print(f"Found {len(memos)} memo(s)\n")
    except (AuthError, APIError) as e:
        print(e)
        sys.exit(1)

    if not memos:
        print("Nothing to ingest.")
        return

    # Dedup
    ingested = load_ingested(vault)
    new_memos = [m for m in memos if m["memo_id"] not in ingested]
    if len(new_memos) < len(memos):
        print(f"Skipping {len(memos) - len(new_memos)} already-ingested memo(s)")

    if not new_memos:
        print("All memos already ingested.")
        return

    # Route each memo
    results = {"written": 0, "skipped": 0, "failed": 0}
    new_ids = set()

    for memo in new_memos:
        try:
            action, dest = route_memo(memo, config, by_name, by_nickname, me_name, args.execute)
            dt = _parse_date(memo.get("created_at"))
            date_label = dt.strftime("%Y-%m-%d") if dt else "undated"
            prefix = "  ->" if args.execute else "  [dry-run]"
            print(f"{prefix} {date_label} | {memo['category']:12s} | {action:16s} | {Path(dest).name}")
            results["written"] += 1
            new_ids.add(memo["memo_id"])
        except Exception as e:
            print(f"  [ERROR] {memo['memo_id'][:8]}: {e}")
            results["failed"] += 1

    # Save state
    if args.execute and new_ids:
        save_ingested(vault, new_ids)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        write_last_sync(now)

    print(f"\nResults: {results['written']} processed, {results['failed']} failed")
    if not args.execute:
        print("(dry run — pass --execute to write files)")


if __name__ == "__main__":
    main()
