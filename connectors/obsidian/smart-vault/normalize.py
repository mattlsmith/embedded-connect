"""
Person file normalizer — ensures canonical section ordering.

Structure enforced:
    ---
    [frontmatter]
    ---
    # Name
    [subtitle/preamble]
    ## Current Focus
    ## Action Items        ← always above Meeting Notes
    ## Meeting Notes       ← meetings sorted newest-first
    ## Rapport             ← always at bottom

Safe to run repeatedly (idempotent).
"""

import re
from pathlib import Path

# Regex for meeting date headers: ### YYYY-MM-DD ...
MEETING_DATE_RE = re.compile(r"^###\s+(\d{4}-\d{2}-\d{2})")


def normalize_person_file(content: str) -> str:
    """Reorder a person file into canonical section order.

    Returns the normalized content string. Does not write to disk.
    """
    # 1. Extract frontmatter
    frontmatter = ""
    body = content
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            frontmatter = content[: end + 3]
            body = content[end + 3 :]

    # 2. Parse body into sections
    lines = body.split("\n")

    h1_block = []  # Everything before the first ## heading
    sections = {}  # heading -> content lines
    current_heading = None
    current_lines = []

    for line in lines:
        if line.startswith("## "):
            # Save previous section
            if current_heading:
                sections[current_heading] = current_lines
            elif h1_block or current_lines:
                h1_block = current_lines

            current_heading = line.strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    # Save last section
    if current_heading:
        sections[current_heading] = current_lines
    elif current_lines:
        h1_block = current_lines

    # 3. Ensure required sections exist
    if not any(h.startswith("## Action Items") for h in sections):
        sections["## Action Items"] = ["## Action Items", "- [ ] ", ""]

    if not any(h.startswith("## Meeting Notes") for h in sections):
        sections["## Meeting Notes"] = ["## Meeting Notes", ""]

    # 4. Sort meetings within Meeting Notes (newest first)
    meeting_key = next(
        (h for h in sections if h.startswith("## Meeting Notes")), None
    )
    if meeting_key:
        sections[meeting_key] = _sort_meetings(sections[meeting_key])

    # 5. Reassemble in canonical order
    ordered_headings = [
        "## Current Focus",
        "## Action Items",
        "## Meeting Notes",
        "## Rapport",
    ]

    result_parts = []
    if frontmatter:
        result_parts.append(frontmatter)

    # H1 block (name, subtitle, preamble)
    h1_text = "\n".join(h1_block).strip()
    if h1_text:
        result_parts.append(h1_text)

    # Ordered sections
    used = set()
    for target in ordered_headings:
        match = next((h for h in sections if h.startswith(target)), None)
        if match:
            result_parts.append("\n".join(sections[match]).strip())
            used.add(match)

    # Any remaining sections (preserve user-added sections)
    for heading, lines_list in sections.items():
        if heading not in used:
            result_parts.append("\n".join(lines_list).strip())

    return "\n\n".join(result_parts) + "\n"


def _sort_meetings(lines: list[str]) -> list[str]:
    """Sort ### meeting entries within Meeting Notes by date, newest first."""
    header = []
    meetings = []
    current_meeting = []
    current_date = ""

    for line in lines:
        m = MEETING_DATE_RE.match(line)
        if m:
            if current_meeting:
                meetings.append((current_date, current_meeting))
            current_date = m.group(1)
            current_meeting = [line]
        elif not meetings and not current_meeting:
            # Lines before any ### meeting header
            if line.startswith("## Meeting Notes"):
                header.append(line)
            else:
                header.append(line)
        else:
            current_meeting.append(line)

    if current_meeting:
        meetings.append((current_date, current_meeting))

    # Sort newest first
    meetings.sort(key=lambda x: x[0], reverse=True)

    result = list(header)
    for _date, meeting_lines in meetings:
        result.extend(meeting_lines)

    return result
