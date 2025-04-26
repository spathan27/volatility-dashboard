import schedule
import time
import pandas as pd
import numpy as np
import yfinance as yf
import smtplib
from email.message import EmailMessage
import os
from datetime import datetime
import pytz
from flask import Flask
import threading

# ========= Load Secrets from Environment =========
EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
RECIPIENT_EMAIL = os.getenv('RECIPIENT_EMAIL')

# ========= Timezone Setup =========
eastern = pytz.timezone('US/Eastern')

# ========= Full Ticker List =========
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

# ========= Fetch Stock Data =========
def fetch_stock_data():
    results = []
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            hist = stock.history(period="1y")

            if not hist.empty:
                hist['log_return'] = np.log(hist['Close'] / hist['Close'].shift(1))
                hist_vol = hist['log_return'].dropna().std() * np.sqrt(252)
            else:
                hist_vol = None

            options_dates = stock.options
            avg_iv = None
            if options_dates:
                chain = stock.option_chain(options_dates[0])
                calls = chain.calls
                if not calls.empty and 'impliedVolatility' in calls.columns:
                    avg_iv = calls['impliedVolatility'].mean()

            results.append({
                "Ticker": ticker,
                "CurrentPrice": info.get('regularMarketPrice', None),
                "HistVol": hist_vol,
                "AvgIV": avg_iv,
                "IVPremium": avg_iv / hist_vol if avg_iv and hist_vol else None
            })
        except Exception as e:
            print(f"Error processing {ticker}: {e}")

    df = pd.DataFrame(results)
    df = df.dropna(subset=["AvgIV", "HistVol"])
    df["IVPremium"] = df["AvgIV"] / df["HistVol"]
    return df

# ========= Send Email =========
def send_email_report_html(df_filtered, custom_subject):
    if df_filtered.empty:
        return "No data to email."

    df_filtered = df_filtered.sort_values(by="IVPremium", ascending=False).head(10)

    html_table = df_filtered.to_html(index=False, border=0, justify='center')

    html_content = f"""
    <html>
        <body style="font-family: Arial; background-color: #f4f4f4; padding: 20px;">
            <h2>{custom_subject}</h2>
            {html_table}
            <p style="font-size: 12px; color: #999;">Sent automatically by your Screener Bot 🤖</p>
        </body>
    </html>
    """

    msg = EmailMessage()
    msg['Subject'] = custom_subject
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = RECIPIENT_EMAIL
    msg.set_content("This is an HTML email. Please view it in an email client that supports HTML.")
    msg.add_alternative(html_content, subtype='html')

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)

    return "✅ HTML Email sent successfully!"

# ========= Smart Scheduler =========
def job_send_email():
    now = datetime.now(eastern)
    current_time = now.strftime("%H:%M")

    print(f"⏰ Current Eastern Time: {current_time}")

    df = fetch_stock_data()

    if "09:45" <= current_time < "10:30":
        subject = "📈 Morning Volatility Screener Update 🚀"
    elif "14:00" <= current_time < "15:00":
        subject = "📈 Afternoon Volatility Screener Update 🚀"
    else:
        subject = "📈 Volatility Screener Update 🚀"

    send_email_report_html(df, subject)

# ========= Check Every Minute =========
def schedule_check():
    now = datetime.now(eastern)
    current_time = now.strftime("%H:%M")

    if current_time == "09:45" or current_time == "14:00":
        job_send_email()

# ========= Flask Web App to Keep Render Happy =========
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Volatility Screener Email Bot is running!"

def main_loop():
    print("✅ Smart Scheduler started... Waiting for Eastern Time triggers...")

    while True:
        schedule_check()
        time.sleep(60)

if __name__ == "__main__":
    scheduler_thread = threading.Thread(target=main_loop)
    scheduler_thread.start()

    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
