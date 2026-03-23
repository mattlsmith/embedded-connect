---
type: dashboard
---

# People Network

> Use Obsidian's **Graph View** (Ctrl/Cmd+G) and filter to the `03_People` folder to see your full relationship network. The more meetings and mentions, the stronger the connections.

---

## Most Active Relationships

```dataview
TABLE length(file.inlinks) AS "Mentions", team, role, last_1on1
FROM "03_People"
SORT length(file.inlinks) DESC
LIMIT 15
```

## Stale 1:1s (2+ Weeks Since Last Meeting)

```dataview
TABLE person, team, last_1on1,
      choice(last_1on1, round((date(today) - last_1on1).days) + " days ago", "never") AS "Last Contact"
FROM "03_People"
WHERE last_1on1 = null OR (date(today) - last_1on1).days > 14
SORT last_1on1 ASC
```

## Recently Met

```dataview
TABLE person, team, last_1on1
FROM "03_People"
WHERE last_1on1 != null AND (date(today) - last_1on1).days <= 7
SORT last_1on1 DESC
```

## People by Team

```dataview
TABLE WITHOUT ID
    file.link AS "Person",
    role,
    last_1on1,
    length(file.inlinks) AS "Mentions"
FROM "03_People"
GROUP BY team
SORT team ASC
```

## Meeting Co-occurrence

> People who appear in the same meeting files are likely collaborators. Check the Graph View with the **03_People** and **02_Voice_Memos/Meetings** folders both visible to see who clusters together.

```dataview
TABLE WITHOUT ID
    file.link AS "Meeting",
    people AS "People Present",
    date
FROM "02_Voice_Memos/Meetings"
WHERE people != null
SORT date DESC
LIMIT 20
```

---

> **Tip:** In Graph View settings, try:
> - **Filters:** Show only `path:03_People OR path:02_Voice_Memos`
> - **Groups:** Color `path:03_People` one color and meetings another
> - **Display:** Enable "Arrows" to see directionality
