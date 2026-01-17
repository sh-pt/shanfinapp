import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import plotly.graph_objects as go
import numpy as np

# --- Setup ---
st.set_page_config(page_title="Anchored VWAP", layout="wide")
st.title("Anchored VWAP + StDev")

# --- Inputs ---
col1, col2 = st.columns(2)
with col1:
    ticker = st.text_input("Ticker Symbol", value="NVDA").upper()
with col2:
    anchor_date = st.date_input("Anchor Date", value=datetime.date(2024, 1, 1))

# --- Data Fetching & Math ---
if ticker:
    start_fetch = anchor_date - datetime.timedelta(days=20)
    df = yf.download(ticker, start=start_fetch, progress=False)

    if not df.empty:
        # Flatten Multi-Index if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Filter to Anchor Date
        df_anchor = df[df.index.date >= anchor_date].copy()

        if 'Close' in df_anchor.columns and 'Volume' in df_anchor.columns:
            # --- 1. VWAP Calculation ---
            df_anchor['TPV'] = df_anchor['Close'] * df_anchor['Volume']
            df_anchor['CumTPV'] = df_anchor['TPV'].cumsum()
            df_anchor['CumVol'] = df_anchor['Volume'].cumsum()
            df_anchor['VWAP'] = df_anchor['CumTPV'] / df_anchor['CumVol']

            # --- 2. Standard Deviation Calculation (Volume Weighted) ---
            # Formula: Var = Mean(x^2) - (Mean(x))^2
            df_anchor['TP2V'] = (df_anchor['Close'] ** 2) * df_anchor['Volume']
            df_anchor['CumTP2V'] = df_anchor['TP2V'].cumsum()

            # Variance calculation
            # We clip at 0 to avoid tiny floating point negatives
            df_anchor['VW_Variance'] = (df_anchor['CumTP2V'] / df_anchor['CumVol']) - (df_anchor['VWAP'] ** 2)
            df_anchor['VW_Variance'] = df_anchor['VW_Variance'].clip(lower=0)
            df_anchor['StDev'] = np.sqrt(df_anchor['VW_Variance'])

            # --- 3. The Bands ---
            df_anchor['Upper1'] = df_anchor['VWAP'] + (1 * df_anchor['StDev'])
            df_anchor['Lower1'] = df_anchor['VWAP'] - (1 * df_anchor['StDev'])
            df_anchor['Upper2'] = df_anchor['VWAP'] + (2 * df_anchor['StDev'])
            df_anchor['Lower2'] = df_anchor['VWAP'] - (2 * df_anchor['StDev'])

            # --- Visualization (Plotly) ---
            fig = go.Figure()

            # A. The Outer Bands (2 Std Dev) - Light Shading
            # We draw Upper2, then fill down to Lower2, but we layer it behind everything
            # Actually, to get distinct zones, we fill U2->U1 and L1->L2.
            # Simpler approach for "Old Friend" speed:
            # 1. Fill L2 to U2 (Lightest)
            # 2. Fill L1 to U1 (Darker on top)

            # Layer 1: The Broad 2-Std Range (Light Grey)
            fig.add_trace(
                go.Scatter(x=df_anchor.index, y=df_anchor['Lower2'], mode='lines', line=dict(width=0), showlegend=False,
                           name='L2'))
            fig.add_trace(
                go.Scatter(x=df_anchor.index, y=df_anchor['Upper2'], mode='lines', line=dict(width=0), fill='tonexty',
                           fillcolor='rgba(200, 200, 200, 0.2)', showlegend=False, name='2 Std Band'))

            # Layer 2: The Inner 1-Std Range (Darker Grey/Blue)
            fig.add_trace(
                go.Scatter(x=df_anchor.index, y=df_anchor['Lower1'], mode='lines', line=dict(width=0), showlegend=False,
                           name='L1'))
            fig.add_trace(
                go.Scatter(x=df_anchor.index, y=df_anchor['Upper1'], mode='lines', line=dict(width=0), fill='tonexty',
                           fillcolor='rgba(100, 100, 250, 0.2)', showlegend=False, name='1 Std Band'))

            # Layer 3: Main Lines
            fig.add_trace(
                go.Scatter(x=df_anchor.index, y=df_anchor['VWAP'], mode='lines', line=dict(color='#FF4B4B', width=2),
                           name='Anchored VWAP'))
            fig.add_trace(
                go.Scatter(x=df_anchor.index, y=df_anchor['Close'], mode='lines', line=dict(color='#2E86C1', width=2),
                           name='Price'))

            fig.update_layout(
                title=f"{ticker} Anchored VWAP",
                hovermode="x unified",
                template="plotly_white",
                height=600,
                margin=dict(l=0, r=0, t=40, b=0),
                legend=dict(orientation="h", y=1, x=0, xanchor="left", yanchor="bottom")
            )

            st.plotly_chart(fig, use_container_width=True)

            # --- Facts & Numbers ---
            latest = df_anchor.iloc[-1]
            st.metric("Price", f"${latest['Close']:.2f}")

            col_a, col_b, col_c = st.columns(3)
            col_a.metric("VWAP", f"${latest['VWAP']:.2f}")
            col_b.metric("+2σ Limit", f"${latest['Upper2']:.2f}")
            col_c.metric("-2σ Limit", f"${latest['Lower2']:.2f}")

        else:
            st.error("Data missing required columns.")
    else:
        st.error("No data found.")

# --- Note Taking ---
st.write("---")
st.subheader("Field Notes")
note = st.text_area("Observations:")
if st.button("Save Note"):
    with open("notes.csv", "a") as f:
        f.write(f"{datetime.datetime.now()},{ticker},{anchor_date},{note}\n")
    st.success("Note saved locally.")