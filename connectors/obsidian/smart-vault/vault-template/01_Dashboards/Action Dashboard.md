---
type: dashboard
---

# Action Dashboard

## My Tasks

- [ ]

---

## Voice Memo ToDos

```dataview
TASK
FROM "00_Inbox"
WHERE !completed
SORT file.name ASC
```

---

## Open Action Items (People)

```dataview
TASK
FROM "03_People"
WHERE !completed
SORT file.name ASC
LIMIT 30
```

---

## Stale 1:1s (Need Attention)

```dataview
TABLE WITHOUT ID
    file.link AS "Person",
    team,
    choice(last_1on1, round((date(today) - last_1on1).days) + " days", "never") AS "Since Last 1:1"
FROM "03_People"
WHERE last_1on1 = null OR (date(today) - last_1on1).days > 14
SORT last_1on1 ASC
LIMIT 10
```

---

## Recent Memos (Last 7 Days)

```dataview
TABLE WITHOUT ID
    file.link AS "Memo",
    category,
    date
FROM "02_Voice_Memos" OR "00_Inbox" OR "04_Resources"
WHERE source = "embedded-voice-memo" AND date >= date(today) - dur(7 days)
SORT date DESC
LIMIT 10
```

---

## Follow-Ups

- [ ]
