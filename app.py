import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import plotly.graph_objects as go
import numpy as np
from streamlit_gsheets import GSheetsConnection

# --- Setup ---
st.set_page_config(page_title="AVWAP", layout="wide")

# --- Connection ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- Inputs ---
col1, col2 = st.columns(2)
with col1:
    ticker = st.text_input("Ticker", value="NVDA").upper()
with col2:
    anchor_date = st.date_input("Anchor", value=datetime.date(2024, 1, 1))

# ==========================================
# SECTION 1: THE CHART
# ==========================================
if ticker:
    # Fetch Data
    start_fetch = anchor_date - datetime.timedelta(days=20)
    df = yf.download(ticker, start=start_fetch, progress=False)

    if not df.empty:
        # Flatten Multi-Index
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df_anchor = df[df.index.date >= anchor_date].copy()

        if 'Close' in df_anchor.columns and 'Volume' in df_anchor.columns:
            # Math
            df_anchor['TPV'] = df_anchor['Close'] * df_anchor['Volume']
            df_anchor['CumTPV'] = df_anchor['TPV'].cumsum()
            df_anchor['CumVol'] = df_anchor['Volume'].cumsum()
            df_anchor['VWAP'] = df_anchor['CumTPV'] / df_anchor['CumVol']

            df_anchor['TP2V'] = (df_anchor['Close'] ** 2) * df_anchor['Volume']
            df_anchor['CumTP2V'] = df_anchor['TP2V'].cumsum()
            df_anchor['VW_Variance'] = (df_anchor['CumTP2V'] / df_anchor['CumVol']) - (df_anchor['VWAP'] ** 2)
            df_anchor['VW_Variance'] = df_anchor['VW_Variance'].clip(lower=0)
            df_anchor['StDev'] = np.sqrt(df_anchor['VW_Variance'])

            df_anchor['Upper1'] = df_anchor['VWAP'] + (1 * df_anchor['StDev'])
            df_anchor['Lower1'] = df_anchor['VWAP'] - (1 * df_anchor['StDev'])
            df_anchor['Upper2'] = df_anchor['VWAP'] + (2 * df_anchor['StDev'])
            df_anchor['Lower2'] = df_anchor['VWAP'] - (2 * df_anchor['StDev'])

            # Visualization
            fig = go.Figure()

            # Bands (No Legend)
            fig.add_trace(
                go.Scatter(x=df_anchor.index, y=df_anchor['Lower2'], mode='lines', line=dict(width=0), showlegend=False,
                           hoverinfo='skip'))
            fig.add_trace(
                go.Scatter(x=df_anchor.index, y=df_anchor['Upper2'], mode='lines', line=dict(width=0), fill='tonexty',
                           fillcolor='rgba(200, 200, 200, 0.2)', showlegend=False, hoverinfo='skip'))
            fig.add_trace(
                go.Scatter(x=df_anchor.index, y=df_anchor['Lower1'], mode='lines', line=dict(width=0), showlegend=False,
                           hoverinfo='skip'))
            fig.add_trace(
                go.Scatter(x=df_anchor.index, y=df_anchor['Upper1'], mode='lines', line=dict(width=0), fill='tonexty',
                           fillcolor='rgba(100, 100, 250, 0.2)', showlegend=False, hoverinfo='skip'))

            # Lines
            fig.add_trace(
                go.Scatter(x=df_anchor.index, y=df_anchor['VWAP'], mode='lines', line=dict(color='#FF4B4B', width=2),
                           showlegend=False))
            fig.add_trace(
                go.Scatter(x=df_anchor.index, y=df_anchor['Close'], mode='lines', line=dict(color='#2E86C1', width=2),
                           showlegend=False))

            # --- CUSTOM LABELS ON RIGHT SIDE ---
            # We add annotations for the last value of each line
            last = df_anchor.iloc[-1]
            labels = [
                (last['Close'], "Price", "#2E86C1"),
                (last['VWAP'], "VWAP", "#FF4B4B"),
                (last['Upper1'], "+1σ", "black"),
                (last['Lower1'], "-1σ", "black"),
                (last['Upper2'], "+2σ", "gray"),
                (