import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import plotly.graph_objects as go
import numpy as np
from streamlit_gsheets import GSheetsConnection

# --- Setup ---
st.set_page_config(page_title="AVWAP", layout="wide")
# Removed st.title as requested

# --- Connection ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- Inputs ---
col1, col2 = st.columns(2)
with col1:
    ticker = st.text_input("Ticker", value="NVDA").upper()
with col2:
    anchor_date = st.date_input("Anchor", value=datetime.date(2024, 1, 1))

# --- TAB STRUCTURE ---
tab_chart, tab_notes = st.tabs(["Chart", "Notes"])

# --- TAB 1: CHART ---
with tab_chart:
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

                # Visualization (Clean & Static)
                fig = go.Figure()

                # Bands (No Legends)
                fig.add_trace(go.Scatter(x=df_anchor.index, y=df_anchor['Lower2'], mode='lines', line=dict(width=0),
                                         showlegend=False, hoverinfo='skip'))
                fig.add_trace(go.Scatter(x=df_anchor.index, y=df_anchor['Upper2'], mode='lines', line=dict(width=0),
                                         fill='tonexty', fillcolor='rgba(200, 200, 200, 0.2)', showlegend=False,
                                         hoverinfo='skip'))
                fig.add_trace(go.Scatter(x=df_anchor.index, y=df_anchor['Lower1'], mode='lines', line=dict(width=0),
                                         showlegend=False, hoverinfo='skip'))
                fig.add_trace(go.Scatter(x=df_anchor.index, y=df_anchor['Upper1'], mode='lines', line=dict(width=0),
                                         fill='tonexty', fillcolor='rgba(100, 100, 250, 0.2)', showlegend=False,
                                         hoverinfo='skip'))

                # Lines (No Legends)
                fig.add_trace(go.Scatter(x=df_anchor.index, y=df_anchor['VWAP'], mode='lines',
                                         line=dict(color='#FF4B4B', width=2), showlegend=False))
                fig.add_trace(go.Scatter(x=df_anchor.index, y=df_anchor['Close'], mode='lines',
                                         line=dict(color='#2E86C1', width=2), showlegend=False))

                # Layout: Minimalist
                fig.update_layout(
                    height=450,
                    margin=dict(l=0, r=0, t=10, b=0),
                    template="plotly_white",
                    xaxis=dict(showgrid=False),
                    yaxis=dict(showgrid=True, gridcolor='#f0f0f0')
                )

                # STATIC PLOT: Disables all zoom/pan/hover interaction
                st.plotly_chart(fig, use_container_width=True, config={'staticPlot': True})

                # Small Text Numbers (Manual formatting)
                latest = df_anchor.iloc[-1]

                # Using columns for small, dense layout
                c1, c2, c3, c4 = st.columns(4)
                c1.markdown(f"**Price**<br>${latest['Close']:.2f}", unsafe_allow_html=True)
                c2.markdown(f"**VWAP**<br>${latest['VWAP']:.2f}", unsafe_allow_html=True)
                c3.markdown(f"**+1σ**<br>${latest['Upper1']:.2f}", unsafe_allow_html=True)
                c4.markdown(f"**-1σ**<br>${latest['Lower1']:.2f}", unsafe_allow_html=True)

            else:
                st.error("Data Error")
        else:
            st.error("No Data")

# --- TAB 2: NOTES ---
with tab_notes:
    try:
        # Load Only Ticker/Note columns
        existing_data = conn.read(worksheet="Sheet1", usecols=[0, 1], ttl=0)
        existing_data = existing_data.dropna(how="all")
        existing_data['Ticker'] = existing_data['Ticker'].astype(str)
        existing_data['Note'] = existing_data['Note'].astype(str)

        # Check for Ticker
        if ticker not in existing_data['Ticker'].values:
            new_row = pd.DataFrame([{"Ticker": ticker, "Note": ""}])
            display_data = pd.concat([existing_data, new_row], ignore_index=True)
        else:
            display_data = existing_data

        # Editor
        st.caption(f"Notes for {ticker}")
        edited_df = st.data_editor(
            display_data[display_data['Ticker'] == ticker],
            num_rows="fixed",
            use_container_width=True,
            hide_index=True,
            column_config={
                "Ticker": st.column_config.TextColumn("Ticker", disabled=True),
                "Note": st.column_config.TextColumn("Note", width="large")
            }
        )

        if st.button("Save", type="primary"):
            other_tickers = existing_data[existing_data['Ticker'] != ticker]
            final_df = pd.concat([other_tickers, edited_df], ignore_index=True)
            conn.update(worksheet="Sheet1", data=final_df)
            st.toast("Saved!")  # Smaller notification than st.success
            st.rerun()

    except Exception as e:
        st.error(f"Waiting for secrets... ({e})")