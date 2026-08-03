# EXTRA TIME — Football, Every Day

A modern, magazine-styled football news site that **publishes itself** — no human hands needed.

Live: https://viasrijan.github.io/dispatch/

## How it works

1. **`scripts/fetch-content.mjs`** — every 30 minutes a GitHub Actions cron fetches headlines from credible football desks (BBC Sport, The Guardian, The Independent, ESPN FC), plus live scores from ESPN's public API.
2. The script **curates, edits and authors the content in-house**:
   - filters out non-football stories and duplicate coverage,
   - edits headlines to fit the layout,
   - writes each story in Extra Time's own editorial style (briefing lead, cleaned paragraphs, category-specific closers),
   - sources a free photo for every story from Wikimedia Commons,
   - categorises stories (Transfers & Rumours, Match Reports, Injuries, Tactics & Analysis, News) and tags leagues,
   - picks a rotating lead story and posts everything as `data/content.json` + `data/scores.json`.
3. **`.github/workflows/auto-update.yml`** commits the fresh edition; GitHub Pages auto-rebuilds. All stories are hosted on our site — no links out to originals.

Trigger a manual update anytime:

```sh
gh workflow run "Auto Update Dispatch"
```

## Site features

- **Live scores ticker** — sticky marquee bar, refreshed live from ESPN every 2 minutes client-side, plus fixtures with team logos across five leagues.
- **Story pages hosted in-house** — hash-routed (`#/story/…`), full editorial article view, no external links.
- **Images everywhere** — lead hero shot, card thumbnails, transfer row thumbs, all lazy-loaded from Wikimedia Commons.
- **Magazine design** — Inter-only typography on a light grey palette (dark-mode aware), mobile-first navigation, reveal animations, reduced-motion support.

## Local development

```sh
node scripts/fetch-content.mjs   # regenerate content + scores (needs network)
python3 -m http.server 8000      # serve the site
```

## Stack

Vanilla HTML/CSS/JS (no build step) + GitHub Actions + RSS feeds + ESPN public API + Wikimedia Commons.
