---
type: guide
---

# Graph View Setup Guide

Your vault is wired with `[[wiki-links]]` between meeting files and person files. This means Obsidian's Graph View gives you a visual map of your professional relationships.

---

## Quick Start

1. Open **Graph View** — `Ctrl+G` (Windows) / `Cmd+G` (Mac)
2. Click the **gear icon** to open filters

## Recommended Filter Settings

### People-Only Network
See just your team and their connections:

| Setting | Value |
|---------|-------|
| **Search filter** | `path:03_People OR path:02_Voice_Memos/Meetings` |
| **Tags** | (leave empty) |
| **Orphans** | Hide |
| **Arrows** | Show |

### Full Activity View
See everything — people, meetings, ideas, todos:

| Setting | Value |
|---------|-------|
| **Search filter** | `-path:99_Templates -path:01_Dashboards` |
| **Orphans** | Hide |
| **Arrows** | Show |

## Recommended Color Groups

Add these in Graph View → Settings → Groups:

| Query | Color | What it highlights |
|-------|-------|-------------------|
| `path:03_People` | Blue | Person files |
| `path:02_Voice_Memos/Meetings` | Green | Meeting files |
| `path:04_Resources/Ideas` | Yellow | Ideas |
| `path:00_Inbox` | Red | Action items / ToDos |
| `path:02_Voice_Memos/General` | Gray | General memos |

## What the Graph Tells You

- **Large nodes** = people/files with many connections (your key relationships)
- **Clusters** = people who appear in meetings together (your working groups)
- **Isolated nodes** = people you haven't connected with recently
- **Central position** = highly connected across multiple teams

## Local Graph

Right-click any person file → **Open Local Graph** to see just that person's connections — who they're mentioned with, which meetings reference them.

## Canvas Alternative

For a more structured view, open `01_Dashboards/People Map.canvas` and drag your person files onto it. You can arrange by team, draw connections, and add context cards.
