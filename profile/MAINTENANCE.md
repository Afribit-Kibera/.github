# Portfolio Data and Maintenance

This repository holds the public Afribit Builders profile. Project names and summaries are curated in `projects.json`; edit the surrounding copy in `README.template.md`, not the generated `README.md`. Source repositories retain their own licences, setup and contribution instructions.

## What Is Counted

- **Catalogue projects:** all approved public product summaries, including products with private source. This is a catalogue count, not a deployment or impact claim.
- **Public repositories:** only explicitly named repositories that the API confirms are public and owned by Afribit-Kibera. `.github` is excluded.
- **Original repositories:** the public repositories not marked as forks by GitHub. This describes GitHub's fork flag, not a claim that every line was written by Afribit.
- **Code mix:** GitHub Linguist's detected language bytes, summed across non-fork public projects. These are not lines of code or authorship percentages.
- **Activity:** weekly commit totals from GitHub's statistics endpoint across the original public projects. The last reported week is partial. Merge commits are excluded by that endpoint; commit counts are not a measure of community impact or developer performance.
- **Contributors:** linked GitHub accounts reported by those original repositories. Bot accounts and the verified Codex automation account are separated from people. Unlinked commit authors may not appear; this is not a team headcount.

The Blink-derived wallet is shown in the catalogue but excluded from aggregate languages, activity and contributors so its inherited upstream history is not presented as Afribit work. Its upstream credits remain in the wallet repository.

## Private Projects

Afribit AI, Afribit Console and AfriBot for Socials have owner-approved public product summaries. Their source remains private. The generator never requests their repository metadata, contributors, languages, issues or activity. It does not contain their private repository URLs or operational endpoints.

## Refresh

The workflow runs weekly and can also be started through **Actions > Refresh portfolio > Run workflow**. It uses the workflow's repository-scoped token; no personal access token or external statistics service is required. Only profile assets, the generated public dataset and marked README regions are committed.

To refresh locally with an authenticated GitHub CLI:

```bash
python scripts/test_profile.py
python scripts/refresh_profile.py
python scripts/test_profile.py
```

For layout-only changes, `python scripts/refresh_profile.py --render-only` uses the saved public dataset. Run the tests, inspect desktop/mobile and light/dark renders, and review the exact file list before committing.

GitHub may return HTTP 202 while calculating activity. The generator retries briefly; if any repository is unavailable, it shows an availability message instead of silently treating missing data as zero. The last successfully published commit remains intact if another required public API read fails.

Assets are first-party, self-contained SVG images with accessible titles and descriptions. Separate mobile images keep chart labels readable at narrow widths. Native Markdown project text and a text summary remain available alongside the charts.

Generated image URLs include their content hash so refreshed charts do not depend on GitHub's image cache expiring. The workflow runs only on the reviewed default branch, a manual dispatch or its weekly schedule; it does not execute on pull requests.

## Official References

- [GitHub repository statistics](https://docs.github.com/en/rest/metrics/statistics)
- [Repository languages and contributors](https://docs.github.com/en/rest/repos/repos)
- [Scheduled workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
