
# ========= Custom Streamlit Page Config =========
import streamlit as st

st.set_page_config(
    page_title="Volatility Screener Dashboard 🚀",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

from PIL import Image

# Load and display logo
logo = Image.open("logo.png")
st.image(logo, width=250)

EMAIL_ADDRESS = st.secrets["email"]["address"]
EMAIL_PASSWORD = st.secrets["email"]["password"]
RECIPIENT_EMAIL = st.secrets["email"]["recipient"]


# volatility_dashboard.py

import pandas as pd
import matplotlib.pyplot as plt

from polygon_data import (
    create_client,
    get_historical_volatility,
    get_ticker_snapshot,
    load_polygon_api_key,
)


import smtplib
from email.message import EmailMessage

def send_email_report_html(df_filtered):
    if df_filtered.empty:
        return "No data to email."

    # Build HTML table
    top_trades = df_filtered[['Ticker', 'CurrentPrice', 'Call_IV_Premium', 'Put_IV_Premium', 'IV_Skew', 'Strategy']]
    html_table = top_trades.to_html(index=False, border=0, justify='center')

    html_content = f"""
    <html>
        <body style="font-family: Arial; background-color: #f9f9f9; padding: 20px;">
            <h2 style="color: #333;">📈 Volatility Screener - Top Trades</h2>
            {html_table}
            <p style="font-size: 12px; color: #999;">Sent automatically by your Screener Bot 🤖</p>
        </body>
    </html>
    """

    msg = EmailMessage()
    msg['Subject'] = '📈 Volatility Screener – Trade Alerts'
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = RECIPIENT_EMAIL
    msg.set_content("This is an HTML email. Please view it in an email client that supports HTML.")
    msg.add_alternative(html_content, subtype='html')

    # Send
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)

    return "✅ HTML Email sent successfully!"


# ========== Data Fetcher (Big Tickers + Sector) ==========

try:
    POLYGON_API_KEY = load_polygon_api_key()
except ValueError as error:
    st.error(str(error))
    st.stop()


@st.cache_resource
def get_polygon_client():
    return create_client(POLYGON_API_KEY)


@st.cache_data
def fetch_stock_data():
    client = get_polygon_client()
    tickers = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "GOOG", "META", "TSLA", "BRK.B", "AVGO",
    "WMT", "LLY", "JPM", "V", "MA", "XOM", "NFLX", "COST", "UNH", "ORCL",
    "HD", "MRK", "PEP", "KO", "INTC", "CSCO", "CVX", "TMO", "ABT", "MCD",
    "CRM", "ACN", "TXN", "NEE", "NKE", "LIN", "AMD", "QCOM", "PM", "UPS",
    "MDT", "HON", "AMGN", "IBM", "BA", "CAT", "GS", "SBUX", "ISRG", "BLK",
    "NOW", "BKNG", "LRCX", "ADI", "VRTX", "GILD", "ADBE", "PANW", "ASML", "INTU",
    "PYPL", "REGN", "MU", "KLAC", "SNPS", "CDNS", "MRVL", "NXPI", "FTNT", "AEP",
    "EXC", "ORLY", "CHTR", "ROST", "BIIB", "DXCM", "TEAM", "WDAY", "CTAS", "DDOG",
    "PCAR", "ANSS", "XEL", "SIRI", "CEG", "LCID", "WBD", "SGEN", "VRSK", "FAST",
    "ZS", "VRSN", "PAYX", "BIDU", "MTCH", "ALGN", "ZM", "JD", "ILMN", "LULU",
    "DOCU", "ENPH", "OKTA", "PCTY", "MDB", "CRSP"
]

    results = []
    
    for ticker in tickers:
        snapshot = get_ticker_snapshot(client, ticker)
        if snapshot:
            results.append(snapshot)

    df = pd.DataFrame(results)
    return df

# ========== App Interface ==========

st.title("📈 Advanced Volatility Screener Dashboard")
st.caption("Built with Streamlit + Polygon.io")

df = fetch_stock_data()

if df.empty:
    st.error(
        "No ticker data was retrieved from Polygon. Please verify your API key and "
        "plan permissions, then try again."
    )
    st.stop()

required_columns = {
    "Ticker",
    "Call_IV_Premium",
    "Put_IV_Premium",
    "IV_Skew",
    "AvgCallIV",
    "AvgPutIV",
    "CurrentPrice",
}

missing_columns = sorted(required_columns.difference(df.columns))
if missing_columns:
    st.error(
        "The Polygon response was missing required fields: "
        f"{', '.join(missing_columns)}. Please try again later."
    )
    st.stop()

if "Sector" not in df.columns:
    df["Sector"] = "Unknown"

st.sidebar.header("Filters")
min_premium = st.sidebar.slider("Minimum IV Premium", 1.0, 3.0, 1.5, step=0.1)
top_n = st.sidebar.slider("Top N stocks", 5, 20, 10)

sector_filter = st.sidebar.multiselect(
    "Sector Filter",
    options=["All"] + sorted(df["Sector"].dropna().unique().tolist()),
    default=["All"]
)

focus_option = st.sidebar.radio(
    "Focus on:",
    options=["Call Premium", "Put Premium"]
)

# Apply Sector Filter
if "All" not in sector_filter:
    df = df[df['Sector'].isin(sector_filter)]

# Apply Premium Filter
if focus_option == "Call Premium":
    df_filtered = df[df['Call_IV_Premium'] >= min_premium].copy()
    df_filtered = df_filtered.sort_values(by="Call_IV_Premium", ascending=False).head(top_n)
else:
    df_filtered = df[df['Put_IV_Premium'] >= min_premium].copy()
    df_filtered = df_filtered.sort_values(by="Put_IV_Premium", ascending=False).head(top_n)

st.subheader(f"Top {focus_option} Opportunities")
st.dataframe(df_filtered)

# Download CSV
st.download_button(
    label="Download data as CSV",
    data=df_filtered.to_csv(index=False).encode('utf-8'),
    file_name='screener_results.csv',
    mime='text/csv',
)

# ========== Volatility Chart (Click-to-View) ==========

st.subheader("📈 Volatility Over Time (Click to View)")

tickers_available = df_filtered['Ticker'].tolist()

selected_ticker = st.selectbox(
    "Select a stock to view its Historical Volatility vs Implied Volatility",
    options=["None"] + tickers_available
)

if selected_ticker != "None":
    try:
        client = get_polygon_client()
        hist, _ = get_historical_volatility(client, selected_ticker, days=365, window=20)
        hist = hist.dropna(subset=["HV_20d"])

        row = df_filtered[df_filtered['Ticker'] == selected_ticker]
        avg_call_iv = row['AvgCallIV'].iloc[0] if not row.empty else None
        avg_put_iv = row['AvgPutIV'].iloc[0] if not row.empty else None

        if hist.empty:
            st.warning("Not enough historical data to chart this ticker.")
        else:
            fig, ax1 = plt.subplots(figsize=(10, 5))
            ax1.plot(hist.index, hist['HV_20d'], label="20d Historical Volatility", color='blue')
            if avg_call_iv:
                ax1.axhline(y=avg_call_iv, linestyle='--', color='green', label="Avg Call IV (current)")
            if avg_put_iv:
                ax1.axhline(y=avg_put_iv, linestyle='--', color='red', label="Avg Put IV (current)")

            ax1.set_ylabel("Volatility (Annualized)")
            ax1.set_title(f"{selected_ticker} Volatility: HV vs IV")
            ax1.legend()
            st.pyplot(fig)

    except Exception as e:
        st.error(f"Could not load chart: {e}")

# ========== Auto Strategy Recommender ==========

st.subheader("🧠 Strategy Recommendations (Aggressive Mode)")

def recommend_strategy(row):
    try:
        call_premium = row['Call_IV_Premium']
        put_premium = row['Put_IV_Premium']
        skew = row['IV_Skew']

        if call_premium > 2.0 and put_premium > 2.0:
            return "Sell Straddle"
        elif put_premium > 1.8 and skew > 0.10:
            return "Sell Cash-Secured Put"
        elif call_premium > 1.8 and skew < -0.10:
            return "Sell Covered Call"
        elif put_premium > 1.5 and call_premium > 1.5:
            return "Buy Straddle"
        elif put_premium > 1.5:
            return "Buy Put Spread"
        elif call_premium > 1.5:
            return "Buy Call Spread"
        else:
            return "Hold"
    except:
        return "Hold"

df_filtered['Strategy'] = df_filtered.apply(recommend_strategy, axis=1)
st.dataframe(df_filtered[['Ticker', 'Sector', 'CurrentPrice', 'Call_IV_Premium', 'Put_IV_Premium', 'IV_Skew', 'Strategy']])

# ========== Dynamic Volatility Reversion Backtest ==========

st.subheader("🔎 Volatility Reversion Backtest (Dynamic Exit)")

def dynamic_backtest(selected_tickers, df_source):
    results = []
    client = get_polygon_client()
    for ticker in selected_tickers:
        try:
            hist, _ = get_historical_volatility(client, ticker, days=180, window=20)
            hist = hist.dropna(subset=["HV_20d"])

            if hist.empty or len(hist) < 30:
                continue

            row = df_source[df_source['Ticker'] == ticker]
            if row.empty:
                continue

            entry_call_iv = row['AvgCallIV'].iloc[0]
            entry_put_iv = row['AvgPutIV'].iloc[0]
            if pd.isna(entry_call_iv) or pd.isna(entry_put_iv):
                continue

            avg_iv = (entry_call_iv + entry_put_iv) / 2
            if avg_iv <= 0:
                continue

            entry_hv = hist['HV_20d'].iloc[0]
            exit_day = None
            for i in range(1, len(hist)):
                hv_now = hist['HV_20d'].iloc[i]
                iv_gap_now = abs(avg_iv - hv_now) / avg_iv

                if iv_gap_now <= 0.10:
                    exit_day = hist.index[i]
                    break

            if exit_day is None:
                exit_day = hist.index[min(30, len(hist)-1)]

            exit_hv = hist.loc[exit_day, 'HV_20d']

            vol_compression = (avg_iv - exit_hv) / avg_iv
            pnl = vol_compression * 100

            results.append({
                "Ticker": ticker,
                "EntryDate": hist.index[0].date(),
                "ExitDate": exit_day.date(),
                "EntryIV": avg_iv,
                "ExitHV": exit_hv,
                "VolCompression": vol_compression,
                "PnL (%)": round(pnl, 2)
            })

        except Exception as e:
            print(f"Backtest error for {ticker}: {e}")

    return pd.DataFrame(results)

selected_backtest_tickers = df_filtered['Ticker'].tolist()

if st.button("Run Dynamic Volatility Backtest"):
    backtest_results = dynamic_backtest(selected_backtest_tickers, df_filtered)
    st.subheader("📈 Backtest Results (Dynamic Exit)")
    st.dataframe(backtest_results)
    
    if not backtest_results.empty:
        avg_pnl = backtest_results['PnL (%)'].mean()
        st.success(f"Average PnL across trades: {avg_pnl:.2f}%")

st.subheader("📬 Test Email Sending")

if st.button("Send Test Email"):
    result = send_email_report_html(df_filtered)
    st.success(result)
