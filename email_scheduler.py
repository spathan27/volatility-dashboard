import schedule
import time
import pandas as pd
import yfinance as yf
import smtplib
from email.message import EmailMessage
import os

# Load secrets from environment variables
EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
RECIPIENT_EMAIL = os.getenv('RECIPIENT_EMAIL')

def fetch_stock_data():
    # Your original logic to pull and process data
    tickers = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN"]  # Small list for quick example
    results = []

    for ticker in tickers:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1y")
        if not hist.empty:
            hist['log_return'] = (hist['Close'] / hist['Close'].shift(1)).apply(lambda x: np.log(x))
            hist_vol = hist['log_return'].dropna().std() * (252**0.5)
        else:
            hist_vol = None
        
        results.append({
            "Ticker": ticker,
            "CurrentPrice": stock.info.get('regularMarketPrice', None),
            "HistVol": hist_vol
        })

    return pd.DataFrame(results)

def send_email_report_html(df_filtered):
    if df_filtered.empty:
        return "No data to email."

    html_table = df_filtered.to_html(index=False, border=0, justify='center')

    html_content = f"""
    <html>
        <body style="font-family: Arial;">
            <h2>📈 Volatility Screener - Top Trades</h2>
            {html_table}
            <p>Sent automatically by your Screener Bot 🤖</p>
        </body>
    </html>
    """

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

def job_send_morning_email():
    df = fetch_stock_data()
    send_email_report_html(df)

def job_send_afternoon_email():
    df = fetch_stock_data()
    send_email_report_html(df)

# Schedule
schedule.every().day.at("09:45").do(job_send_morning_email)
schedule.every().day.at("14:00").do(job_send_afternoon_email)

print("✅ Scheduler started... Waiting for trigger times...")

while True:
    schedule.run_pending()
    time.sleep(30)
