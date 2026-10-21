# Portfolio Data and Maintenance

This repository holds the public Afribit Builders profile. Project names and summaries are curated in `projects.json`; edit the surrounding copy in `README.template.md`, not the generated `README.md`. Source repositories retain their own licences, setup and contribution instructions.

## What Is Counted

- **Catalogue projects:** all approved public product summaries, including products with private source. This is a catalogue count, not a deployment or impact claim.
- **Public repositories:** only explicitly named repositories that the API confirms are public and owned by Afribit-Kibera. `.github` is excluded.
- **Original repositories:** the public repositories not marked as forks by GitHub. This describes GitHub's fork flag, not a claim that every line was written by Afribit.
- **Code mix:** GitHub Linguist's detected language bytes, summed across non-fork public projects. These are not lines of code or authorship percentages.
- **Activity:** twelve weeks of default-branch commits from GitHub's paginated commits API across the original public projects. Commits are deduplicated by SHA within each repository, grouped by committer date into Sunday-starting UTC weeks and exclude merge commits. The latest reported week is partial. The repository heatmap reconciles to each weekly total. Totals include all commit authors; they are not a human-only count or a measure of community impact or developer performance.
- **Contributors:** human GitHub accounts reported by those original repositories. AI and automation are tools, not collaborators: bot accounts and configured automation logins are omitted from the contributor display and published contributor data. Unlinked commit authors may not appear; this is not a team headcount. Content-specific credits, including Gemini audio attribution, are separate.

The Blink-derived wallet is shown in the catalogue but excluded from aggregate languages, activity and contributors so its inherited upstream history is not presented as Afribit work. Its upstream credits remain in the wallet repository.

## Private Projects

Afribit AI, Afribit Console and AfriBot for Socials have owner-approved public product summaries. Their source remains private. The generator never requests their repository metadata, contributors, languages, issues or activity. It does not contain their private repository URLs or operational endpoints.

## Refresh

The workflow runs weekly and can also be started through **Actions > Refresh portfolio > Run workflow**. It uses the workflow's repository-scoped token; no personal access token or external statistics service is required. Only profile assets, the generated public dataset and marked README regions are committed.

To refresh locally with an authenticated GitHub CLI:

```bash
npm ci --ignore-scripts
npm test
python scripts/test_profile.py
python scripts/refresh_profile.py
python scripts/test_profile.py
```

For layout-only changes, `python scripts/refresh_profile.py --render-only` uses the saved public dataset. Run the tests, inspect desktop/mobile and light/dark renders, and review the exact file list before committing.

The collector reads bounded, fully paginated commit history directly, avoiding the statistics endpoint's HTTP 202 calculation delays. It keeps aggregate counts only, not commit messages, emails or author details. A successful empty commit list is zero activity; a failed or incomplete read is unavailable data. If any original repository is unavailable, it shows an availability message rather than a partial total. The last successfully published commit remains intact if another required public API read fails.

Assets are first-party, self-contained SVG images with accessible titles and descriptions. Separate mobile images keep chart labels readable at narrow widths. Native Markdown project text and a text summary remain available alongside the charts.

The GitHub API supplies the numbers automatically; images are the README-compatible presentation, not manually maintained calculations. [Apache ECharts](https://github.com/apache/echarts) renders the language composition rings, weekly trend and repository heatmap as resolution-independent SVG. The renderer is version-pinned in the lockfile and runs locally in Actions, without an external chart service or additional credentials. Animation and script-dependent interactions are disabled. Exact heatmap counts and language percentages remain readable without relying on colour.

The overall language ring shows the five largest languages plus all remaining bytes grouped as Other. Each smaller project ring shows that project's leading language against its remaining source bytes, rather than implying that all projects have the same language proportions.

## Visualisation Research

- [Lowlighter Metrics](https://github.com/lowlighter/metrics): extensive organisation-compatible plugins, including calendars and language analytics. Its documented organisation setup requires a personal token with `read:org`.
- [GitHub Profile Summary Cards](https://github.com/vn7n24fzkq/github-profile-summary-cards): automatic profile cards with organisation support, language donuts and activity views.
- [GitHub Readme Stats](https://github.com/anuraghazra/github-readme-stats): established stats and language cards with self-hosted and Actions options.
- [Apache ECharts server-side SVG](https://echarts.apache.org/handbook/en/how-to/cross-platform/server/): selected here so the graphics can use Afribit's explicit public-repository allowlist and fork exclusions without changing the existing token boundary.

Generated image URLs include their content hash so refreshed charts do not depend on GitHub's image cache expiring. The workflow runs only on the reviewed default branch, a manual dispatch or its weekly schedule; it does not execute on pull requests.

## Official References

- [GitHub commits API](https://docs.github.com/en/rest/commits/commits#list-commits)
- [Repository languages and contributors](https://docs.github.com/en/rest/repos/repos)
- [Scheduled workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
