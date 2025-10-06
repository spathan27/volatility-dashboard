# Volatility Dashboard

This project provides a Streamlit dashboard and an accompanying email scheduler to screen equity volatility using Polygon.io market and options data.

## Configuration

Sensitive credentials such as the Polygon API key and email settings should never be committed to the repository. The application and scheduler automatically read the Polygon API key from either an environment variable or a Streamlit secrets file.

### Polygon API Key

1. **Preferred: environment variable**
   ```bash
   export POLYGON_API_KEY="your_real_key_here"
   ```
   The dashboard and the scheduler will both pick up the key from the `POLYGON_API_KEY` variable.

2. **Streamlit Cloud / local secrets file**
   Create a `.streamlit/secrets.toml` file (not tracked by git) with the following structure:
   ```toml
   [polygon]
   api_key = "your_real_key_here"
   ```

### Email Credentials (Scheduler)

For the optional email scheduler, define the following environment variables before running `email_scheduler.py`:

```bash
export EMAIL_ADDRESS="sender@example.com"
export EMAIL_PASSWORD="app_specific_password"
export RECIPIENT_EMAIL="recipient@example.com"
```

These values are **not** required for the Streamlit dashboard.

## Running the Dashboard

```bash
streamlit run volatility_dashboard.py
```

## Running the Email Scheduler

```bash
python email_scheduler.py
```

The scheduler uses the same Polygon API key loading mechanism described above.
