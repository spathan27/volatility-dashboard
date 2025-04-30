import streamlit as st
from datetime import datetime
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import smtplib
from email.message import EmailMessage
from PIL import Image
import time

# ========= Streamlit Page Config =========
st.set_page_config(
    page_title="Volatility Screener Dashboard 🚀",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ========= Logo =========
logo = Image.open("logo.png")
st.image(logo, width=250)

# ========= Load Secrets =========
EMAIL_ADDRESS = st.secrets["email"]["address"]
EMAIL_PASSWORD = st.secrets["email"]["password"]
RECIPIENT_EMAIL = st.secrets["email"]["recipient"]

# ========= Refresh Button =========
if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.session_state['force_refresh'] = True
    st.experimental_rerun()

# ========== Email Sending ==========
def send_email_report_html(df_filtered):
    if df_filtered.empty:
        return "No data to email."
    top_trades = df_filtered[['Ticker', 'CurrentPrice', 'Call_IV_Premium', 'Put_IV_Premium', 'IV_Skew']]
    html_table = top_trades.to_html(index=False, border=0, justify='center')
    html_content = f"""<html><body style='font-family: Arial; background-color: #f9f9f9; padding: 20px;'>
        <h2 style='color: #333;'>📈 Volatility Screener - Top Trades</h2>
        {html_table}
        <p style='font-size: 12px; color: #999;'>Sent automatically by your Screener Bot 🤖</p>
    </body></html>"""
    msg = EmailMessage()
    msg['Subject'] = '📈 Volatility Screener – Trade Alerts'
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = RECIPIENT_EMAIL
    msg.set_content("This is an HTML email. Please view it in an email client that supports HTML.")
    msg.add_alternative(html_content, subtype='html')
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)
    return "✅ HTML Email sent successfully!"

# ========== Data Fetcher ==========
@st.cache_data
def fetch_stock_data():
    tickers = [
        "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "NFLX", "JPM", "V",
        "MA", "XOM", "COST", "UNH", "ORCL", "HD", "PEP", "KO", "INTC", "CSCO"
    ]
    results = []
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            current_price = info.get('regularMarketPrice')
            sector = info.get('sector', 'Unknown')
            market_cap = info.get('marketCap', 0)
            if not current_price or market_cap < 5e9:
                continue
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
            time.sleep(1)
        except Exception as e:
            print(f"Error processing {ticker}: {e}")
    return pd.DataFrame(results)

# ========== Load or Refresh Data ==========
if 'data' not in st.session_state or st.session_state.get('force_refresh', False):
    df = fetch_stock_data()
    st.session_state['data'] = df
    st.session_state['last_refresh'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state['force_refresh'] = False
else:
    df = st.session_state['data']

# ========== Interface ==========
st.title("📈 Advanced Volatility Screener Dashboard")
st.caption("Built with Streamlit + Yahoo Finance")
if 'last_refresh' in st.session_state:
    st.caption(f"🕒 Last refreshed: {st.session_state['last_refresh']} (Eastern Time)")

# Sidebar Filters
st.sidebar.header("Filters")
min_premium = st.sidebar.slider("Minimum IV Premium", 1.0, 3.0, 1.5, step=0.1)
top_n = st.sidebar.slider("Top N stocks", 5, 20, 10)
sector_options = ["All"] + sorted(df['Sector'].dropna().unique().tolist()) if not df.empty and 'Sector' in df else ["All"]
sector_filter = st.sidebar.multiselect("Sector Filter", sector_options, default=["All"])
focus_option = st.sidebar.radio("Focus on:", ["Call Premium", "Put Premium"])
if "All" not in sector_filter:
    df = df[df['Sector'].isin(sector_filter)]
if focus_option == "Call Premium":
    df_filtered = df[df['Call_IV_Premium'] >= min_premium].sort_values(by="Call_IV_Premium", ascending=False).head(top_n)
else:
    df_filtered = df[df['Put_IV_Premium'] >= min_premium].sort_values(by="Put_IV_Premium", ascending=False).head(top_n)

st.subheader(f"Top {focus_option} Opportunities")
st.dataframe(df_filtered)

st.download_button("📥 Download CSV", df_filtered.to_csv(index=False).encode("utf-8"), "screener_results.csv", "text/csv")

st.subheader("📬 Test Email Sending")
if st.button("Send Test Email"):
    result = send_email_report_html(df_filtered)
    st.success(result)