#!/usr/bin/env python3
"""
Example: search your memos by keyword across transcriptions and summaries.

This runs client-side after fetching your data. For semantic (AI) search,
use the embeddings — see the embedding_search.py example.
"""

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from graymatter import GrayMatterClient

email = input("Email: ")
password = getpass.getpass("Password: ")
query = input("Search for: ").lower()

client = GrayMatterClient()
client.login(email, password)

memos = client.get_memos()
matches = []
for memo in memos:
    text = f"{memo['summary']} {memo['transcription']}".lower()
    if query in text:
        matches.append(memo)

print(f"\nFound {len(matches)} memo(s) matching '{query}':\n")
for memo in matches:
    date = memo["created_at"][:10] if memo["created_at"] else "undated"
    summary = (memo["summary"] or "")[:100].replace("\n", " ")
    print(f"  {date} | {memo['category']:12s} | {memo['memo_id'][:8]}")
    print(f"    {summary}...\n")
