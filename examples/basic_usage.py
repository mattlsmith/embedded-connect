#!/usr/bin/env python3
"""
Basic example: fetch and print your Gray Matter voice memos.
"""

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from graymatter import GrayMatterClient

email = input("Email: ")
password = getpass.getpass("Password: ")

client = GrayMatterClient()
client.login(email, password)
print(f"Logged in as {client.email} (uid: {client.uid})\n")

memos = client.get_memos()
print(f"You have {len(memos)} memo(s):\n")

for memo in memos:
    date = memo["created_at"][:10] if memo["created_at"] else "undated"
    summary_preview = (memo["summary"] or "No summary")[:80].replace("\n", " ")
    print(f"  {date} | {memo['category']:12s} | {summary_preview}")
