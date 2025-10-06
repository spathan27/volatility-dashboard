import schedule
import time
import pandas as pd
import smtplib
from email.message import EmailMessage
import os

from polygon_data import create_client, get_ticker_snapshot, load_polygon_api_key

# ========= Load Secrets from Environment =========
EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
RECIPIENT_EMAIL = os.getenv('RECIPIENT_EMAIL')
POLYGON_API_KEY = load_polygon_api_key()

CLIENT = create_client(POLYGON_API_KEY)

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
        snapshot = get_ticker_snapshot(CLIENT, ticker)
        if not snapshot:
            continue

        hist_vol = snapshot.get("HistVol")
        call_iv = snapshot.get("AvgCallIV")
        put_iv = snapshot.get("AvgPutIV")
        avg_iv = None
        if call_iv is not None and put_iv is not None:
            avg_iv = (call_iv + put_iv) / 2

        iv_premium = avg_iv / hist_vol if avg_iv and hist_vol else None

        results.append({
            "Ticker": ticker,
            "CurrentPrice": snapshot.get("CurrentPrice"),
            "HistVol": hist_vol,
            "AvgIV": avg_iv,
            "IVPremium": iv_premium
        })

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
