"""Utility helpers for working with Polygon.io market and options data."""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Optional, Tuple

import numpy as np
import pandas as pd
from polygon import RESTClient


def load_polygon_api_key() -> str:
    """Return the Polygon API key from environment variables or Streamlit secrets.

    The lookup order prioritises the ``POLYGON_API_KEY`` environment variable so the
    key never needs to be committed to source control.  If a Streamlit ``secrets``
    configuration is available we fall back to ``[polygon][api_key]``.
    """

    env_key = os.getenv("POLYGON_API_KEY")
    if env_key:
        return env_key

    try:
        import streamlit as st  # Imported lazily to avoid mandatory dependency.

        secrets_section = st.secrets.get("polygon", {})
        secret_key = secrets_section.get("api_key")
        if secret_key:
            return secret_key
    except Exception:
        # Streamlit is not available or the secrets structure is missing; fall
        # through to the explicit error raised below.
        pass

    raise ValueError(
        "Set the POLYGON_API_KEY environment variable or configure "
        "[polygon][api_key] in .streamlit/secrets.toml"
    )


def create_client(api_key: str) -> RESTClient:
    """Create a Polygon REST client from the provided API key."""
    if not api_key:
        raise ValueError("A Polygon.io API key is required to use this application.")
    return RESTClient(api_key=api_key)


def _get_aggregate_window(
    client: RESTClient,
    ticker: str,
    start: datetime,
    end: datetime,
) -> pd.DataFrame:
    """Fetch daily aggregates for *ticker* between *start* and *end*.

    Returns a dataframe indexed by the UTC datetime of each bar with columns for
    the adjusted close price. Missing or incomplete responses return an empty
    dataframe so callers can gracefully skip the symbol.
    """
    try:
        aggs = client.get_aggs(
            ticker=ticker,
            multiplier=1,
            timespan="day",
            from_=start.strftime("%Y-%m-%d"),
            to=end.strftime("%Y-%m-%d"),
            adjusted=True,
            limit=5000,
        )
    except Exception:
        return pd.DataFrame()

    records = []
    for agg in aggs:
        timestamp = getattr(agg, "timestamp", None)
        close = getattr(agg, "close", None)
        if timestamp is None or close is None:
            continue
        # Polygon timestamps are in milliseconds.
        bar_time = datetime.fromtimestamp(timestamp / 1000.0)
        records.append({"Date": bar_time, "Close": close})

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df.sort_values("Date", inplace=True)
    df.set_index("Date", inplace=True)
    return df


def get_historical_volatility(
    client: RESTClient,
    ticker: str,
    days: int = 365,
    window: int = 20,
) -> Tuple[pd.DataFrame, Optional[float]]:
    """Return a dataframe of prices and HV along with the latest HV reading."""
    end = datetime.utcnow()
    start = end - timedelta(days=days)
    prices = _get_aggregate_window(client, ticker, start, end)
    if prices.empty or len(prices) < window + 1:
        return prices, None

    prices = prices.copy()
    prices["log_return"] = np.log(prices["Close"] / prices["Close"].shift(1))
    prices["HV_20d"] = (
        prices["log_return"].rolling(window=window).std() * np.sqrt(252)
    )
    hv_series = prices["HV_20d"].dropna()
    hv_latest = hv_series.iloc[-1] if not hv_series.empty else None
    return prices, hv_latest


def _get_next_option_expiry(
    client: RESTClient,
    ticker: str,
    min_days_to_expiry: int = 7,
) -> Optional[str]:
    today = datetime.utcnow().date()
    expiries = []
    try:
        contracts = client.list_options_contracts(
            underlying_ticker=ticker,
            order="asc",
            sort="expiration_date",
            limit=1000,
        )
    except Exception:
        return None

    for contract in contracts:
        exp_str = getattr(contract, "expiration_date", None)
        if not exp_str:
            continue
        try:
            exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        if (exp_date - today).days >= min_days_to_expiry:
            expiries.append(exp_date)
        if len(expiries) >= 10:
            break

    if not expiries:
        return None
    next_expiry = min(expiries)
    return next_expiry.strftime("%Y-%m-%d")


def get_option_iv_snapshot(
    client: RESTClient,
    ticker: str,
    current_price: float,
    min_days_to_expiry: int = 7,
) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """Calculate average call/put implied volatility for the next expiry."""
    expiry = _get_next_option_expiry(client, ticker, min_days_to_expiry)
    if not expiry:
        return None, None, None

    call_ivs = []
    put_ivs = []

    try:
        contracts = client.list_options_contracts(
            underlying_ticker=ticker,
            expiration_date=expiry,
            limit=2000,
        )
    except Exception:
        return None, None, expiry

    for contract in contracts:
        contract_type = getattr(contract, "contract_type", "").lower()
        strike = getattr(contract, "strike_price", None)
        implied_vol = getattr(contract, "implied_volatility", None)
        if contract_type not in {"call", "put"} or strike is None or implied_vol is None:
            continue

        day_stats = getattr(contract, "day", None)
        volume = getattr(contract, "volume", None)
        open_interest = getattr(contract, "open_interest", None)
        if day_stats is not None:
            volume = getattr(day_stats, "volume", volume)
            open_interest = getattr(day_stats, "open_interest", open_interest)

        volume = volume or 0
        open_interest = open_interest or 0

        if contract_type == "call":
            if strike > current_price and volume > 0 and open_interest > 0:
                call_ivs.append(implied_vol)
        else:
            if strike < current_price and volume > 0 and open_interest > 0:
                put_ivs.append(implied_vol)

    call_avg = float(np.mean(call_ivs)) if call_ivs else None
    put_avg = float(np.mean(put_ivs)) if put_ivs else None
    return call_avg, put_avg, expiry


def get_ticker_snapshot(
    client: RESTClient,
    ticker: str,
    min_market_cap: float = 5e9,
    hv_days: int = 365,
    hv_window: int = 20,
    min_days_to_expiry: int = 7,
) -> Optional[dict]:
    """Gather a full metrics snapshot for a ticker or return ``None`` on failure."""
    try:
        details = client.get_ticker_details(ticker)
    except Exception:
        return None

    market_cap = getattr(details, "market_cap", None)
    if not market_cap or market_cap < min_market_cap:
        return None

    sector = getattr(details, "sector", None) or "Unknown"

    try:
        last_trade = client.get_last_trade(ticker)
        current_price = getattr(last_trade, "price", None)
    except Exception:
        current_price = None

    if current_price is None:
        return None

    hist_prices, hist_vol = get_historical_volatility(
        client, ticker, days=hv_days, window=hv_window
    )
    if hist_vol is None or not np.isfinite(hist_vol):
        return None

    call_iv, put_iv, expiry = get_option_iv_snapshot(
        client,
        ticker,
        current_price=current_price,
        min_days_to_expiry=min_days_to_expiry,
    )

    if call_iv is None or put_iv is None:
        return None

    call_premium = call_iv / hist_vol if hist_vol else None
    put_premium = put_iv / hist_vol if hist_vol else None

    return {
        "Ticker": ticker,
        "Sector": sector,
        "MarketCap": market_cap,
        "CurrentPrice": current_price,
        "HistVol": hist_vol,
        "AvgCallIV": call_iv,
        "AvgPutIV": put_iv,
        "Call_IV_Premium": call_premium,
        "Put_IV_Premium": put_premium,
        "IV_Skew": put_iv - call_iv,
        "NextExpiry": expiry,
    }
