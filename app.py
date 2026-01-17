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

            # 1. Bands (Background) - No Legend
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

            # 2. Main Lines
            fig.add_trace(
                go.Scatter(x=df_anchor.index, y=df_anchor['VWAP'], mode='lines', line=dict(color='#FF4B4B', width=2),
                           showlegend=False))
            fig.add_trace(
                go.Scatter(x=df_anchor.index, y=df_anchor['Close'], mode='lines', line=dict(color='#2E86C1', width=2),
                           showlegend=False))

            # 3. Floating Labels on Right Side
            last = df_anchor.iloc[-1]


            def add_label(val, text, color):
                fig.add_annotation(
                    x=1.0, xanchor="left", xref="paper",
                    y=val, yanchor="middle",
                    text=f"{text} {val:.2f}",
                    showarrow=False,
                    font=dict(size=10, color=color),
                    align="left"
                )


            # --- COLOR UPDATE HERE ---
            add_label(last['Close'], "Price", "#2E86C1")
            add_label(last['VWAP'], "VWAP", "#FF4B4B")
            # Changed 1std to "gray" to match 2std
            add_label(last['Upper1'], "+1σ", "gray")
            add_label(last['Lower1'], "-1σ", "gray")
            add_label(last['Upper2'], "+2σ", "gray")
            add_label(last['Lower2'], "-2σ", "gray")

            # Layout
            fig.update_layout(
                height=450,
                margin=dict(l=0, r=70, t=10, b=0),
                template="plotly_white",
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor='#f0f0f0', side="left")
            )

            st.plotly_chart(fig, use_container_width=True, config={'staticPlot': True})

        else:
            st.error("Data Error: Missing Columns")
    else:
        st.error("No Data")

# ==========================================
# SECTION 2: INTELLIGENT NOTES
# ==========================================
st.divider()

try:
    # 1. Load Data
    existing_data = conn.read(worksheet="Sheet1", usecols=[0, 1, 2], ttl=0)
    existing_data = existing_data.dropna(how="all")
    existing_data['Date'] = existing_data['Date'].astype(str)
    existing_data['Ticker'] = existing_data['Ticker'].astype(str)
    existing_data['Note'] = existing_data['Note'].astype(str)

    # 2. Split Data
    current_ticker_df = existing_data[existing_data['Ticker'] == ticker].copy()
    other_tickers_df = existing_data[existing_data['Ticker'] != ticker].copy()

    col_edit, col_add = st.columns([2, 1])

    # 3. The Editor (View & Delete)
    with col_edit:
        st.caption(f"History for {ticker} (Select left edge + Delete key to remove)")

        edited_df = st.data_editor(
            current_ticker_df,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,  # Standard hide
            column_config={
                # --- HIDES THE UGLY '0' COLUMN ---
                "_index": st.column_config.Column(hidden=True),
                "Date": st.column_config.TextColumn("Date", disabled=True),
                "Ticker": st.column_config.TextColumn("Ticker", disabled=True),
                "Note": st.column_config.TextColumn("Note", width="large")
            }
        )

        if st.button("Sync Changes", type="primary"):
            final_df = pd.concat([other_tickers_df, edited_df], ignore_index=True)
            conn.update(worksheet="Sheet1", data=final_df)
            st.toast("Updated!")
            st.rerun()

    # 4. Add New Note
    with col_add:
        with st.form("new_note"):
            st.caption("New Entry")
            new_txt = st.text_area("Content", height=150, label_visibility="collapsed")
            if st.form_submit_button("Add Note"):
                if new_txt:
                    today = datetime.date.today().strftime("%Y-%m-%d")
                    new_row = pd.DataFrame([{"Date": today, "Ticker": ticker, "Note": new_txt}])
                    final_df = pd.concat([other_tickers_df, edited_df, new_row], ignore_index=True)
                    conn.update(worksheet="Sheet1", data=final_df)
                    st.toast("Saved!")
                    st.rerun()

    # 5. Reading Mode
    if not current_ticker_df.empty:
        with st.expander("Reading Mode (Clean View)", expanded=False):
            for i, row in current_ticker_df.iterrows():
                st.markdown(f"**{row['Date']}**")
                st.info(row['Note'])

except Exception as e:
    st.error(f"Connecting to Brain... ({e})")