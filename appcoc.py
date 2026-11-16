"""
International Cost of Capital App
Compares a project's cost of equity, cost of debt and WACC in USD and in the
currency of a selected country, using industry betas and the BBB spread from
Aswath Damodaran, OECD statutory corporate tax rates, and 10-year government
bond yields from Trading Economics.
"""
import io
import re
from datetime import datetime

import altair as alt
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="International Cost of Capital", page_icon="🌐", layout="wide")

# ----------------------------------------------------------------------------
# Sources
# ----------------------------------------------------------------------------
BETA_URL = "https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls"
RATINGS_URL = "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/ratings.html"
OECD_URL = ("https://www.oecd.org/en/publications/corporate-tax-statistics-2024_9c27d6e8-en/"
            "full-report/statutory-corporate-income-tax-rates_440f9286.html#chapter-d1e2342-08e74a33fb")
TE_URL = "https://tradingeconomics.com/bonds"
HEADERS = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")}

DEFAULT_INDUSTRY = "Software (System & Application)"
DEFAULT_COUNTRY = "United States"

# Offline fallbacks — used ONLY if a live fetch fails. The app labels them clearly.
FALLBACK_BETAS = {"Advertising": 0.9301, "Aerospace/Defense": 0.8467, "Air Transport": 0.7041, "Apparel": 0.7580, "Auto & Truck": 1.2690, "Auto Parts": 1.0217, "Bank (Money Center)": 0.3411, "Banks (Regional)": 0.2865, "Beverage (Alcoholic)": 0.6132, "Beverage (Soft)": 0.5557, "Broadcasting": 0.2864, "Brokerage & Investment Banking": 0.5808, "Building Materials": 0.9302, "Business & Consumer Services": 0.7736, "Cable TV": 0.3524, "Chemical (Basic)": 0.5800, "Chemical (Diversified)": 0.3666, "Chemical (Specialty)": 0.7922, "Coal & Related Energy": 1.0165, "Computer Services": 0.9155, "Computers/Peripherals": 1.3051, "Construction Supplies": 1.0161, "Diversified": 0.7889, "Drugs (Biotechnology)": 1.0341, "Drugs (Pharmaceutical)": 0.8862, "Education": 0.6602, "Electrical Equipment": 1.1478, "Electronics (Consumer & Office)": 0.8299, "Electronics (General)": 0.8974, "Engineering/Construction": 1.0949, "Entertainment": 0.7372, "Environmental & Waste Services": 0.8145, "Farming/Agriculture": 0.8130, "Financial Svcs. (Non-bank & Insurance)": 0.3189, "Food Processing": 0.4574, "Food Wholesalers": 0.6409, "Furn/Home Furnishings": 0.6248, "Green & Renewable Energy": 0.4633, "Healthcare Products": 0.8291, "Healthcare Support Services": 0.6889, "Heathcare Information and Technology": 0.9913, "Homebuilding": 0.7850, "Hospitals/Healthcare Facilities": 0.5517, "Hotel/Gaming": 0.8323, "Household Products": 0.7178, "Information Services": 0.7372, "Insurance (General)": 0.5636, "Insurance (Life)": 0.4272, "Insurance (Prop/Cas.)": 0.4357, "Investments & Asset Management": 0.5297, "Machinery": 0.8680, "Metals & Mining": 0.9636, "Office Equipment & Services": 0.9806, "Oil/Gas (Integrated)": 0.2712, "Oil/Gas (Production and Exploration)": 0.5628, "Oil/Gas Distribution": 0.4651, "Oilfield Svcs/Equip.": 0.7430, "Packaging & Container": 0.7231, "Paper/Forest Products": 0.7216, "Power": 0.3100, "Precious Metals": 0.7932, "Publishing & Newspapers": 0.4773, "R.E.I.T.": 0.3929, "Real Estate (Development)": 0.4783, "Real Estate (General/Diversified)": 0.5779, "Real Estate (Operations & Services)": 0.8149, "Recreation": 0.6951, "Reinsurance": 0.4384, "Restaurant/Dining": 0.7674, "Retail (Automotive)": 0.6984, "Retail (Building Supply)": 1.3070, "Retail (Distributors)": 0.7827, "Retail (General)": 0.7600, "Retail (Grocery and Food)": 0.8048, "Retail (REITs)": 0.4362, "Retail (Special Lines)": 0.9488, "Rubber& Tires": 0.1435, "Semiconductor": 1.4893, "Semiconductor Equip": 1.3481, "Shipbuilding & Marine": 0.6440, "Shoe": 0.9337, "Software (Entertainment)": 1.0128, "Software (Internet)": 1.5461, "Software (System & Application)": 1.2254, "Steel": 0.9035, "Telecom (Wireless)": 0.3873, "Telecom. Equipment": 0.8635, "Telecom. Services": 0.3654, "Tobacco": 0.6776, "Transportation": 0.6753, "Transportation (Railroads)": 0.8069, "Trucking": 0.8504, "Utility (General)": 0.1486, "Utility (Water)": 0.2812, "Total Market": 0.7217, "Total Market (without financials)": 0.8775}
  # Damodaran betas.xls, Jan 2026 update, unlevered beta
FALLBACK_BETA_DATE = "2026-01-05 (offline copy)"

# OECD Corporate Tax Statistics 2024 — combined (central + sub-central) statutory CIT rates, %
FALLBACK_TAX = {
    "United States": 25.6, "Canada": 26.1, "Mexico": 30.0, "Brazil": 34.0, "Argentina": 35.0,
    "Chile": 27.0, "Colombia": 35.0, "Peru": 29.5, "United Kingdom": 25.0, "Germany": 29.9,
    "France": 25.8, "Italy": 27.8, "Spain": 25.0, "Portugal": 31.5, "Netherlands": 25.8,
    "Belgium": 25.0, "Switzerland": 19.6, "Austria": 23.0, "Ireland": 12.5, "Luxembourg": 24.9,
    "Sweden": 20.6, "Norway": 22.0, "Denmark": 22.0, "Finland": 20.0, "Iceland": 20.0,
    "Poland": 19.0, "Czech Republic": 21.0, "Hungary": 9.0, "Greece": 22.0, "Turkey": 25.0,
    "Israel": 23.0, "Japan": 29.7, "South Korea": 26.4, "China": 25.0, "Hong Kong": 16.5,
    "India": 25.2, "Indonesia": 22.0, "Singapore": 17.0, "Australia": 30.0, "New Zealand": 28.0,
    "South Africa": 27.0, "Saudi Arabia": 20.0, "Thailand": 20.0, "Philippines": 25.0,
    "Malaysia": 24.0, "Vietnam": 20.0, "Estonia": 20.0, "Slovakia": 21.0, "Slovenia": 22.0,
}
FALLBACK_TAX_DATE = "2024 (OECD CTS 2024, offline copy)"

FALLBACK_SPREAD = 1.11  # %, Baa2/BBB, large non-financial firms (offline placeholder — verify)

# Name harmonisation between sources
ALIASES = {
    "US": "United States", "USA": "United States", "U.S.": "United States",
    "UK": "United Kingdom", "Britain": "United Kingdom", "Great Britain": "United Kingdom",
    "Korea": "South Korea", "Korea, Republic of": "South Korea", "Republic of Korea": "South Korea",
    "Czechia": "Czech Republic", "Türkiye": "Turkey", "Turkiye": "Turkey",
    "Hong Kong, China": "Hong Kong", "China (People's Republic of)": "China",
    "Slovak Republic": "Slovakia", "Euro Area": "Euro Area",
}


def norm_country(name: str) -> str:
    n = re.sub(r"\s*\d+Y$", "", str(name)).strip()
    return ALIASES.get(n, n)


# ----------------------------------------------------------------------------
# Data fetchers (cached; the Refresh button clears the cache)
# ----------------------------------------------------------------------------
@st.cache_data(ttl=6 * 3600, show_spinner=False)
def fetch_betas():
    try:
        r = requests.get(BETA_URL, headers=HEADERS, timeout=20)
        r.raise_for_status()
        raw = pd.read_excel(io.BytesIO(r.content), sheet_name="Industry Averages", header=None)
        hdr = raw.index[raw.iloc[:, 0].astype(str).str.strip() == "Industry Name"][0]
        date_val = raw.iloc[0, 1]
        df = raw.iloc[hdr + 1:].copy()
        df.columns = [str(c).strip() for c in raw.iloc[hdr]]
        df = df[["Industry Name", "Unlevered beta"]].dropna()
        df["Unlevered beta"] = pd.to_numeric(df["Unlevered beta"], errors="coerce")
        df = df.dropna()
        date = pd.to_datetime(date_val).strftime("%Y-%m-%d") if pd.notna(date_val) else "n/a"
        return dict(zip(df["Industry Name"].str.strip(), df["Unlevered beta"])), date, "live"
    except Exception as e:  # noqa: BLE001
        return FALLBACK_BETAS, FALLBACK_BETA_DATE, f"fallback ({type(e).__name__})"


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def fetch_bbb_spread():
    try:
        r = requests.get(RATINGS_URL, headers=HEADERS, timeout=20)
        r.raise_for_status()
        tables = pd.read_html(io.StringIO(r.text))
        # First table containing Baa2/BBB = large non-financial service firms
        for t in tables:
            flat = t.astype(str)
            mask = flat.apply(lambda col: col.str.contains("Baa2/BBB", regex=False)).any(axis=1)
            if mask.any():
                row = flat[mask].iloc[0].tolist()
                pct = [c for c in row if "%" in c]
                val = float(pct[-1].replace("%", "")) if pct else float(row[-1])
                if val < 0.2:  # given as decimal
                    val *= 100
                m = re.search(r"(January|February|March|April|May|June|July|August|September|"
                              r"October|November|December)\s+\d{4}", r.text)
                return val, (m.group(0) if m else datetime.now().strftime("%Y-%m-%d")), "live"
        raise ValueError("Baa2/BBB row not found")
    except Exception as e:  # noqa: BLE001
        return FALLBACK_SPREAD, "Jan 2026 (offline placeholder)", f"fallback ({type(e).__name__})"


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def fetch_tax_rates():
    try:
        r = requests.get(OECD_URL, headers=HEADERS, timeout=20)
        r.raise_for_status()
        out = {}
        for t in pd.read_html(io.StringIO(r.text)):
            if t.shape[1] < 2:
                continue
            first = t.iloc[:, 0].astype(str)
            nums = t.iloc[:, -1].apply(pd.to_numeric, errors="coerce")
            if nums.notna().sum() > 20:
                for c, v in zip(first, nums):
                    if pd.notna(v) and 0 <= v <= 60:
                        out[norm_country(c)] = float(v)
        if len(out) < 20:
            raise ValueError("table not parsed")
        return out, "2024 (OECD CTS 2024)", "live"
    except Exception as e:  # noqa: BLE001
        return FALLBACK_TAX, FALLBACK_TAX_DATE, f"fallback ({type(e).__name__})"


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_yields():
    try:
        r = requests.get(TE_URL, headers=HEADERS, timeout=20)
        r.raise_for_status()
        out = {}
        for t in pd.read_html(io.StringIO(r.text)):
            cols = [str(c) for c in t.columns]
            ycol = next((c for c in cols if c.strip().lower() == "yield"), None)
            if ycol is None:
                continue
            t.columns = cols
            for name, y in zip(t.iloc[:, 0] if cols[0] != ycol else t.iloc[:, 1], t[ycol]):
                y = pd.to_numeric(y, errors="coerce")
                if pd.notna(y):
                    out.setdefault(norm_country(name), float(y))
        if len(out) < 10:
            raise ValueError("bond table not parsed")
        return out, datetime.now().strftime("%Y-%m-%d %H:%M"), "live"
    except Exception as e:  # noqa: BLE001
        return {}, "unavailable", f"failed ({type(e).__name__}) — enter yields manually"


# ----------------------------------------------------------------------------
# Core math (all rates in decimals)
# ----------------------------------------------------------------------------
def compute(bu, tax, wd, erp, rf_us, rf_f, spread_us, spread_f_override=None):
    we = 1 - wd
    de = wd / we if we > 0 else float("inf")
    bl = bu * (1 + (1 - tax) * de)                          # Hamada relevering
    ke_us = rf_us + bl * erp                                # CAPM in USD
    kd_us = rf_us + spread_us                               # pre-tax USD cost of debt
    parity = (1 + rf_f) / (1 + rf_us)                       # inflation/interest-rate parity factor
    ke_f = (1 + ke_us) * parity - 1                         # foreign-currency cost of equity
    kd_f_auto = (1 + kd_us) * parity - 1
    spread_f_auto = kd_f_auto - rf_f
    spread_f = spread_f_auto if spread_f_override is None else spread_f_override
    kd_f = rf_f + spread_f
    wacc_us = we * ke_us + wd * kd_us * (1 - tax)
    wacc_f = we * ke_f + wd * kd_f * (1 - tax)
    return dict(de=de, bl=bl, ke_us=ke_us, kd_us=kd_us, kd_us_at=kd_us * (1 - tax),
                ke_f=ke_f, kd_f=kd_f, kd_f_at=kd_f * (1 - tax), spread_f_auto=spread_f_auto,
                spread_f=spread_f, wacc_us=wacc_us, wacc_f=wacc_f, parity=parity)


# ----------------------------------------------------------------------------
# Styling
# ----------------------------------------------------------------------------
st.markdown("""
<style>
.block-container {padding-top: 2rem;}
.hero {background: linear-gradient(120deg,#0f2a4a 0%,#1f4e79 60%,#2b6cb0 100%);
       color:#fff;padding:1.4rem 1.8rem;border-radius:14px;margin-bottom:1.2rem;}
.hero h1 {color:#fff;font-size:1.9rem;margin:0;}
.hero p {color:#dbe7f5;margin:.3rem 0 0 0;}
.card {border:1px solid #e3e8ef;border-radius:12px;padding:1rem 1.2rem;background:#fafcff;}
.card h3 {margin-top:0;font-size:1.1rem;color:#1f4e79;}
.big {font-size:2.1rem;font-weight:700;color:#0f2a4a;}
.lbl {color:#6b7a90;font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;}
.src {font-size:.8rem;color:#6b7a90;}
.ok {color:#1a7f37;font-weight:600;} .warn {color:#b35900;font-weight:600;}
</style>""", unsafe_allow_html=True)

st.markdown("""<div class="hero"><h1>🌐 International Cost of Capital</h1>
<p>Translate a project's cost of equity, cost of debt and WACC from U.S. dollars into any
country's currency — using live industry betas, credit spreads, tax rates and government bond yields.</p>
</div>""", unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# Load data
# ----------------------------------------------------------------------------
with st.spinner("Fetching latest market data…"):
    betas, beta_date, beta_status = fetch_betas()
    spread_live, spread_date, spread_status = fetch_bbb_spread()
    taxes, tax_date, tax_status = fetch_tax_rates()
    yields, yld_date, yld_status = fetch_yields()

countries = sorted(set(taxes) | set(yields) | {DEFAULT_COUNTRY})

# ----------------------------------------------------------------------------
# Sidebar inputs
# ----------------------------------------------------------------------------
sb = st.sidebar
sb.header("⚙️ Project setup")
if sb.button("🔄 Refresh data", width="stretch", help="Clear the cache and re-fetch all sources"):
    st.cache_data.clear()
    st.rerun()

industries = list(betas.keys())
industry = sb.selectbox("Industry", industries,
                        index=industries.index(DEFAULT_INDUSTRY) if DEFAULT_INDUSTRY in industries else 0)
country = sb.selectbox("Target country", countries, index=countries.index(DEFAULT_COUNTRY))

erp = sb.slider("Equity risk premium (%)", 2.0, 12.0, 6.5, 0.1,
                help="Mature-market (U.S.) ERP applied to the levered beta") / 100
wd = sb.slider("Target debt share D/(D+E) (%)", 0, 90, 30, 1,
               help="Project's target debt weight in the capital structure") / 100
tax_choice = sb.radio("Project tax rate", ["U.S.", "Selected country"], horizontal=True,
                      help="One tax rate is used for relevering beta and the debt tax shield in BOTH currencies")

sb.divider()
sb.subheader("✍️ Manual overrides")
sb.caption("Toggle on to replace a fetched value with your own.")

def override(label, key, auto_val, fmt_step=0.01, help_txt=None):
    on = sb.toggle(f"Override {label}", key=f"on_{key}", help=help_txt)
    if on:
        return sb.number_input(label, value=float(round(auto_val, 4)), step=fmt_step, key=f"v_{key}"), True
    return auto_val, False

bu_auto = float(betas[industry])
bu, bu_ovr = override("unlevered beta", "bu", bu_auto, 0.01)

us_tax_auto = taxes.get("United States", FALLBACK_TAX["United States"])
f_tax_auto = taxes.get(country, FALLBACK_TAX.get(country, us_tax_auto))
us_tax, us_tax_ovr = override("U.S. tax rate (%)", "ust", us_tax_auto, 0.1)
f_tax, f_tax_ovr = override(f"{country} tax rate (%)", "ft", f_tax_auto, 0.1)

spread_us, spread_ovr = override("USD BBB spread (%)", "sp", spread_live, 0.01)

rf_us_auto = yields.get("United States", float("nan"))
rf_f_auto = yields.get(country, float("nan"))
yld_missing = pd.isna(rf_us_auto) or pd.isna(rf_f_auto)
if yld_missing:
    sb.warning("Live yields unavailable for this pair — enter them below.")
    rf_us = sb.number_input("U.S. 10Y yield (%)", value=4.10 if pd.isna(rf_us_auto) else rf_us_auto, step=0.01)
    rf_f = sb.number_input(f"{country} 10Y yield (%)",
                           value=(rf_us if country == "United States" else 4.00) if pd.isna(rf_f_auto) else rf_f_auto,
                           step=0.01)
    rf_us_ovr = rf_f_ovr = True
else:
    rf_us, rf_us_ovr = override("U.S. 10Y yield (%)", "rfu", rf_us_auto, 0.01)
    rf_f, rf_f_ovr = override(f"{country} 10Y yield (%)", "rff", rf_f_auto, 0.01)

sf_on = sb.toggle(f"Override {country} BBB spread", key="on_sf",
                  help="Off = spread implied by parity from the USD cost of debt. On = your own local-currency spread.")

tax = (us_tax if tax_choice == "U.S." else f_tax) / 100

# preliminary run to get the auto foreign spread for the input default
pre = compute(bu, tax, wd, erp, rf_us / 100, rf_f / 100, spread_us / 100)
if sf_on:
    sf_val = sb.number_input(f"{country} BBB spread (%)", value=float(round(pre["spread_f_auto"] * 100, 3)),
                             step=0.01) / 100
    res = compute(bu, tax, wd, erp, rf_us / 100, rf_f / 100, spread_us / 100, sf_val)
else:
    res = pre
    sb.caption(f"Auto {country} spread: **{pre['spread_f_auto']*100:.3f}%**")

cur = "Local currency" if country != "United States" else "USD (same country)"

# ----------------------------------------------------------------------------
# Tabs
# ----------------------------------------------------------------------------
t1, t2, t3, t4, t5 = st.tabs(["📊 Results", "🧮 How it's calculated", "🏭 All-industry comparison",
                              "✅ Verification", "📚 Data sources"])

def pct(x, d=2):
    return f"{x*100:.{d}f}%"

with t1:
    st.markdown(f"**{industry}** project in **{country}** · ERP {pct(erp,1)} · Debt {pct(wd,0)} · "
                f"Tax {pct(tax,1)} ({tax_choice})")
    c1, c2 = st.columns(2)
    for col, title, ke, kd, kdat, wacc, rf, spr in [
        (c1, "🇺🇸 U.S. dollars", res["ke_us"], res["kd_us"], res["kd_us_at"], res["wacc_us"], rf_us/100, spread_us/100),
        (c2, f"🌍 {country} — {cur}", res["ke_f"], res["kd_f"], res["kd_f_at"], res["wacc_f"], rf_f/100, res["spread_f"]),
    ]:
        with col:
            st.markdown(f"""<div class="card"><h3>{title}</h3>
            <div class="lbl">WACC</div><div class="big">{pct(wacc)}</div>
            <table style="width:100%;margin-top:.6rem">
            <tr><td>10Y government yield</td><td style="text-align:right">{pct(rf)}</td></tr>
            <tr><td>Cost of equity</td><td style="text-align:right"><b>{pct(ke)}</b></td></tr>
            <tr><td>BBB spread</td><td style="text-align:right">{pct(spr,3)}</td></tr>
            <tr><td>Pre-tax cost of debt</td><td style="text-align:right">{pct(kd)}</td></tr>
            <tr><td>After-tax cost of debt</td><td style="text-align:right"><b>{pct(kdat)}</b></td></tr>
            </table></div>""", unsafe_allow_html=True)

    st.write("")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Unlevered beta", f"{bu:.3f}", "manual" if bu_ovr else None, delta_color="off")
    m2.metric("Levered beta", f"{res['bl']:.3f}")
    m3.metric("D/E ratio", f"{res['de']:.3f}" if res['de'] != float('inf') else "∞")
    m4.metric("WACC gap (local − USD)", pct(res["wacc_f"] - res["wacc_us"]),
              help="Driven by the gap between the two government bond yields")

    comp = pd.DataFrame({
        "Component": ["Cost of equity", "After-tax cost of debt", "WACC"] * 2,
        "Currency": ["USD"] * 3 + [country] * 3,
        "Rate": [res["ke_us"], res["kd_us_at"], res["wacc_us"], res["ke_f"], res["kd_f_at"], res["wacc_f"]],
    })
    chart = alt.Chart(comp).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
        x=alt.X("Component:N", title=None, sort=["Cost of equity", "After-tax cost of debt", "WACC"]),
        xOffset="Currency:N",
        y=alt.Y("Rate:Q", axis=alt.Axis(format="%"), title=None),
        color=alt.Color("Currency:N", scale=alt.Scale(range=["#1f4e79", "#e07a1f"]), legend=alt.Legend(orient="top")),
        tooltip=["Currency", "Component", alt.Tooltip("Rate:Q", format=".2%")],
    ).properties(height=320)
    st.altair_chart(chart, width="stretch")

    out = pd.DataFrame({
        "Item": ["Industry", "Country", "Unlevered beta", "Levered beta", "Tax rate used", "Debt share",
                 "Equity risk premium", "10Y yield", "BBB spread", "Cost of equity", "Pre-tax cost of debt",
                 "After-tax cost of debt", "WACC"],
        "USD": [industry, "United States", bu, res["bl"], tax, wd, erp, rf_us/100, spread_us/100,
                res["ke_us"], res["kd_us"], res["kd_us_at"], res["wacc_us"]],
        country: [industry, country, bu, res["bl"], tax, wd, erp, rf_f/100, res["spread_f"],
                  res["ke_f"], res["kd_f"], res["kd_f_at"], res["wacc_f"]],
    })
    st.download_button("⬇️ Download results (CSV)", out.to_csv(index=False).encode(),
                       f"cost_of_capital_{country.replace(' ','_')}.csv", "text/csv")

with t2:
    st.subheader("What the app is calculating")
    st.markdown("Every number flows from five inputs: the **unlevered beta**, the **debt share**, the **tax rate**, "
                "the **equity risk premium**, and the **two 10-year government yields** (plus the BBB spread).")
    st.markdown("**1 · Relever the industry beta to the project's capital structure (Hamada)**")
    st.latex(r"\beta_L=\beta_U\left[1+(1-t)\frac{D}{E}\right]")
    st.caption(f"= {bu:.3f} × [1 + (1 − {tax:.3f}) × {res['de']:.3f}] = **{res['bl']:.3f}**")
    st.markdown("**2 · USD cost of equity (CAPM) and cost of debt**")
    st.latex(r"k_e^{USD}=r_f^{US}+\beta_L\times ERP \qquad k_d^{USD}=r_f^{US}+s_{BBB}")
    st.caption(f"k_e = {pct(rf_us/100)} + {res['bl']:.3f} × {pct(erp,1)} = **{pct(res['ke_us'])}**   ·   "
               f"k_d = {pct(rf_us/100)} + {pct(spread_us/100,3)} = **{pct(res['kd_us'])}**")
    st.markdown("**3 · Convert to the foreign currency with the yield (inflation) differential**")
    st.latex(r"k^{F}=(1+k^{USD})\times\frac{1+r_f^{F}}{1+r_f^{US}}-1")
    st.caption(f"Parity factor (1+{pct(rf_f/100)})/(1+{pct(rf_us/100)}) = **{res['parity']:.5f}**  →  "
               f"k_e^F = **{pct(res['ke_f'])}**")
    st.markdown("**4 · Foreign BBB spread** — auto mode backs it out of the converted cost of debt; "
                "override mode uses your number directly:")
    st.latex(r"s^{F}_{auto}=(1+k_d^{USD})\frac{1+r_f^{F}}{1+r_f^{US}}-1-r_f^{F}\qquad k_d^{F}=r_f^{F}+s^{F}")
    st.caption(f"Auto spread = **{pct(res['spread_f_auto'],3)}**; spread used = **{pct(res['spread_f'],3)}**")
    st.markdown("**5 · WACC in each currency**")
    st.latex(r"WACC=\frac{E}{V}k_e+\frac{D}{V}k_d(1-t)")
    st.caption(f"USD: {pct(1-wd,0)}×{pct(res['ke_us'])} + {pct(wd,0)}×{pct(res['kd_us'])}×(1−{tax:.3f}) = "
               f"**{pct(res['wacc_us'])}**   ·   {country}: **{pct(res['wacc_f'])}**")
    st.info("**Key assumptions** — (1) Damodaran's U.S. unlevered industry beta applies to the project wherever "
            "it is located; (2) the ERP is a mature-market USD premium (no separate country risk premium is added); "
            "(3) the difference in 10-year government yields captures expected inflation differences, so costs are "
            "converted by relative interest-rate parity; (4) a single project tax rate is used in both currencies; "
            "(5) the project borrows at a BBB rating.")

with t3:
    st.subheader("Every industry, same country & assumptions")
    rows = []
    for ind, b in betas.items():
        r = compute(float(b), tax, wd, erp, rf_us/100, rf_f/100, spread_us/100,
                    res["spread_f"] if sf_on else None)
        rows.append({"Industry": ind, "Unlevered beta": float(b), "Levered beta": r["bl"],
                     "Cost of equity (USD)": r["ke_us"], f"Cost of equity ({country})": r["ke_f"],
                     "WACC (USD)": r["wacc_us"], f"WACC ({country})": r["wacc_f"]})
    allind = pd.DataFrame(rows).sort_values("WACC (USD)", ascending=False)
    hl = alt.condition(alt.datum.Industry == industry, alt.value("#e07a1f"), alt.value("#1f4e79"))
    bar = alt.Chart(allind).mark_bar().encode(
        y=alt.Y("Industry:N", sort="-x", title=None),
        x=alt.X(f"WACC ({country}):Q", axis=alt.Axis(format="%"), title=f"WACC ({country})"),
        color=hl, tooltip=["Industry", alt.Tooltip("Unlevered beta:Q", format=".3f"),
                           alt.Tooltip("WACC (USD):Q", format=".2%"),
                           alt.Tooltip(f"WACC ({country}):Q", format=".2%")],
    ).properties(height=max(400, 14 * len(allind)))
    cA, cB = st.columns([3, 2])
    cA.altair_chart(bar, width="stretch")
    fmt = {c: "{:.2%}" for c in allind.columns if "Cost" in c or "WACC" in c}
    fmt.update({"Unlevered beta": "{:.3f}", "Levered beta": "{:.3f}"})
    cB.dataframe(allind.style.format(fmt), width="stretch", height=600, hide_index=True)
    st.download_button("⬇️ Download all-industry table (CSV)", allind.to_csv(index=False).encode(),
                       "all_industries.csv", "text/csv")

with t4:
    st.subheader("Built-in sanity checks")
    st.caption("Run on the current inputs. These are the checks required by the assignment.")
    a = compute(bu, tax, wd, erp, rf_us/100, rf_us/100, spread_us/100)
    chk1 = abs(a["ke_f"] - a["ke_us"]) < 1e-12 and abs(a["wacc_f"] - a["wacc_us"]) < 1e-12
    z = compute(bu, tax, 0.0, erp, rf_us/100, rf_f/100, spread_us/100)
    chk2 = abs(z["wacc_us"] - z["ke_us"]) < 1e-12 and abs(z["wacc_f"] - z["ke_f"]) < 1e-12
    o = compute(bu, tax, wd, erp, rf_us/100, rf_f/100, spread_us/100, 0.10)
    chk3 = all(abs(o[k] - pre[k]) < 1e-12 for k in ["ke_us", "kd_us", "wacc_us"])
    for ok, name, detail in [
        (chk1, "Equal government yields → equal USD and local results",
         f"With both yields at {pct(rf_us/100)}: WACC USD {pct(a['wacc_us'],4)} vs local {pct(a['wacc_f'],4)}"),
        (chk2, "Zero debt → WACC equals cost of equity",
         f"USD: WACC {pct(z['wacc_us'],4)} = k_e {pct(z['ke_us'],4)}"),
        (chk3, "Overriding the foreign spread leaves USD results unchanged",
         f"Foreign spread forced to 10%: USD WACC {pct(o['wacc_us'],4)} vs {pct(pre['wacc_us'],4)}"),
    ]:
        st.markdown(f"<span class='{'ok' if ok else 'warn'}'>{'✅ PASS' if ok else '❌ FAIL'}</span> "
                    f"&nbsp;**{name}** — {detail}", unsafe_allow_html=True)
    st.divider()
    st.markdown("**Hand-check worksheet** (reproduce these in a spreadsheet):")
    st.dataframe(pd.DataFrame({
        "Step": ["β_U", "D/E", "β_L", "k_e USD", "k_d USD", "Parity factor", "k_e local", "k_d local",
                 "WACC USD", "WACC local"],
        "Value": [f"{bu:.4f}", f"{res['de']:.4f}", f"{res['bl']:.4f}", pct(res['ke_us'], 4), pct(res['kd_us'], 4),
                  f"{res['parity']:.6f}", pct(res['ke_f'], 4), pct(res['kd_f'], 4),
                  pct(res['wacc_us'], 4), pct(res['wacc_f'], 4)],
    }), hide_index=True, width="stretch")

with t5:
    st.subheader("Where the data comes from")
    def badge(status):
        return "<span class='ok'>● live</span>" if status == "live" else f"<span class='warn'>● {status}</span>"
    src = [
        ("Industry unlevered betas", "Aswath Damodaran (NYU Stern) — betas.xls", BETA_URL, beta_date, beta_status),
        ("BBB (Baa2) USD spread", "Damodaran — ratings.html, large non-financial firms", RATINGS_URL, spread_date, spread_status),
        ("Statutory corporate tax rates", "OECD Corporate Tax Statistics 2024", OECD_URL, tax_date, tax_status),
        ("10-year government yields", "Trading Economics — bonds", TE_URL, yld_date, yld_status),
    ]
    for name, who, url, date, status in src:
        st.markdown(f"**{name}** &nbsp; {badge(status)}<br><span class='src'>{who} · as of {date} · "
                    f"<a href='{url}' target='_blank'>source</a></span>", unsafe_allow_html=True)
    st.caption(f"Session loaded {datetime.now().strftime('%Y-%m-%d %H:%M')}. Click **Refresh data** in the "
               "sidebar to re-fetch. If a source is shown as fallback, an embedded copy is used and you can "
               "override the value manually in the sidebar.")
    st.markdown("**Values in use**")
    st.dataframe(pd.DataFrame({
        "Input": ["Unlevered beta", "U.S. tax rate", f"{country} tax rate", "USD BBB spread",
                  "U.S. 10Y yield", f"{country} 10Y yield"],
        "Value": [f"{bu:.4f}", f"{us_tax:.2f}%", f"{f_tax:.2f}%", f"{spread_us:.3f}%", f"{rf_us:.3f}%", f"{rf_f:.3f}%"],
        "Origin": ["manual" if bu_ovr else "fetched", "manual" if us_tax_ovr else "fetched",
                   "manual" if f_tax_ovr else "fetched", "manual" if spread_ovr else "fetched",
                   "manual" if rf_us_ovr else "fetched", "manual" if rf_f_ovr else "fetched"],
    }), hide_index=True, width="stretch")
