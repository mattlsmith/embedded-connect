---
type: dashboard
---

# Voice Memo Analytics

---

## This Week's Activity

```dataview
TABLE WITHOUT ID
    file.link AS "Memo",
    category,
    date,
    length(file.outlinks) AS "Links"
FROM "02_Voice_Memos" OR "00_Inbox" OR "04_Resources"
WHERE source = "embedded-voice-memo" AND date >= date(today) - dur(7 days)
SORT date DESC
```

## Category Breakdown (All Time)

```dataview
TABLE WITHOUT ID
    category AS "Category",
    length(rows) AS "Count"
FROM "02_Voice_Memos" OR "00_Inbox" OR "04_Resources"
WHERE source = "embedded-voice-memo"
GROUP BY category
SORT length(rows) DESC
```

## Memos by Month

```dataview
TABLE WITHOUT ID
    dateformat(date, "yyyy-MM") AS "Month",
    length(rows) AS "Memos"
FROM "02_Voice_Memos" OR "00_Inbox" OR "04_Resources"
WHERE source = "embedded-voice-memo" AND date != null
GROUP BY dateformat(date, "yyyy-MM")
SORT dateformat(date, "yyyy-MM") DESC
LIMIT 12
```

## Recent Ideas

```dataview
TABLE WITHOUT ID
    file.link AS "Idea",
    date,
    tags
FROM "04_Resources/Ideas"
WHERE source = "embedded-voice-memo"
SORT date DESC
LIMIT 10
```

## Open ToDos

```dataview
TASK
FROM "00_Inbox"
WHERE !completed AND source = "embedded-voice-memo"
SORT file.name DESC
LIMIT 20
```

## Longest Memos (Multi-Chunk)

```dataview
TABLE WITHOUT ID
    file.link AS "Memo",
    category,
    date,
    embedding_chunks AS "Chunks"
FROM "02_Voice_Memos" OR "00_Inbox" OR "04_Resources"
WHERE source = "embedded-voice-memo" AND embedding_chunks > 1
SORT embedding_chunks DESC
LIMIT 10
```

## People Mentioned Most

```dataview
TABLE WITHOUT ID
    file.link AS "Person",
    team,
    length(file.inlinks) AS "Appearances",
    last_1on1
FROM "03_People"
SORT length(file.inlinks) DESC
LIMIT 10
```

---

## Timeline (Last 30 Days)

```dataview
LIST WITHOUT ID
    "**" + dateformat(date, "MMM dd") + "** — " + category + " — " + file.link
FROM "02_Voice_Memos" OR "00_Inbox" OR "04_Resources"
WHERE source = "embedded-voice-memo" AND date >= date(today) - dur(30 days)
SORT date DESC
```
