#!/usr/bin/env python3
"""
Embedded Smart Vault — Setup Wizard

Sets up your Obsidian vault with the Embedded folder structure,
dashboards, templates, and people directory. Safe to run on an
existing vault — only creates folders/files that don't exist yet.

Usage:
    python setup.py
"""

import shutil
import sys
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = SCRIPT_DIR / "vault-template"
CONFIG_FILE = SCRIPT_DIR / "config.yaml"


def main():
    print("=" * 60)
    print("  Embedded Smart Vault — Setup")
    print("=" * 60)
    print()

    # 1. Get vault path
    vault_input = input("Obsidian vault path: ").strip().strip('"').strip("'")
    if not vault_input:
        print("No path provided. Exiting.")
        sys.exit(1)

    vault_path = Path(vault_input).expanduser().resolve()
    if not vault_path.exists():
        create = input(f"'{vault_path}' doesn't exist. Create it? [y/N] ").strip().lower()
        if create != "y":
            print("Exiting.")
            sys.exit(1)
        vault_path.mkdir(parents=True)

    print(f"\nVault: {vault_path}\n")

    # 2. Get user name (for self-exclusion in person detection)
    user_name = input("Your full name (excluded from person detection): ").strip()
    if not user_name:
        user_name = "Your Name"

    # 3. Copy vault template structure
    print("\nSetting up vault structure...")
    copied = 0
    skipped = 0

    for src in TEMPLATE_DIR.rglob("*"):
        rel = src.relative_to(TEMPLATE_DIR)

        # Skip people.yaml — we'll generate it separately
        if rel.name == "people.yaml":
            continue

        dest = vault_path / rel

        if src.is_dir():
            if not dest.exists():
                dest.mkdir(parents=True)
                print(f"  [created] {rel}/")
                copied += 1
            else:
                skipped += 1
        else:
            if not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
                print(f"  [created] {rel}")
                copied += 1
            else:
                print(f"  [exists]  {rel}")
                skipped += 1

    # 4. Create people.yaml in vault root if not exists
    people_dest = vault_path / "people.yaml"
    if not people_dest.exists():
        people_template = TEMPLATE_DIR / "people.yaml"
        content = people_template.read_text(encoding="utf-8")
        content = content.replace('name: "Your Name"', f'name: "{user_name}"')
        people_dest.write_text(content, encoding="utf-8")
        print(f"  [created] people.yaml")
        copied += 1
    else:
        # Update the name in existing file
        content = people_dest.read_text(encoding="utf-8")
        if 'name: "Your Name"' in content:
            content = content.replace('name: "Your Name"', f'name: "{user_name}"')
            people_dest.write_text(content, encoding="utf-8")
            print(f"  [updated] people.yaml (set your name)")
        else:
            print(f"  [exists]  people.yaml")
        skipped += 1

    # 5. Create dedup log
    dedup_log = vault_path / ".embedded_ingested.txt"
    if not dedup_log.exists():
        dedup_log.write_text("", encoding="utf-8")

    # 6. Update config.yaml with vault path
    config = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8"))
    config["vault_path"] = str(vault_path)
    config["people_file"] = str(people_dest)
    CONFIG_FILE.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False), encoding="utf-8")

    print(f"\n  {copied} created, {skipped} already existed")

    # 7. Summary
    print()
    print("=" * 60)
    print("  Setup complete!")
    print("=" * 60)
    print()
    print("Your vault structure:")
    print(f"  {vault_path}/")
    print("  ├── 00_Inbox/              (ToDo items land here)")
    print("  ├── 01_Dashboards/         (6 dashboards)")
    print("  │   ├── Action Dashboard   (tasks + stale 1:1 alerts)")
    print("  │   ├── 1on1 Dashboard     (all people, recent meetings)")
    print("  │   ├── People Network     (relationship graph + staleness)")
    print("  │   ├── Analytics          (category breakdown, timeline)")
    print("  │   ├── Rapport Dashboard  (personal details reference)")
    print("  │   ├── People Map.canvas  (visual drag-and-drop org map)")
    print("  │   └── Graph View Guide   (how to set up Obsidian graph)")
    print("  ├── 02_Voice_Memos/        (Meetings + General)")
    print("  ├── 03_People/             (1:1 person files)")
    print("  ├── 04_Resources/          (Ideas + Budget)")
    print("  ├── 99_Templates/          (Person + Weekly Review)")
    print("  └── people.yaml            (Your team directory)")
    print()
    print("Next steps:")
    print(f"  1. Edit {people_dest}")
    print("     Add your team members so memos route to the right person files")
    print()
    print("  2. Install the Dataview plugin in Obsidian")
    print("     Community Plugins → Browse → 'Dataview' → Install + Enable")
    print("     (required for all dashboards)")
    print()
    print("  3. Run the smart ingest:")
    print("     python ingest.py --email you@example.com --dry-run")
    print()
    print("  4. Open Graph View (Ctrl+G) — see 01_Dashboards/Graph View Guide.md")
    print("     for recommended filter and color settings")
    print()


if __name__ == "__main__":
    main()
