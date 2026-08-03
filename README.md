# THE DISPATCH — Football's Daily Briefing

A modern, magazine-styled football news site that **publishes itself**.

Live: https://viasrijan.github.io/dispatch/

## How it works

1. **`scripts/fetch-content.mjs`** — every 30 minutes a GitHub Actions cron fetches headlines from credible football desks (BBC Sport, The Guardian, The Independent, ESPN FC), plus live scores from ESPN's public API.
2. The script **curates the content automatically**: filters out non-football stories, removes duplicates across sources, edits headlines to fit the layout, categorises stories (Transfers & Rumours, Match Reports, Injuries, Tactics & Analysis, News), tags leagues, picks a rotating lead story, and posts the result as `data/content.json` + `data/scores.json`.
3. **`.github/workflows/auto-update.yml`** commits the fresh edition; GitHub Pages auto-rebuilds and the site is updated within a few minutes — no human involved.

You can trigger a manual update anytime:

```sh
gh workflow run "Auto Update Dispatch"
```

## Site features

- **Live scores ticker** — sticky marquee bar that refreshes live from ESPN every 2 minutes (client-side) and shows the latest/upcoming matches from five leagues.
- **Hero lead + latest news grid** — auto-rotating edition, every article links back to its original publisher.
- **Transfers & Rumours** and **Fixtures & Results** sections, auto-populated each cycle.
- **Magazine design** — Playfair Display serif headlines, newsprint palette, dark-mode aware, mobile-first navigation, reveal animations, reduced-motion support.

## Local development

```sh
# Regenerate content + scores (needs network)
node scripts/fetch-content.mjs

# Serve the site
python3 -m http.server 8000
```

## Stack

Vanilla HTML/CSS/JS (no build step) + GitHub Actions + RSS feeds + ESPN public API.
