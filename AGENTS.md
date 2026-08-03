# Agent notes

- Site identity: EXTRA TIME. Deployment is fully automatic — GitHub Pages serves the `main` branch.
- Content is auto-published by `.github/workflows/auto-update.yml` (30-minute cron) which runs `scripts/fetch-content.mjs` and commits `data/*.json`. Do not manually edit `data/*.json`.
- Manual update: `gh workflow run "Auto Update Dispatch"`.
- All stories are hosted in-house (hash routes `#/story/{slug}`); no links to original sources.
- Never commit API keys or secrets to this repository.
