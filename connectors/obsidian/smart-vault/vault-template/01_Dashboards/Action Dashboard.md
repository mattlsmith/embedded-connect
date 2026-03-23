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

## Follow-Ups

- [ ]
