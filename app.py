import streamlit as st
import yfinance as yf
import pandas as pd
import datetime

# --- Setup ---
st.set_page_config(page_title="Anchored VWAP", layout="wide")
st.title("Anchored VWAP Collector")

# --- Inputs ---
col1, col2 = st.columns(2)
with col1:
    ticker = st.text_input("Ticker Symbol", value="NVDA").upper()
with col2:
    # default to start of 2024 or a specific recent low
    anchor_date = st.date_input("Anchor Date", value=datetime.date(2024, 1, 1))

# --- Data Fetching & Math ---
if ticker:
    # Get data with buffer to ensure we cover the anchor date
    start_fetch = anchor_date - datetime.timedelta(days=10)
    df = yf.download(ticker, start=start_fetch, progress=False)

    if not df.empty:
        # 1. Filter data to start exactly at Anchor Date
        df_anchor = df[df.index.date >= anchor_date].copy()

        # 2. Calculate Anchored VWAP
        # Formula: Cumulative(Price * Volume) / Cumulative(Volume)
        # Note: We use 'Adj Close' for accuracy, or 'Close' if you prefer raw price
        df_anchor['TPV'] = df_anchor['Close'] * df_anchor['Volume']  # Total Price Volume
        df_anchor['CumTPV'] = df_anchor['TPV'].cumsum()
        df_anchor['CumVol'] = df_anchor['Volume'].cumsum()
        df_anchor['Anchored VWAP'] = df_anchor['CumTPV'] / df_anchor['CumVol']

        # --- Visualization ---
        st.subheader(f"{ticker} Anchored from {anchor_date}")

        # Create a chart with both Price and VWAP
        chart_data = df_anchor[['Close', 'Anchored VWAP']]
        st.line_chart(chart_data, color=["#2E86C1", "#E74C3C"])  # Blue for Price, Red for VWAP

        # --- Facts & Numbers ---
        latest_price = df_anchor['Close'].iloc[-1]
        latest_vwap = df_anchor['Anchored VWAP'].iloc[-1]
        diff = ((latest_price - latest_vwap) / latest_vwap) * 100

        st.metric("Current Price", f"${latest_price:.2f}")
        st.metric("Anchored VWAP", f"${latest_vwap:.2f}", f"{diff:.2f}% from mean")

    else:
        st.error("No data found. Check ticker.")

# --- Note Taking (Local Storage) ---
st.write("---")
st.subheader("Field Notes")
note = st.text_area("Observations on this anchor point:")
if st.button("Save Note"):
    # Appends to a CSV file in the same folder
    with open("notes.csv", "a") as f:
        f.write(f"{datetime.datetime.now()},{ticker},{anchor_date},{note}\n")
    st.success("Note saved locally.")