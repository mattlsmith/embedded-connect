---
type: weekly-review
week: "{{date:gggg-[W]ww}}"
date: "{{date:YYYY-MM-DD}}"
---

# Weekly Review — {{date:MMM DD, YYYY}}

## This Week's Voice Memos

```dataview
TABLE WITHOUT ID
    file.link AS "Memo",
    category,
    date
FROM "02_Voice_Memos" OR "00_Inbox" OR "04_Resources"
WHERE source = "embedded-voice-memo"
    AND date >= date("{{date:YYYY-MM-DD}}") - dur(7 days)
    AND date <= date("{{date:YYYY-MM-DD}}")
SORT date DESC
```

## People I Met With

```dataview
TABLE WITHOUT ID
    file.link AS "Person",
    team,
    last_1on1
FROM "03_People"
WHERE last_1on1 >= date("{{date:YYYY-MM-DD}}") - dur(7 days)
    AND last_1on1 <= date("{{date:YYYY-MM-DD}}")
SORT last_1on1 DESC
```

## Open Action Items

```dataview
TASK
FROM "03_People" OR "00_Inbox"
WHERE !completed
LIMIT 20
```

## Reflections

-
-
-

## Next Week Priorities

- [ ]
- [ ]
- [ ]
