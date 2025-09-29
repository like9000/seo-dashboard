# seo-dashboard

This repository contains automation scripts and GitHub Actions workflows that orchestrate
SEO data synchronisation tasks.

## Workflows

Reusable automation lives under [`workflows/`](workflows/) and is deployed through four
scheduled GitHub Actions workflows:

| Workflow | Schedule (UTC) | Purpose |
| --- | --- | --- |
| `gsc_pull.yml` | Daily at 02:30 | Pull Google Search Console data for configured properties. |
| `monitors_sync.yml` | Weekdays at 06:00 | Synchronise monitor definitions from the monitoring provider. |
| `ranks_pull.yml` | Daily at 03:15 | Fetch rank-tracking data for the configured project. |
| `refresh_views.yml` | Daily at 05:00 | Refresh database or Supabase views so dashboards stay current. |

Each workflow sets up Python 3.11, installs dependencies from `requirements.txt` when it is
present, and invokes the companion script in [`scripts/`](scripts/) with retry logic so
transient failures do not abort the run immediately.

## Required GitHub secrets

| Secret | Used by | Description |
| --- | --- | --- |
| `GSC_SERVICE_ACCOUNT_JSON` | `gsc_pull.yml` | JSON blob for the Google service account authorised for Search Console. |
| `GSC_PROPERTY_IDS` | `gsc_pull.yml` | Comma-separated list of Search Console property identifiers to pull. |
| `MONITORS_API_TOKEN` | `monitors_sync.yml` | API token that grants access to the monitoring service. |
| `MONITORS_BASE_URL` | `monitors_sync.yml` | Base URL of the monitoring service API. |
| `RANKS_API_TOKEN` | `ranks_pull.yml` | Credential used to authenticate against the rank-tracking API. |
| `RANKS_PROJECT_ID` | `ranks_pull.yml` | Identifier for the project whose ranking data is fetched. |
| `SUPABASE_URL` | `refresh_views.yml` | Supabase project URL hosting the database views. |
| `SUPABASE_SERVICE_ROLE_KEY` | `refresh_views.yml` | Service role key permitted to refresh views. |

Secrets must be configured in the repository or organisation settings before the workflows
can run on GitHub.

## Local verification

The workflows can be exercised locally with [`act`](https://github.com/nektos/act). Examples:

```bash
act workflow_dispatch -W workflows/gsc_pull.yml
act workflow_dispatch -W workflows/monitors_sync.yml -j run
```

When `act` is unavailable, run the scripts directly with the required environment variables
set. This repository includes lightweight placeholder implementations that validate required
configuration and log their progress:

```bash
export GSC_SERVICE_ACCOUNT_JSON='{}'
export GSC_PROPERTY_IDS='sc-domain:example.com'
python scripts/gsc_pull.py
```

Replace the environment variable values with real credentials during production execution.
