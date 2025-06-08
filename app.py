import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
from ta.momentum import RSIIndicator, StochRSIIndicator
from ta.trend import MACD, SMAIndicator, EMAIndicator

st.set_page_config(layout="wide")
st.title("Analisador de Criptomoedas com Indicadores Técnicos")

# Função para obter dados da Binance
def obter_dados(symbol, interval, limit=500):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        resposta = requests.get(url)
        dados = resposta.json()
        df = pd.DataFrame(dados, columns=[
            "timestamp", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "number_of_trades",
            "taker_buy_base_volume", "taker_buy_quote_volume", "ignore"
        ])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)
        df = df[["open", "high", "low", "close", "volume"]].astype(float)
        return df
    except Exception as e:
        st.error(f"Erro ao baixar ou processar dados: {e}")
        return pd.DataFrame()

# Interface do usuário
col1, col2, col3 = st.columns(3)

with col1:
    simbolo = st.text_input("Símbolo da Criptomoeda", value="BTCUSDT")
with col2:
    intervalo = st.selectbox("Intervalo do Gráfico", ["1m", "5m", "15m", "1h", "4h", "1d"], index=0)
with col3:
    atualizar = st.number_input("Atualizar a cada X segundos", min_value=10, max_value=3600, value=60, step=10)

# Botão para executar análise
if st.button("Analisar"):
    df = obter_dados(simbolo.upper(), intervalo)

    if df.empty:
        st.warning("Nenhum dado disponível. Verifique o símbolo ou tente novamente mais tarde.")
        st.stop()

    try:
        # Indicadores
        df["MA20"] = SMAIndicator(df["close"], window=20).sma_indicator()
        df["EMA20"] = EMAIndicator(df["close"], window=20).ema_indicator()
        df["Volatility"] = df["close"].rolling(window=20).std()
        df["RSI"] = RSIIndicator(df["close"], window=14).rsi()

        macd = MACD(df["close"])
        df["MACD"] = macd.macd()
        df["MACD_signal"] = macd.macd_signal()
        df["MACD_hist"] = macd.macd_diff()

        if intervalo == "1m" and len(df) >= 100:
            stoch_rsi = StochRSIIndicator(df["close"], window=14)
            df["StochRSI"] = stoch_rsi.stochrsi()

    except Exception as e:
        st.error(f"Erro ao calcular indicadores: {e}")
        st.stop()

    # Gráfico principal com velas e médias móveis
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["open"],
        high=df["high"],
        low=df["low"],
        close=df["close"],
        name="Candlestick",
        increasing_line_color='green', decreasing_line_color='red'
    ))
    fig.add_trace(go.Scatter(x=df.index, y=df["MA20"], mode="lines", name="MA 20", line=dict(color="orange")))
    fig.add_trace(go.Scatter(x=df.index, y=df["EMA20"], mode="lines", name="EMA 20", line=dict(color="blue")))
    fig.update_layout(title="Preço + Médias Móveis", xaxis_title="Data", yaxis_title="Preço (USDT)", height=600)
    st.plotly_chart(fig, use_container_width=True)

    # Gráfico de Volatilidade
    fig_vol = go.Figure()
    fig_vol.add_trace(go.Scatter(x=df.index, y=df["Volatility"], mode="lines", name="Volatilidade", line=dict(color="purple")))
    fig_vol.update_layout(title="Volatilidade (Desvio Padrão 20 períodos)", height=300)
    st.plotly_chart(fig_vol, use_container_width=True)

    # Gráfico RSI
    fig_rsi = go.Figure()
    fig_rsi.add_trace(go.Scatter(x=df.index, y=df["RSI"], mode="lines", name="RSI", line=dict(color="green")))
    fig_rsi.update_layout(title="RSI (14 períodos)", yaxis=dict(range=[0, 100]), height=300)
    st.plotly_chart(fig_rsi, use_container_width=True)

    # Gráfico MACD
    fig_macd = go.Figure()
    fig_macd.add_trace(go.Scatter(x=df.index, y=df["MACD"], name="MACD", line=dict(color="blue")))
    fig_macd.add_trace(go.Scatter(x=df.index, y=df["MACD_signal"], name="Signal", line=dict(color="red")))
    fig_macd.add_trace(go.Bar(x=df.index, y=df["MACD_hist"], name="Histograma", marker_color="gray"))
    fig_macd.update_layout(title="MACD", height=300)
    st.plotly_chart(fig_macd, use_container_width=True)

    # Gráfico StochRSI (se existir)
    if "StochRSI" in df.columns:
        fig_stoch = go.Figure()
        fig_stoch.add_trace(go.Scatter(x=df.index, y=df["StochRSI"], mode="lines", name="StochRSI", line=dict(color="teal")))
        fig_stoch.update_layout(title="Stochastic RSI", yaxis=dict(range=[0, 1]), height=300)
        st.plotly_chart(fig_stoch, use_container_width=True)

    st.caption(f"A cada {atualizar} segundos a análise é atualizada. Recarregue a página para rodar novamente.")
