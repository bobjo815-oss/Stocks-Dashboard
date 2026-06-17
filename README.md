# Stocks Dashboard

Local-first portfolio dashboard for consolidating brokerage balance exports into a single Korean-language investment dashboard.

This project was created from an iterative desktop workflow:

1. A personal brokerage balance workbook was exported from multiple accounts.
2. The workbook structure was normalized into a common holding schema.
3. A single-file dark-theme dashboard was generated for local viewing.
4. Local update scripts were added for user-key quote refreshes and OPENDART disclosure data.
5. Public-repository hygiene was added so private holdings, account data, API keys, generated dashboards, and raw spreadsheets stay out of Git.


## Origin Note

This project started as a local-first implementation experiment inspired by portfolio-analysis prompting ideas from 허성범 YouTube and the linked Notion prompt collection: [AI](https://app.notion.com/p/yofcompanycom/AI-380c94a109af81ce9eb4d726263e53f8?source=copy_link). The repository does not copy private prompt text, account data, or brokerage exports; it keeps only the public-safe implementation and documentation.
## What This Repository Contains

- Public dashboard template under `src/`
- Local update scripts under `work/`
- Windows launcher scripts under `outputs/`
- API setup notes
- Ignore rules for private inputs and generated financial outputs

## What This Repository Must Not Contain

Never commit:

- `.env` or any API key
- brokerage account numbers
- raw balance exports
- generated `portfolio_dashboard.html`
- generated JSON enrichment files
- screenshots or copied text containing holdings, quantities, average prices, cash balances, or account details

The public dashboard template is tracked at `src/portfolio_dashboard.template.html`. The generated dashboard is intentionally ignored because it embeds portfolio holdings and financial values.

## Local Setup

1. Copy `.env.example` to `.env`.
2. Fill in only the local values you want to use.
3. Set `STOCKS_XLSX_PATH` to your private workbook path, or place a private workbook at `input/stocks.xlsx`.
4. Run the Korean-named update launcher in `outputs/`, or run `work/update_portfolio_from_xlsx.py` from a local environment.

The update launcher renders `outputs/portfolio_dashboard.html` from `src/portfolio_dashboard.template.html`, imports the workbook, queries user-configured Korea Investment Securities and OPENDART APIs where configured, and opens the generated local dashboard. Browser-side market/FX fetching is disabled; exchange rates can be entered manually.

## Data Model

The dashboard normalizes holdings into:

- broker
- account type
- ticker or stock code
- name
- sector
- average price
- shares
- current price
- cost
- market value
- profit/loss
- optional dividend and technical indicators

Cash balances are represented as cash-like positions without storing account numbers.

## API Notes

- OPENDART is used for disclosure, dividend-related filings, periodic reports, and financial-statement signals.
- Korea Investment Securities Open API can be used for domestic quote refreshes when each user configures their own keys.
- API secrets must stay in `.env` only.
- The browser dashboard must never contain API secrets.


## Public History Safety

This repository is public. A normal cleanup commit does not erase earlier public commits. If private data, generated dashboards, raw exports, API secrets, or holding-derived identifiers ever enter Git history, stop and rewrite the public history from a clean tree or recreate the repository. Do not rely on a later delete commit.

Each user must generate `outputs/portfolio_dashboard.html` locally for their own account data. The public repository should contain only source code, templates, launchers, and documentation. Generated dashboards, workbook exports, JSON enrichments, logs, screenshots, and copied brokerage tables must remain local-only and ignored.

External data access is intentionally user-owned. The browser template does not fetch market or FX data on its own; users who want quote, DART, or brokerage API refreshes must configure their own local API keys in `.env`.
## Public Safety

This is a public repository. Treat all portfolio data as private financial information. Keep the repo code-only and regenerate private dashboard artifacts locally. See `SECURITY.md` for the full local/external data-flow boundary.
