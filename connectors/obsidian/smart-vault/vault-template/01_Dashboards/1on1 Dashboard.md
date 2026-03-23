---
type: dashboard
---

# 1:1 Dashboard

## Recent 1:1s

```dataview
TABLE person, team, role, last_1on1
FROM "03_People"
WHERE last_1on1 != null
SORT last_1on1 DESC
LIMIT 15
```

## All People by Team

```dataview
LIST
FROM "03_People"
SORT file.name ASC
GROUP BY team
```

## Open Action Items

```dataview
TASK
FROM "03_People"
WHERE !completed
SORT file.name ASC
LIMIT 20
```
