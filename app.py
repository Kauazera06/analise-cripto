import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
import time
import ta
from streamlit_autorefresh import st_autorefresh

st.set_page_config(layout="wide")
st.title("Analisador de Criptomoedas com Indicadores Técnicos")

# Controle de atualização automática a cada X segundos
col1, col2, col3 = st.columns(3)
with col1:
    simbolo = st.text_input("Símbolo da Criptomoeda", value="BTCUSDT")
with col2:
    intervalo = st.selectbox("Intervalo do Gráfico", ["1m", "5m", "15m", "1h", "4h", "1d"], index=0)
with col3:
    atualizar = st.number_input("Atualizar a cada X segundos", min_value=10, max_value=3600, value=60, step=10)

# Implementa auto refresh
count = st_autorefresh(interval=atualizar * 1000, limit=None, key="auto_refresh")

# Função para obter dados da Binance
@st.cache_data(ttl=60)
def obter_dados(symbol, interval, limit=500):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        resposta = requests.get(url)
        dados = resposta.json()
        if isinstance(dados, dict) and dados.get("code"):
            st.error(f"Erro na API da Binance: {dados.get('msg', 'Erro desconhecido')}")
            return pd.DataFrame()
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

df = obter_dados(simbolo.upper(), intervalo)

if df.empty:
    st.warning("Nenhum dado disponível. Verifique o símbolo ou tente novamente mais tarde.")
    st.stop()

# Calcular indicadores técnicos
try:
    df["MA"] = df["close"].rolling(window=20).mean()
    df["EMA"] = df["close"].ewm(span=20, adjust=False).mean()
    df["Volatility"] = df["close"].rolling(window=20).std()
    df["RSI"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()

    macd_indicator = ta.trend.MACD(df["close"])
    df["MACD"] = macd_indicator.macd()
    df["MACD_signal"] = macd_indicator.macd_signal()
    df["MACD_hist"] = macd_indicator.macd_diff()

    if intervalo == "1m" and len(df) >= 300:
        stochrsi = ta.momentum.StochRSIIndicator(df["close"], window=14)
        df["StochRSI"] = stochrsi.stochrsi()
except Exception as e:
    st.error(f"Erro ao calcular indicadores: {e}")
    st.stop()

# Usar session_state para guardar o histórico das análises
if "historico" not in st.session_state:
    st.session_state["historico"] = []

# Montar o gráfico principal
def plot_candlestick(df):
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
    fig.add_trace(go.Scatter(x=df.index, y=df["MA"], mode="lines", name="MA 20", line=dict(color="orange")))
    fig.add_trace(go.Scatter(x=df.index, y=df["EMA"], mode="lines", name="EMA 20", line=dict(color="blue")))
    fig.update_layout(title="Preço + Médias Móveis", xaxis_title="Data", yaxis_title="Preço (USDT)", height=600)
    return fig

def plot_volatility(df):
    fig_vol = go.Figure()
    fig_vol.add_trace(go.Scatter(x=df.index, y=df["Volatility"], mode="lines", name="Volatilidade", line=dict(color="purple")))
    fig_vol.update_layout(title="Volatilidade (Desvio Padrão 20 períodos)", height=300)
    return fig_vol

def plot_rsi(df):
    fig_rsi = go.Figure()
    fig_rsi.add_trace(go.Scatter(x=df.index, y=df["RSI"], mode="lines", name="RSI", line=dict(color="green")))
    fig_rsi.update_layout(title="RSI (14 períodos)", yaxis=dict(range=[0, 100]), height=300)
    return fig_rsi

def plot_macd(df):
    fig_macd = go.Figure()
    fig_macd.add_trace(go.Scatter(x=df.index, y=df["MACD"], name="MACD", line=dict(color="blue")))
    fig_macd.add_trace(go.Scatter(x=df.index, y=df["MACD_signal"], name="Signal", line=dict(color="red")))
    fig_macd.add_trace(go.Bar(x=df.index, y=df["MACD_hist"], name="Histograma", marker_color="gray"))
    fig_macd.update_layout(title="MACD", height=300)
    return fig_macd

def plot_stochrsi(df):
    fig_stoch = go.Figure()
    fig_stoch.add_trace(go.Scatter(x=df.index, y=df["StochRSI"], mode="lines", name="StochRSI", line=dict(color="teal")))
    fig_stoch.update_layout(title="Stochastic RSI", yaxis=dict(range=[0, 1]), height=300)
    return fig_stoch

# Gerar gráficos
fig = plot_candlestick(df)
fig_vol = plot_volatility(df)
fig_rsi = plot_rsi(df)
fig_macd = plot_macd(df)
fig_stoch = plot_stochrsi(df) if "StochRSI" in df.columns else None

# Guardar as análises atuais no histórico para mostrar tudo na tela
st.session_state["historico"].append({
    "timestamp": df.index[-1],
    "simbolo": simbolo.upper(),
    "intervalo": intervalo,
    "fig": fig,
    "fig_vol": fig_vol,
    "fig_rsi": fig_rsi,
    "fig_macd": fig_macd,
    "fig_stoch": fig_stoch
})

# Mostrar histórico com os gráficos, um abaixo do outro
for i, entry in enumerate(reversed(st.session_state["historico"][-10:])):  # Últimas 10 análises
    st.markdown(f"### Análise #{len(st.session_state['historico']) - i} - {entry['simbolo']} ({entry['intervalo']}) às {entry['timestamp']}")
    st.plotly_chart(entry["fig"], use_container_width=True)
    st.plotly_chart(entry["fig_vol"], use_container_width=True)
    st.plotly_chart(entry["fig_rsi"], use_container_width=True)
    st.plotly_chart(entry["fig_macd"], use_container_width=True)
    if entry["fig_stoch"]:
        st.plotly_chart(entry["fig_stoch"], use_container_width=True)

st.caption(f"A análise é atualizada automaticamente a cada {atualizar} segundos.")

