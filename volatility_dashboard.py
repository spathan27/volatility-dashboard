
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

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import matplotlib.pyplot as plt


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

@st.cache_data
def fetch_stock_data():
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
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            sector = info.get('sector', 'Unknown')
            market_cap = info.get('marketCap', 0)
            current_price = info.get('regularMarketPrice', None)

            if market_cap is None or market_cap < 5e9:
                continue  # Skip small caps

            hist = stock.history(period="1y")
            if hist.empty:
                continue
            hist['log_return'] = np.log(hist['Close'] / hist['Close'].shift(1))
            hist['HV_20d'] = hist['log_return'].rolling(window=20).std() * np.sqrt(252)

            today = datetime.today()
            valid_expiries = [date for date in stock.options if (datetime.strptime(date, "%Y-%m-%d") - today).days >= 7]
            if not valid_expiries:
                continue

            next_expiry = valid_expiries[0]
            chain = stock.option_chain(next_expiry)
            calls = chain.calls
            puts = chain.puts

            if calls.empty or puts.empty:
                continue

            otm_calls = calls[(calls['strike'] > current_price) & (calls['volume'] > 0) & (calls['openInterest'] > 0)]
            otm_puts = puts[(puts['strike'] < current_price) & (puts['volume'] > 0) & (puts['openInterest'] > 0)]

            if otm_calls.empty or otm_puts.empty:
                continue

            avg_call_iv = otm_calls['impliedVolatility'].mean()
            avg_put_iv = otm_puts['impliedVolatility'].mean()

            results.append({
                "Ticker": ticker,
                "Sector": sector,
                "MarketCap": market_cap,
                "CurrentPrice": current_price,
                "HistVol": hist['HV_20d'].iloc[-1],
                "AvgCallIV": avg_call_iv,
                "AvgPutIV": avg_put_iv,
                "Call_IV_Premium": avg_call_iv / hist['HV_20d'].iloc[-1] if hist['HV_20d'].iloc[-1] else None,
                "Put_IV_Premium": avg_put_iv / hist['HV_20d'].iloc[-1] if hist['HV_20d'].iloc[-1] else None,
                "IV_Skew": avg_put_iv - avg_call_iv
            })
        
        except Exception as e:
            print(f"Error processing {ticker}: {e}")

    df = pd.DataFrame(results)
    return df

# ========== App Interface ==========

st.title("📈 Advanced Volatility Screener Dashboard")
st.caption("Built with Streamlit + Yahoo Finance")

df = fetch_stock_data()

if df.empty:
    st.warning(
        "We couldn't load any data from Yahoo Finance right now. Please try again shortly."
    )
    st.stop()

st.sidebar.header("Filters")
min_premium = st.sidebar.slider("Minimum IV Premium", 1.0, 3.0, 1.5, step=0.1)
top_n = st.sidebar.slider("Top N stocks", 5, 20, 10)

sector_options = sorted(set(df['Sector'].dropna()))
sector_filter = st.sidebar.multiselect(
    "Sector Filter",
    options=["All"] + sector_options,
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
    df_filtered = df[df['Call_IV_Premium'] >= min_premium]
    df_filtered = df_filtered.sort_values(by="Call_IV_Premium", ascending=False).head(top_n)
else:
    df_filtered = df[df['Put_IV_Premium'] >= min_premium]
    df_filtered = df_filtered.sort_values(by="Put_IV_Premium", ascending=False).head(top_n)

df_filtered = df_filtered.copy()

if df_filtered.empty:
    st.info("No tickers met the current filter criteria. Try adjusting the sliders.")
    st.stop()

st.subheader(f"Top {focus_option} Opportunities")
st.dataframe(df_filtered)


def _safe_idxmax(series: pd.Series):
    cleaned = series.replace([np.inf, -np.inf], np.nan).dropna()
    if cleaned.empty:
        return None
    return cleaned.idxmax()


def generate_textual_insights(df_insights: pd.DataFrame):
    insights = []

    call_idx = _safe_idxmax(df_insights['Call_IV_Premium'])
    if call_idx is not None:
        row = df_insights.loc[call_idx]
        insights.append(
            f"**{row['Ticker']}** shows the richest call premium at {row['Call_IV_Premium']:.2f}× its historical volatility."
        )

    put_idx = _safe_idxmax(df_insights['Put_IV_Premium'])
    if put_idx is not None:
        row = df_insights.loc[put_idx]
        insights.append(
            f"**{row['Ticker']}** has the most elevated put premium, {row['Put_IV_Premium']:.2f}× vs. history."
        )

    skew_idx = _safe_idxmax(df_insights['IV_Skew'].abs())
    if skew_idx is not None:
        row = df_insights.loc[skew_idx]
        direction = "puts" if row['IV_Skew'] > 0 else "calls"
        insights.append(
            f"**{row['Ticker']}** shows the strongest skew favouring {direction} (skew {row['IV_Skew']:+.2f})."
        )

    return insights


st.subheader("🔍 Key Insights")
insight_cols = st.columns(3)

metrics = {
    "Avg Call Premium": df_filtered['Call_IV_Premium'].replace([np.inf, -np.inf], np.nan).mean(),
    "Avg Put Premium": df_filtered['Put_IV_Premium'].replace([np.inf, -np.inf], np.nan).mean(),
    "Avg IV Skew": df_filtered['IV_Skew'].replace([np.inf, -np.inf], np.nan).mean(),
}

for (label, value), col in zip(metrics.items(), insight_cols):
    if pd.isna(value):
        col.metric(label, "–")
    else:
        col.metric(label, f"{value:.2f}")

for insight in generate_textual_insights(df_filtered):
    st.markdown(f"- {insight}")

sector_summary = (
    df_filtered
    .groupby('Sector')[['Call_IV_Premium', 'Put_IV_Premium', 'IV_Skew']]
    .mean()
    .reset_index()
    .sort_values(by='Call_IV_Premium', ascending=False)
)

if not sector_summary.empty:
    st.subheader("🏭 Sector-Level Premium Averages")
    st.dataframe(
        sector_summary.style.format({
            'Call_IV_Premium': '{:.2f}',
            'Put_IV_Premium': '{:.2f}',
            'IV_Skew': '{:+.2f}'
        })
    )

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
        stock = yf.Ticker(selected_ticker)

        hist = stock.history(period="1y")
        hist['log_return'] = np.log(hist['Close'] / hist['Close'].shift(1))
        hist['HV_20d'] = hist['log_return'].rolling(window=20).std() * np.sqrt(252)

        today = datetime.today()
        valid_expiries = [date for date in stock.options if (datetime.strptime(date, "%Y-%m-%d") - today).days >= 7]
        avg_call_iv, avg_put_iv = None, None
        if valid_expiries:
            expiry = valid_expiries[0]
            chain = stock.option_chain(expiry)
            calls = chain.calls
            puts = chain.puts
            avg_call_iv = calls['impliedVolatility'].mean()
            avg_put_iv = puts['impliedVolatility'].mean()

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
        plt.close(fig)

    except Exception as e:
        st.error(f"Could not load chart: {e}")

# ========== Premium Dispersion Chart ==========

st.subheader("🛰️ Premium Dispersion Snapshot")

fig_dispersion, ax_dispersion = plt.subplots(figsize=(8, 5))
scatter = ax_dispersion.scatter(
    df_filtered['Call_IV_Premium'],
    df_filtered['Put_IV_Premium'],
    c=df_filtered['IV_Skew'],
    cmap='coolwarm',
    edgecolor='k'
)
ax_dispersion.set_xlabel('Call IV Premium')
ax_dispersion.set_ylabel('Put IV Premium')
ax_dispersion.set_title('Call vs. Put IV Premium (colour = skew)')
colorbar = fig_dispersion.colorbar(scatter, ax=ax_dispersion)
colorbar.set_label('IV Skew')
for _, row in df_filtered.iterrows():
    ax_dispersion.annotate(
        row['Ticker'],
        (row['Call_IV_Premium'], row['Put_IV_Premium']),
        fontsize=8,
        alpha=0.7
    )

st.pyplot(fig_dispersion)
plt.close(fig_dispersion)

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

def dynamic_backtest(selected_tickers):
    results = []
    for ticker in selected_tickers:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="6mo")

            if hist.empty or len(hist) < 30:
                continue

            hist['log_return'] = np.log(hist['Close'] / hist['Close'].shift(1))
            hist['HV_20d'] = hist['log_return'].rolling(window=20).std() * np.sqrt(252)
            hist.dropna(inplace=True)

            entry_hv = hist['HV_20d'].iloc[0]
            today = datetime.today()

            valid_expiries = [date for date in stock.options if (datetime.strptime(date, "%Y-%m-%d") - today).days >= 7]
            if not valid_expiries:
                continue

            expiry = valid_expiries[0]
            chain = stock.option_chain(expiry)
            calls = chain.calls
            puts = chain.puts

            if calls.empty or puts.empty:
                continue

            avg_call_iv = calls['impliedVolatility'].mean()
            avg_put_iv = puts['impliedVolatility'].mean()
            avg_iv = (avg_call_iv + avg_put_iv) / 2

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
    backtest_results = dynamic_backtest(selected_backtest_tickers)
    st.subheader("📈 Backtest Results (Dynamic Exit)")
    st.dataframe(backtest_results)
    
    if not backtest_results.empty:
        avg_pnl = backtest_results['PnL (%)'].mean()
        st.success(f"Average PnL across trades: {avg_pnl:.2f}%")

st.subheader("📬 Test Email Sending")

if st.button("Send Test Email"):
    result = send_email_report_html(df_filtered)
    st.success(result)
