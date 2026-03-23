---
type: dashboard
---

# Rapport Dashboard

Use this dashboard to keep track of personal details about your team — birthdays, hobbies, family, interests. Building rapport strengthens working relationships.

## People Overview

```dataview
TABLE person, team, role
FROM "03_People"
SORT team ASC, file.name ASC
```

## Tips

- Add a `rapport:` field to each person's frontmatter with a short summary
- Use the collapsible **Personal Details** section in each person file for longer notes
- Review before 1:1s to reconnect on personal topics
