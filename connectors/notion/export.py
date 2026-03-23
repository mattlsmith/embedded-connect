#!/usr/bin/env python3
"""
Embedded → Notion Connector

Exports your voice memos as pages in a Notion database. Each memo
becomes a database entry with properties (title, category, tags, date)
and a rich page body (summary + transcription).

Setup:
    1. Create a Notion integration at https://www.notion.so/my-integrations
    2. Create a database in Notion with these columns:
       - Title (title)       — auto-created with every database
       - Category (select)   — Meeting, Idea, ToDo, People, Budget, Other
       - Tags (multi_select) — your custom tags
       - Date (date)         — memo creation date
       - Memo ID (rich_text) — for deduplication
    3. Share the database with your integration (click ··· → Connections → add your integration)
    4. Copy the database ID from the URL (the 32-char hex string before the ?v=)

Usage:
    python export.py --email you@example.com --notion-token secret_xxx --database-id abc123

    # Or use environment variables
    export NOTION_TOKEN=secret_xxx
    export NOTION_DATABASE_ID=abc123def456...
    python export.py --email you@example.com

    # Incremental sync
    python export.py --email you@example.com --incremental

    # Filter by category
    python export.py --email you@example.com --category Meeting

    # Dry run
    python export.py --email you@example.com --dry-run
"""

import argparse
import getpass
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests as http_requests

# Add repo root for shared client
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from embedded import EmbeddedClient, AuthError, APIError

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
LAST_SYNC_FILE = Path(__file__).resolve().parent / ".notion_last_sync"
DEDUP_FILE = Path(__file__).resolve().parent / ".notion_ingested.txt"

# Notion rich_text has a 2000 character limit per block
NOTION_TEXT_LIMIT = 2000


# -------------------------------------------------------------------
# Notion API
# -------------------------------------------------------------------

class NotionClient:
    """Minimal Notion API client for creating database pages."""

    def __init__(self, token: str, database_id: str):
        self.token = token
        self.database_id = database_id
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Notion-Version": NOTION_VERSION,
        }

    def verify_connection(self) -> dict:
        """Verify the integration can access the database."""
        resp = http_requests.post(
            f"{NOTION_API}/databases/{self.database_id}/query",
            headers=self.headers,
            json={"page_size": 1},
            timeout=15,
        )
        if resp.status_code == 404:
            print("Error: Database not found. Did you share it with your integration?")
            sys.exit(1)
        if resp.status_code == 401:
            print("Error: Invalid Notion token.")
            sys.exit(1)
        resp.raise_for_status()
        return resp.json()

    def create_page(self, properties: dict, children: list) -> dict:
        """Create a page in the database.

        Handles rate limiting with automatic retry.
        """
        payload = {
            "parent": {"database_id": self.database_id},
            "properties": properties,
            "children": children,
        }

        for attempt in range(3):
            resp = http_requests.post(
                f"{NOTION_API}/pages",
                headers=self.headers,
                json=payload,
                timeout=30,
            )

            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 2))
                print(f"    Rate limited, waiting {retry_after}s...")
                time.sleep(retry_after)
                continue

            if resp.status_code != 200:
                error = resp.json().get("message", resp.text[:200])
                raise APIError(f"Notion API error ({resp.status_code}): {error}")

            return resp.json()

        raise APIError("Failed after 3 retries (rate limited)")


# -------------------------------------------------------------------
# Notion content builders
# -------------------------------------------------------------------

def _rich_text(text: str, bold: bool = False, italic: bool = False) -> dict:
    """Build a Notion rich_text object."""
    rt = {
        "type": "text",
        "text": {"content": text[:NOTION_TEXT_LIMIT]},
    }
    if bold or italic:
        rt["annotations"] = {"bold": bold, "italic": italic}
    return rt


def _split_text_blocks(text: str, block_type: str = "paragraph") -> list[dict]:
    """Split long text into multiple Notion blocks (2000 char limit each)."""
    if not text:
        return []

    blocks = []
    for i in range(0, len(text), NOTION_TEXT_LIMIT):
        chunk = text[i : i + NOTION_TEXT_LIMIT]
        blocks.append({
            "object": "block",
            "type": block_type,
            block_type: {
                "rich_text": [_rich_text(chunk)],
            },
        })
    return blocks


def _heading_block(text: str, level: int = 2) -> dict:
    """Build a Notion heading block."""
    block_type = f"heading_{level}"
    return {
        "object": "block",
        "type": block_type,
        block_type: {
            "rich_text": [_rich_text(text)],
        },
    }


def _toggle_block(title: str, content_text: str) -> list[dict]:
    """Build a toggleable (collapsible) section.

    Due to API limitations, we create a toggle heading followed by
    content blocks. The toggle contains the first chunk of text,
    and additional chunks follow as indented paragraphs.
    """
    if not content_text:
        return []

    # Notion toggle blocks can have children (nested content)
    children = _split_text_blocks(content_text)

    return [{
        "object": "block",
        "type": "toggle",
        "toggle": {
            "rich_text": [_rich_text(title, bold=True)],
            "children": children,
        },
    }]


def _divider_block() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}


def _bullet_block(text: str) -> dict:
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {
            "rich_text": [_rich_text(text)],
        },
    }


def _todo_block(text: str, checked: bool = False) -> dict:
    return {
        "object": "block",
        "type": "to_do",
        "to_do": {
            "rich_text": [_rich_text(text)],
            "checked": checked,
        },
    }


def memo_to_notion(memo: dict) -> tuple[dict, list]:
    """Convert a memo to Notion properties + children blocks.

    Returns (properties_dict, children_blocks_list).
    """
    memo_id = memo.get("memo_id", "unknown")
    category = memo.get("category", "Other")
    summary = memo.get("summary", "")
    transcription = memo.get("transcription", "")
    date_str = memo.get("created_at", "")[:10] or None
    chunk_count = memo.get("chunk_count", 1)

    # Build title
    title_hint = summary[:60].replace("\n", " ").strip() if summary else category
    title = f"Voice Memo – {title_hint}"

    # Parse tags
    tags = []
    raw_tags = memo.get("tags", "")
    if raw_tags:
        for t in str(raw_tags).split(","):
            t = t.strip()
            if t:
                tags.append(t)

    # Properties
    properties = {
        "Title": {
            "title": [_rich_text(title)],
        },
        "Category": {
            "select": {"name": category},
        },
        "Memo ID": {
            "rich_text": [_rich_text(memo_id)],
        },
    }

    if tags:
        properties["Tags"] = {
            "multi_select": [{"name": t} for t in tags[:10]],  # Notion limit
        }

    if date_str:
        properties["Date"] = {
            "date": {"start": date_str},
        }

    # Page body (children blocks)
    children = []

    # Metadata callout
    meta_parts = [f"Category: {category}"]
    if chunk_count > 1:
        meta_parts.append(f"Chunks: {chunk_count}")
    if memo.get("audio_file_name"):
        meta_parts.append(f"Audio: {memo['audio_file_name']}")

    children.append({
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": [_rich_text(" | ".join(meta_parts))],
            "icon": {"type": "emoji", "emoji": "🎙️"},
        },
    })

    children.append(_divider_block())

    # Summary section
    if summary:
        children.append(_heading_block("Summary"))

        # If it's a ToDo, try to extract action items
        if category == "ToDo":
            items, remaining = _extract_todos_and_rest(summary)
            for item in items:
                children.append(_todo_block(item))
            if remaining:
                children.extend(_split_text_blocks(remaining))
        else:
            children.extend(_split_text_blocks(summary))

    # Transcription as collapsible toggle
    if transcription:
        children.append(_divider_block())
        children.extend(_toggle_block("Full Transcription", transcription))

    # Cap at 100 blocks (Notion API limit per request)
    return properties, children[:100]


def _extract_todos_and_rest(text: str) -> tuple[list[str], str]:
    """Extract action items from summary text for ToDo memos."""
    import re

    lines = text.split("\n")
    items = []
    rest_lines = []
    in_actions = False

    for line in lines:
        stripped = line.strip()

        # Detect action items section
        if re.match(r"\*?\*?Action Items\*?\*?:?", stripped, re.IGNORECASE):
            in_actions = True
            continue
        if re.match(r"\*?\*?Next Steps\*?\*?:?", stripped, re.IGNORECASE):
            in_actions = True
            continue

        # Stop action items at next section
        if in_actions and (stripped.startswith("#") or (stripped.startswith("**") and stripped.endswith("**"))):
            in_actions = False

        if in_actions:
            m = re.match(r"^[-•*]\s*(?:\[.\]\s*)?(.*)", stripped)
            if m and len(m.group(1).strip()) > 5:
                items.append(m.group(1).strip())
                continue

        rest_lines.append(line)

    return items[:10], "\n".join(rest_lines).strip()


# -------------------------------------------------------------------
# Dedup & incremental
# -------------------------------------------------------------------

def load_ingested() -> set[str]:
    if DEDUP_FILE.exists():
        return set(DEDUP_FILE.read_text(encoding="utf-8").strip().splitlines())
    return set()


def save_ingested(memo_ids: set[str]):
    existing = load_ingested()
    all_ids = existing | memo_ids
    DEDUP_FILE.write_text("\n".join(sorted(all_ids)) + "\n", encoding="utf-8")


def read_last_sync() -> str | None:
    if LAST_SYNC_FILE.exists():
        return LAST_SYNC_FILE.read_text(encoding="utf-8").strip() or None
    return None


def write_last_sync(ts: str):
    LAST_SYNC_FILE.write_text(ts + "\n", encoding="utf-8")


# -------------------------------------------------------------------
# CLI
# -------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Export Embedded voice memos to a Notion database.",
    )
    parser.add_argument("--email", required=True, help="Your Embedded account email")
    parser.add_argument("--notion-token", default=os.getenv("NOTION_TOKEN"),
                        help="Notion integration token (or set NOTION_TOKEN env var)")
    parser.add_argument("--database-id", default=os.getenv("NOTION_DATABASE_ID"),
                        help="Notion database ID (or set NOTION_DATABASE_ID env var)")
    parser.add_argument("--incremental", action="store_true", help="Only sync new memos since last run")
    parser.add_argument("--category", help="Filter by category")
    parser.add_argument("--dry-run", action="store_true", help="Preview without creating pages")
    args = parser.parse_args()

    if not args.notion_token:
        print("Error: Notion token required. Pass --notion-token or set NOTION_TOKEN env var.")
        print("\nTo create one: https://www.notion.so/my-integrations")
        sys.exit(1)
    if not args.database_id:
        print("Error: Database ID required. Pass --database-id or set NOTION_DATABASE_ID env var.")
        print("\nCopy it from your Notion database URL (32-char hex string).")
        sys.exit(1)

    # Connect to Notion
    notion = NotionClient(args.notion_token, args.database_id)
    if not args.dry_run:
        print("Verifying Notion connection...")
        notion.verify_connection()
        print("Notion database connected.\n")

    # Authenticate with Embedded
    password = getpass.getpass("Embedded password: ")
    client = EmbeddedClient()
    try:
        print(f"Signing in as {args.email}...")
        client.login(args.email, password)
        print("Authenticated.\n")
    except AuthError as e:
        print(e)
        sys.exit(1)

    # Incremental
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
        memos = client.get_memos(since=since, category=args.category)
        print(f"Found {len(memos)} memo(s)\n")
    except (AuthError, APIError) as e:
        print(e)
        sys.exit(1)

    if not memos:
        print("Nothing to export.")
        return

    # Dedup
    ingested = load_ingested()
    new_memos = [m for m in memos if m["memo_id"] not in ingested]
    if len(new_memos) < len(memos):
        print(f"Skipping {len(memos) - len(new_memos)} already-synced memo(s)")

    if not new_memos:
        print("All memos already in Notion.")
        return

    # Create pages
    created = 0
    failed = 0
    new_ids = set()

    for memo in new_memos:
        date = memo.get("created_at", "")[:10] or "undated"
        cat = memo.get("category", "Other")
        short_id = memo.get("memo_id", "")[:8]

        if args.dry_run:
            print(f"  [dry-run] {date} | {cat:12s} | {short_id}...")
            created += 1
            continue

        try:
            properties, children = memo_to_notion(memo)
            notion.create_page(properties, children)
            print(f"  -> {date} | {cat:12s} | {short_id}...")
            new_ids.add(memo["memo_id"])
            created += 1

            # Respect rate limits (3 req/s max)
            time.sleep(0.35)

        except Exception as e:
            print(f"  [ERROR] {short_id}: {e}")
            failed += 1

    # Save state
    if not args.dry_run and new_ids:
        save_ingested(new_ids)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        write_last_sync(now)

    print(f"\nResults: {created} created, {failed} failed")
    if args.dry_run:
        print("(dry run — remove --dry-run to create pages)")


if __name__ == "__main__":
    main()
