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
            # Math: VWAP & StDev
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

            # Bands
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

            # Layout: Labels on Right Side
            fig.update_layout(
                height=450,
                margin=dict(l=0, r=0, t=10, b=0),
                template="plotly_white",
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor='#f0f0f0', side="right")  # <--- MOVED TO RIGHT
            )

            st.plotly_chart(fig, use_container_width=True, config={'staticPlot': True})

        else:
            st.error("Data Error")
    else:
        st.error("No Data")

# ==========================================
# SECTION 2: THE NOTES (DIARY MODE)
# ==========================================
st.divider()  # Visual separator

try:
    # 1. Load Data
    existing_data = conn.read(worksheet="Sheet1", usecols=[0, 1, 2], ttl=0)
    existing_data = existing_data.dropna(how="all")
    # Enforce string types
    existing_data['Date'] = existing_data['Date'].astype(str)
    existing_data['Ticker'] = existing_data['Ticker'].astype(str)
    existing_data['Note'] = existing_data['Note'].astype(str)

    # 2. View History (Table)
    # Filter for just this ticker
    history = existing_data[existing_data['Ticker'] == ticker]

    col_hist, col_add = st.columns([1, 1])

    with col_hist:
        st.caption(f"History for {ticker}")
        if not history.empty:
            # Show table sorted by date (newest on top if you prefer, currently default order)
            st.dataframe(history[['Date', 'Note']], hide_index=True, use_container_width=True)
        else:
            st.info("No notes yet.")

    # 3. Add New Note (Form)
    with col_add:
        st.caption("Add New Entry")
        with st.form("add_note_form"):
            new_note_text = st.text_area("Write here (supports new lines)", height=100)
            submit = st.form_submit_button("Save Note")

            if submit and new_note_text:
                # Create new row
                current_date = datetime.date.today().strftime("%Y-%m-%d")
                new_row = pd.DataFrame([{"Date": current_date, "Ticker": ticker, "Note": new_note_text}])

                # Append to master data
                updated_df = pd.concat([existing_data, new_row], ignore_index=True)

                # Push to Google
                conn.update(worksheet="Sheet1", data=updated_df)
                st.toast("Note Saved!")
                st.rerun()

except Exception as e:
    st.error(f"Waiting for connection... ({e})")