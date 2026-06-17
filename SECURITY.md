# Security and Privacy Notes

This repository is public. The dashboard is designed as a local-first personal finance tool, but some actions can still expose data if used carelessly.

## Private Data Boundary

Do not commit or share:

- `.env` files, API keys, app secrets, access tokens, or brokerage credentials
- raw brokerage exports such as `.xlsx`, `.csv`, `.tsv`, or copied balance tables
- generated `outputs/portfolio_dashboard.html`
- generated enrichment JSON under `work/`
- screenshots that reveal holdings, quantities, average prices, market values, cash balances, or account types

## Browser Storage

The dashboard does not persist holdings, average prices, quantities, or account data in `localStorage` by default. It removes legacy `portfolio-dashboard-holdings` and `portfolio-dashboard-version` keys on load/save.

The browser may still keep non-sensitive preferences such as currency display mode, FX rate, and investment preference buttons.

## External Network Requests

The static browser dashboard does not call external market or FX data providers. It does not send holdings, symbols, prices, quantities, or account data to third-party sites from the browser.

Local Python scripts can contact only user-configured API providers in the default launcher:

- Korea Investment Securities Open API for quotes when keys are configured
- OPENDART for disclosure data when a user-provided key is configured

These scripts may send stock codes and API credentials to the configured provider. They must run only from a trusted local machine. Non-key public scraping scripts are not part of the default launcher.

## Clipboard Risk

JSON export contains sensitive portfolio fields. The dashboard asks for confirmation before copying it to the clipboard. Paste it only into trusted local tools.

## Public Commit Checklist

Before pushing:

1. Run `git status --ignored --short` and verify private files are ignored.
2. Verify `src/portfolio_dashboard.template.html` has empty `exampleHoldings` and empty DART enrichment.
3. Scan public candidate files for known holding names/codes and secret-like strings.
4. Do not stage generated dashboard HTML, generated JSON, `.env`, raw workbooks, or screenshots.
