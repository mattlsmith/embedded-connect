#!/usr/bin/env python3
"""
Embedded → JSON Connector

Exports your voice memos as JSON files — useful as a starting point for
building custom integrations, importing into other tools, or backing up
your data.

Usage:
    python export.py --email you@example.com --output my_memos.json
    python export.py --email you@example.com --output memos.json --category Meeting
    python export.py --email you@example.com --output memos.json --include-embeddings
"""

import argparse
import getpass
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from embedded import EmbeddedClient, AuthError, APIError


def main():
    parser = argparse.ArgumentParser(
        description="Export Embedded voice memos to JSON.",
    )
    parser.add_argument("--email", required=True, help="Your Embedded account email")
    parser.add_argument("--output", required=True, help="Output JSON file path")
    parser.add_argument("--category", help="Filter by category (Meeting, Idea, ToDo, etc.)")
    parser.add_argument("--since", help="ISO timestamp — only memos after this date")
    parser.add_argument("--include-embeddings", action="store_true", help="Include 3072-dim embedding vectors")
    parser.add_argument("--raw-chunks", action="store_true", help="Export raw chunks instead of stitched memos")
    args = parser.parse_args()

    password = getpass.getpass("Embedded password: ")

    client = EmbeddedClient()
    try:
        print(f"Signing in as {args.email}...")
        client.login(args.email, password)
        print("Authenticated successfully.")
    except AuthError as e:
        print(e)
        sys.exit(1)

    try:
        print("Fetching your memos...")
        if args.raw_chunks:
            data = client.get_raw_chunks(
                since=args.since,
                category=args.category,
                include_embeddings=args.include_embeddings,
            )
            print(f"Found {len(data)} chunk(s)")
        else:
            data = client.get_memos(
                since=args.since,
                category=args.category,
                include_embeddings=args.include_embeddings,
            )
            print(f"Found {len(data)} memo(s)")
    except (AuthError, APIError) as e:
        print(e)
        sys.exit(1)

    if not data:
        print("Nothing to export.")
        return

    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Exported to {output_path}")


if __name__ == "__main__":
    main()
