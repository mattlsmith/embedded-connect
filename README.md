# Embedded Connect

Open-source connectors for [Embedded](https://github.com/mattlsmith/embedded) — the AI-powered voice memo app. Export your transcriptions, summaries, tags, and embeddings to the tools you already use.

## Quick Start

```bash
git clone https://github.com/mattlsmith/embedded-connect.git
cd embedded-connect
pip install -r requirements.txt
```

### Export to Obsidian

```bash
python connectors/obsidian/export.py --email you@example.com --vault-path ~/Obsidian/Vault/VoiceMemos
```

### Export to JSON

```bash
python connectors/json-export/export.py --email you@example.com --output my_memos.json
```

### Use the Python SDK

```python
from embedded import EmbeddedClient

client = EmbeddedClient()
client.login("you@example.com", "your-password")

memos = client.get_memos()
for memo in memos:
    print(memo["category"], memo["summary"][:80])
```

## Authentication

All you need is your **Embedded account email and password** — the same credentials you use in the iOS app. No API keys or tokens to manage.

Your data is fetched through a secure API that verifies your identity and returns **only your memos**. Other users' data is never accessible.

## Available Connectors

| Connector | Description | Path |
|-----------|-------------|------|
| **Obsidian (Simple)** | Markdown files with YAML frontmatter, organized by month | `connectors/obsidian/export.py` |
| **Obsidian (Smart Vault)** | Full vault system with dashboards, person routing, 1:1 files | `connectors/obsidian/smart-vault/` |
| **Notion** | Database pages with properties, rich content, collapsible transcripts | `connectors/notion/` |
| **JSON Export** | Full data dump as JSON — great for custom integrations | `connectors/json-export/` |

---

## Notion Connector

Syncs your voice memos to a Notion database. Each memo becomes a page with structured properties and rich content.

### Setup

1. **Create a Notion integration** at [notion.so/my-integrations](https://www.notion.so/my-integrations)
2. **Create a database** in Notion with these columns:

   | Column | Type | Purpose |
   |--------|------|---------|
   | Title | Title | Memo title (auto-created) |
   | Category | Select | Meeting, Idea, ToDo, etc. |
   | Tags | Multi-select | Your custom tags |
   | Date | Date | Memo creation date |
   | Memo ID | Rich text | For deduplication |

3. **Share the database** with your integration (click `···` → Connections → add your integration)
4. **Copy the database ID** from the URL (the 32-char hex string)

### Usage

```bash
# Set credentials (or pass as CLI flags)
export NOTION_TOKEN=secret_xxx
export NOTION_DATABASE_ID=abc123def456...

# Dry run
python connectors/notion/export.py --email you@example.com --dry-run

# Export all memos
python connectors/notion/export.py --email you@example.com

# Incremental sync
python connectors/notion/export.py --email you@example.com --incremental

# Filter by category
python connectors/notion/export.py --email you@example.com --category Meeting
```

### What You Get

Each Notion page includes:
- **Properties:** Title, Category (select), Tags (multi-select), Date, Memo ID
- **Callout block** with metadata (category, chunk count, audio file)
- **Summary section** (for ToDo memos, action items become interactive checkboxes)
- **Collapsible transcription** (toggle block — click to expand)
- **Deduplication** — never creates duplicate pages
- **Rate limit handling** — automatic retry with backoff

---

## Smart Vault — Obsidian Power Setup

A complete Obsidian knowledge management system that automatically routes your voice memos to the right place, manages 1:1 files for your team, and provides live dashboards.

### What You Get

- **Auto-routing** — Meetings go to person 1:1 files, ideas to an Ideas folder, ToDos to your inbox with checkboxes
- **Person detection** — Mentions of people in your memos are matched to their 1:1 file
- **1:1 file management** — Each person gets a structured file with Action Items, Meeting Notes (newest-first), and Rapport sections
- **Dataview dashboards** — Action Dashboard, 1:1 Dashboard, and Rapport Dashboard that auto-aggregate from your vault
- **File normalization** — Person files maintain canonical section ordering, safe to run repeatedly
- **Incremental sync** — Only fetches new memos since last run
- **Deduplication** — Never ingests the same memo twice

### Quick Start

```bash
# 1. Set up your vault structure
cd connectors/obsidian/smart-vault
python setup.py

# 2. Edit people.yaml in your vault — add your team
# 3. Install the Dataview plugin in Obsidian

# 4. Dry run (preview routing without writing)
python ingest.py --email you@example.com --dry-run

# 5. Execute
python ingest.py --email you@example.com --execute

# 6. Incremental sync (subsequent runs)
python ingest.py --email you@example.com --execute --incremental
```

### Vault Structure

```
your-vault/
├── 00_Inbox/              ← ToDo items with checkboxes
├── 01_Dashboards/
│   ├── Action Dashboard   ← Aggregates all open tasks
│   ├── 1on1 Dashboard     ← Recent meetings, all people
│   └── Rapport Dashboard  ← Personal details reference
├── 02_Voice_Memos/
│   ├── Meetings/          ← Standalone meeting files
│   └── General/           ← Other/uncategorized memos
├── 03_People/
│   └── {Team}/
│       └── Person Name.md ← 1:1 file (auto-created)
├── 04_Resources/
│   ├── Ideas/             ← Idea memos (article-spark format)
│   └── Budget/            ← Budget/forecast notes
├── 99_Templates/
│   └── Template - 1on1 Person.md
└── people.yaml            ← Your team directory
```

### Routing Logic

| Category | Destination | Behavior |
|----------|-------------|----------|
| **Meeting / People** | Person 1:1 file | Appends to `## Meeting Notes` if one person detected |
| **Meeting / People** | `02_Voice_Memos/Meetings/` | Creates standalone file if no person or multiple people |
| **Idea** | `04_Resources/Ideas/` | Article-spark format with summary + transcription |
| **Budget** | `04_Resources/Budget/` | Budget note format |
| **ToDo** | `00_Inbox/` | Extracts action items as `- [ ]` checkboxes |
| **Other** | `02_Voice_Memos/General/` | General memo format |

### People Directory (`people.yaml`)

Define your team so the pipeline can route memos to the right person:

```yaml
me:
  name: "Your Name"

people:
  - name: "Jane Doe"
    nickname: ["jane"]
    team: "Engineering"
    role: "Senior Engineer"
    vault_path: "03_People/Engineering/Jane Doe.md"

  - name: "Bob Wilson"
    nickname: ["bob"]
    team: "Design"
    role: "Lead Designer"
    vault_path: "03_People/Design/Bob Wilson.md"
```

### Configuration (`config.yaml`)

Customize folder paths, routing, and behavior:

```yaml
vault_path: "/path/to/your/vault"

folders:
  inbox: "00_Inbox"
  meetings: "02_Voice_Memos/Meetings"
  general: "02_Voice_Memos/General"
  people: "03_People"
  ideas: "04_Resources/Ideas"
  budget: "04_Resources/Budget"

max_action_items: 10
```

### CLI Options

```
--email EMAIL        Your Embedded account email (required)
--execute            Write files (default is dry run)
--incremental        Only fetch memos since last run
--category CATEGORY  Filter: Meeting, Idea, ToDo, People, Budget, Other
--memo-id ID         Process a single memo by ID
```

---

## Python SDK (`embedded.py`)

The shared client that all connectors use. You can also use it directly.

### `EmbeddedClient`

| Method | Description |
|--------|-------------|
| `login(email, password)` | Authenticate with your Embedded account |
| `get_memos(since, category, include_embeddings)` | Fetch memos with stitched transcriptions |
| `get_raw_chunks(since, category, include_embeddings)` | Fetch raw embedding chunks (for search/ML) |

### Memo Fields

Every memo returned by `get_memos()` includes:

| Field | Type | Description |
|-------|------|-------------|
| `memo_id` | string | Unique identifier |
| `transcription` | string | Full transcription (stitched from chunks) |
| `summary` | string | AI-generated executive summary |
| `category` | string | Meeting, Idea, ToDo, People, Budget, Other |
| `tags` | string | Comma-separated user tags |
| `audio_file_name` | string | Original audio file path |
| `created_at` | string | ISO 8601 timestamp |
| `updated_at` | string | ISO 8601 timestamp |
| `chunk_count` | int | Number of embedding chunks |

### Embeddings

Pass `include_embeddings=True` to get the 3072-dimensional Gemini embedding vectors for each chunk. Useful for building semantic search, clustering, or recommendation features.

```python
memos = client.get_memos(include_embeddings=True)
for memo in memos:
    for chunk in memo["chunks"]:
        vector = chunk["embedding"]  # 3072-dim list of floats
        print(f"Chunk {chunk['chunk_index']}: {len(vector)} dimensions")
```

### Raw Chunks

Use `get_raw_chunks()` when you need per-chunk data without stitching:

```python
chunks = client.get_raw_chunks(include_embeddings=True)
for chunk in chunks:
    print(chunk["memo_id"], chunk["chunk_index"], chunk["start_char"], chunk["end_char"])
```

## CLI Options

### Obsidian Connector

```
--email EMAIL        Your Embedded account email (required)
--vault-path PATH    Obsidian vault directory for memos (required)
--incremental        Only export memos created since last run
--category CATEGORY  Filter: Meeting, Idea, ToDo, People, Budget, Other
--dry-run            Preview without writing files
```

### JSON Connector

```
--email EMAIL           Your Embedded account email (required)
--output PATH           Output JSON file path (required)
--category CATEGORY     Filter by category
--since TIMESTAMP       ISO timestamp — only memos after this date
--include-embeddings    Include 3072-dim embedding vectors
--raw-chunks            Export raw chunks instead of stitched memos
```

## Building Your Own Connector

Create a new directory under `connectors/` and use the shared client:

```python
from embedded import EmbeddedClient

client = EmbeddedClient()
client.login(email, password)

# Get stitched memos (transcription chunks combined)
memos = client.get_memos()

# Or get raw chunks for embedding-level access
chunks = client.get_raw_chunks(include_embeddings=True)

# Build your integration here!
```

See `examples/` for more patterns.

## Contributing

We welcome community connectors! To add a new one:

1. Fork this repo
2. Create `connectors/your-connector/export.py`
3. Use `embedded.py` for auth and data fetching
4. Add a section to this README
5. Open a pull request

Ideas for connectors:
- **Logseq** — export as Logseq-compatible markdown
- **Roam Research** — daily notes format
- **CSV** — spreadsheet-friendly export
- **Todoist / Things** — extract ToDo items as tasks
- **Slack** — post summaries to a channel
- **Webhook** — push new memos to any URL
- **SQLite** — local searchable database

## Project Structure

```
embedded-connect/
├── embedded.py                   # Shared Python SDK
├── requirements.txt              # Python dependencies
├── connectors/
│   ├── obsidian/
│   │   ├── export.py             # Simple Obsidian export
│   │   └── smart-vault/          # Full vault system
│   │       ├── setup.py          # Interactive setup wizard
│   │       ├── ingest.py         # Smart routing pipeline
│   │       ├── normalize.py      # Person file normalizer
│   │       ├── config.yaml       # Pipeline configuration
│   │       └── vault-template/   # Starter vault structure
│   ├── notion/
│   │   └── export.py             # Notion database connector
│   └── json-export/
│       └── export.py             # JSON export connector
└── examples/
    ├── basic_usage.py            # Fetch and print memos
    └── search_memos.py           # Keyword search across memos
```

## Security

- Your password is used only to authenticate with Firebase and is never stored or transmitted elsewhere
- The API verifies your identity server-side and returns only your data
- No API keys or service credentials are required
- Row Level Security (RLS) enforces per-user data isolation at the database level
- All communication is over HTTPS

## License

MIT — see [LICENSE](LICENSE).

## Links

- [Embedded App](https://github.com/mattlsmith/embedded)
- [Report Issues](https://github.com/mattlsmith/embedded-connect/issues)
