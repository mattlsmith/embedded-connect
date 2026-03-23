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
| **Obsidian** | Markdown files with YAML frontmatter, organized by month | `connectors/obsidian/` |
| **JSON Export** | Full data dump as JSON — great for custom integrations | `connectors/json-export/` |

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
- **Notion** — create pages in a Notion database
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
├── embedded.py              # Shared Python SDK
├── requirements.txt           # Python dependencies
├── connectors/
│   ├── obsidian/
│   │   └── export.py          # Obsidian Markdown connector
│   └── json-export/
│       └── export.py          # JSON export connector
└── examples/
    ├── basic_usage.py         # Fetch and print memos
    └── search_memos.py        # Keyword search across memos
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
