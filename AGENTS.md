# Agent notes

- Deployment is fully automatic: the site is served by GitHub Pages from the `main` branch.
- Content is auto-published by `.github/workflows/auto-update.yml` (30-minute cron) which runs `scripts/fetch-content.mjs` and commits `data/*.json`. Do not manually edit `data/*.json`.
- To publish a manual update run: `gh workflow run "Auto Update Dispatch"`.
- Never commit API keys or secrets to this repository.
