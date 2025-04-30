import schedule
import time
import pandas as pd
import numpy as np
import yfinance as yf
import smtplib
from email.message import EmailMessage
import os

# ========= Load Secrets from Environment =========
EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
RECIPIENT_EMAIL = os.getenv('RECIPIENT_EMAIL')

# ========= Fetch Stock Data =========
def fetch_stock_data():
    # List of NASDAQ-100 or large-cap tickers
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
def send_email_report_html(df_filtered):
    if df_filtered.empty:
        return "No data to email."

    df_filtered = df_filtered.sort_values(by="IVPremium", ascending=False).head(10)

    html_table = df_filtered.to_html(index=False, border=0, justify='center')

    html_content = f"""
    <html>
        <body style="font-family: Arial; background-color: #f4f4f4; padding: 20px;">
            <h2>📈 Volatility Screener - Top 10 Opportunities</h2>
            {html_table}
            <p style="font-size: 12px; color: #999;">Sent automatically by your Screener Bot 🤖</p>
        </body>
    </html>
    """

    msg = EmailMessage()
    msg['Subject'] = '📈 Volatility Screener – Daily Alerts'
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = RECIPIENT_EMAIL
    msg.set_content("This is an HTML email. Please view it in an email client that supports HTML.")
    msg.add_alternative(html_content, subtype='html')

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)

    return "✅ HTML Email sent successfully!"

# ========= Scheduler Jobs =========
def job_send_morning_email():
    print("⏰ Morning Email Triggered!")
    df = fetch_stock_data()
    send_email_report_html(df)

def job_send_afternoon_email():
    print("⏰ Afternoon Email Triggered!")
    df = fetch_stock_data()
    send_email_report_html(df)

# ========= Schedule =========
schedule.every().day.at("09:45").do(job_send_morning_email)
schedule.every().day.at("14:00").do(job_send_afternoon_email)

print("✅ Scheduler started... Waiting for trigger times...")

while True:
    schedule.run_pending()
    time.sleep(30)
