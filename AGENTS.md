# Agent Instructions

This repository is public. The highest-priority rule is to prevent leakage of private financial information.

## Privacy Boundary

Do not commit, print, summarize in public docs, or expose:

- API keys, app secrets, access tokens, or account credentials
- brokerage account numbers or account identifiers
- raw brokerage exports
- generated dashboard HTML containing holdings
- template files that accidentally contain real holdings, quantities, prices, cash balances, or account labels
- generated JSON files containing portfolio-derived enrichment
- screenshots, copied balance tables, holdings lists, quantities, average prices, current values, cash balances, or P/L details

`.env`, `input/`, spreadsheets, generated HTML, generated JSON, and logs must remain ignored.


## Git History Rule

A later cleanup commit is not enough if private financial data entered public history. Before pushing privacy-sensitive work, check both the current tracked files and relevant Git history. If secrets, generated dashboards, raw exports, holdings, quantities, prices, cash balances, account labels, or holding-derived identifiers appear in history, stop and ask the repository owner for explicit approval before any destructive rewrite such as an orphan-root replacement or force-push.

Never force-push or rewrite public history unless the user explicitly requests it for this repository. When approved, rebuild the branch from a clean public-safe tree and include only tracked source code, templates, launchers, and documentation.
## Development Rules

- Keep source code and templates public-safe. `src/portfolio_dashboard.template.html` must contain empty `exampleHoldings`, empty DART enrichment, and no real portfolio values.
- Keep local/private data in `.env`, ignored input folders, or ignored generated outputs.
- Prefer environment variables over hardcoded user paths.
- If a script needs private data, read it from `.env` or an ignored local file.
- Before committing, run:

```powershell
git status --ignored --short
git ls-files
```

Confirm no private data files are tracked.

## Project Origin

This dashboard was built from an iterative local workflow for consolidating multi-account stock balances into a local-only portfolio view. The implementation evolved to support:

- brokerage workbook normalization
- cash balance handling
- user-key API quote refresh
- Korea Investment Securities quote integration without browser-side public market fetching
- OPENDART disclosure enrichment
- dashboard guidance based on portfolio structure and public disclosures

The origin story is intentionally described without any actual holdings, account values, or personally identifying financial details.

## Public Commit Checklist

Before committing or pushing:

1. Verify `.env` is ignored.
2. Verify `outputs/portfolio_dashboard.html` is ignored.
3. Verify `src/portfolio_dashboard.template.html` contains empty `exampleHoldings` and no real portfolio values.
4. Verify workbook files are ignored.
5. Verify generated JSON files are ignored.
6. Scan tracked files for secrets if `.env` exists.
7. Do not push until the tracked file list is code/docs/templates only.
8. If the repo is public and history was contaminated, get explicit approval before rewriting history and force-pushing a clean root commit.
