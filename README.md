[README2.md](https://github.com/user-attachments/files/34928309/README2.md)
# 🌐 International Cost of Capital App

A Streamlit app that compares a project's **cost of equity, cost of debt and WACC in U.S. dollars and in the currency of any selected country**.

## Features
- **Live data with sources and dates** (plus a 🔄 Refresh button):
  - Industry unlevered betas: Aswath Damodaran, [betas.xls](https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls)
  - Baa2/BBB USD spread (large non-financial firms): Damodaran, [ratings.html](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/ratings.html)
  - Statutory corporate tax rates: [OECD Corporate Tax Statistics 2024](https://www.oecd.org/en/publications/corporate-tax-statistics-2024_9c27d6e8-en/full-report/statutory-corporate-income-tax-rates_440f9286.html)
  - 10-year government bond yields: [Trading Economics](https://tradingeconomics.com/bonds) (scraped, no API key)
- Select an **industry** and **target country**; adjust the **equity risk premium** and **target debt share**.
- **Manual overrides** for unlevered beta, both tax rates, USD BBB spread and both government yields. The foreign BBB spread can be overridden; when the toggle is off, the app shows the auto (parity-implied) spread.
- **Tax-rate switch**: use the U.S. or the selected country's rate for the project (same rate in both currencies).
- **Side-by-side results**, a step-by-step "How it's calculated" tab, an **all-industry comparison**, built-in **verification checks**, and **CSV downloads**.
- **Defaults:** Software (System & Application), United States, U.S. tax rate, 6.5% ERP, 30% debt.

## Formulas
| Step | Formula |
|---|---|
| Levered beta | β_L = β_U × [1 + (1 − t) × D/E] |
| USD cost of equity | k_e = r_f,US + β_L × ERP |
| USD cost of debt | k_d = r_f,US + BBB spread |
| Foreign-currency rate | k_F = (1 + k_USD) × (1 + r_f,F) / (1 + r_f,US) − 1 |
| Foreign spread (auto) | s_F = k_d,F − r_f,F; with override, k_d,F = r_f,F + s_F |
| WACC | E/V × k_e + D/V × k_d × (1 − t) |

## Verification (built into the app)
1. Equal government yields → identical USD and local results (foreign spread override off).
2. Zero debt → WACC = cost of equity.
3. Overriding the foreign-currency spread leaves USD results unchanged.

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy
Push `app.py`, `requirements.txt` and `README.md` to a GitHub repo → [share.streamlit.io](https://share.streamlit.io) → New app → select the repo, branch and `app.py` → Deploy.

## Notes
If a source can't be reached, the app falls back to an embedded copy of the data, flags it as **fallback** in the Data sources tab, and lets you enter the value manually.
