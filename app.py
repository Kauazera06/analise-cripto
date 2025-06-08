import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
from streamlit_autorefresh import st_autorefresh
import yfinance as yf

st.set_page_config(layout="wide")
st.title("Analisador de Criptomoedas com Alertas e Indicadores Técnicos")

# ----------- INDICADORES -------------

def EMA(df, period=14):
    return df['Close'].ewm(span=period, adjust=False).mean()

def RSI(df, period=14):
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def StochRSI(df, period=14, smoothK=3, smoothD=3):
    rsi = RSI(df, period)
    min_rsi = rsi.rolling(window=period).min()
    max_rsi = rsi.rolling(window=period).max()
    stochrsi = (rsi - min_rsi) / (max_rsi - min_rsi)
    K = stochrsi.rolling(window=smoothK).mean()
    D = K.rolling(window=smoothD).mean()
    return K, D

def KDJ(df, period=9, k_period=3, d_period=3):
    low_min = df['Low'].rolling(window=period).min()
    high_max = df['High'].rolling(window=period).max()
    rsv = (df['Close'] - low_min) / (high_max - low_min) * 100
    K = rsv.ewm(com=k_period-1, adjust=False).mean()
    D = K.ewm(com=d_period-1, adjust=False).mean()
    J = 3 * K - 2 * D
    return K, D, J

def MACD(df, fast=12, slow=26, signal=9):
    exp1 = df['Close'].ewm(span=fast, adjust=False).mean()
    exp2 = df['Close'].ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    hist = macd - signal_line
    return macd, signal_line, hist

def BollingerBands(df, period=20, std_dev=2):
    sma = df['Close'].rolling(window=period).mean()
    std = df['Close'].rolling(window=period).std()
    upper = sma + std_dev * std
    lower = sma - std_dev * std
    return sma, upper, lower

def ADX(df, period=14):
    high = df['High']
    low = df['Low']
    close = df['Close']

    plus_dm = high.diff()
    minus_dm = low.diff().abs()

    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)

    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.rolling(window=period).mean()

    plus_di = 100 * (plus_dm.rolling(window=period).sum() / atr)
    minus_di = 100 * (minus_dm.rolling(window=period).sum() / atr)

    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    adx = dx.rolling(window=period).mean()

    return adx

# ----------- TELEGRAM -------------

def enviar_alerta_telegram(mensagem):
    token = "7507470816:AAFpu1RRtGQYJfv1cuGjRsW4H87ryM1XsRY"
    chat_id = "1705586919"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.get(url, params={"chat_id": chat_id, "text": mensagem})
    except Exception as e:
        st.error(f"Erro ao enviar mensagem Telegram: {e}")

# ----------- OBTÉM DADOS -------------

@st.cache_data(ttl=60)
def obter_dados(symbol, period, interval):
    df = yf.download(symbol, period=period, interval=interval)
    df.dropna(inplace=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df['EMA_14'] = EMA(df)
    df['RSI_14'] = RSI(df)
    df['StochRSI_K'], df['StochRSI_D'] = StochRSI(df)
    df['K'], df['D'], df['J'] = KDJ(df)
    df['MACD'], df['MACD_signal'], df['MACD_hist'] = MACD(df)
    df['BB_MA'], df['BB_upper'], df['BB_lower'] = BollingerBands(df)
    df['ADX_14'] = ADX(df)
    return df

# ----------- GRÁFICOS -------------

def plot_candlestick(df, nome):
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"],
        increasing_line_color='green', decreasing_line_color='red',
        name="Preço"
    ))
    fig.add_trace(go.Scatter(x=df.index, y=df["EMA_14"], mode="lines", name="EMA 14", line=dict(color="blue")))
    fig.add_trace(go.Scatter(x=df.index, y=df["BB_upper"], mode="lines", name="Bollinger Sup", line=dict(color="orange", dash="dash")))
    fig.add_trace(go.Scatter(x=df.index, y=df["BB_lower"], mode="lines", name="Bollinger Inf", line=dict(color="orange", dash="dash")))
    fig.add_trace(go.Bar(x=df.index, y=df["Volume"], name="Volume", marker_color='grey', opacity=0.3, yaxis="y2"))
    fig.update_layout(
        title=f"{nome} - Candlestick + Indicadores",
        xaxis_title="Data", yaxis_title="Preço (USD)", height=600,
        xaxis_rangeslider_visible=False,
        yaxis2=dict(overlaying="y", side="right", showgrid=False, position=0.15, title="Volume")
    )
    return fig

def plot_rsi(df, nome):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df["RSI_14"], mode="lines", name="RSI", line=dict(color="green")))
    fig.update_layout(title=f"{nome} - RSI (14 períodos)", yaxis=dict(range=[0, 100]), height=300)
    return fig

def plot_stochrsi(df, nome):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df["StochRSI_K"], mode="lines", name="StochRSI K", line=dict(color="teal")))
    fig.add_trace(go.Scatter(x=df.index, y=df["StochRSI_D"], mode="lines", name="StochRSI D", line=dict(color="orange")))
    fig.update_layout(title=f"{nome} - Stochastic RSI", yaxis=dict(range=[0, 1]), height=300)
    return fig

def plot_kdj(df, nome):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df["K"], mode="lines", name="K", line=dict(color="blue")))
    fig.add_trace(go.Scatter(x=df.index, y=df["D"], mode="lines", name="D", line=dict(color="red")))
    fig.add_trace(go.Scatter(x=df.index, y=df["J"], mode="lines", name="J", line=dict(color="purple")))
    fig.update_layout(title=f"{nome} - Indicador KDJ", height=300)
    return fig

def plot_macd(df, nome):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df["MACD"], mode="lines", name="MACD", line=dict(color="blue")))
    fig.add_trace(go.Scatter(x=df.index, y=df["MACD_signal"], mode="lines", name="Signal", line=dict(color="orange")))
    fig.add_trace(go.Bar(x=df.index, y=df["MACD_hist"], name="Histograma", marker_color="grey"))
    fig.update_layout(title=f"{nome} - MACD", height=300)
    return fig

def plot_adx(df, nome):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df["ADX_14"], mode="lines", name="ADX", line=dict(color="purple")))
    fig.update_layout(title=f"{nome} - ADX (14 períodos)", yaxis=dict(range=[0, 100]), height=300)
    return fig

# ----------- APP PRINCIPAL -------------

def main():
    interval_options = {
        "10 segundos": 10 * 1000,
        "20 segundos": 20 * 1000,
        "30 segundos": 30 * 1000,
        "1 minuto": 60 * 1000,
        "3 minutos": 3 * 60 * 1000,
        "5 minutos": 5 * 60 * 1000
    }
    cripto_opcoes = {
        "Bitcoin": "BTC-USD", "Ethereum": "ETH-USD", "Binance Coin": "BNB-USD",
        "Cardano": "ADA-USD", "Solana": "SOL-USD", "Ripple": "XRP-USD",
        "Polkadot": "DOT-USD", "Litecoin": "LTC-USD", "Syrup": "SYRUP-USD",
        "Dogecoin": "DOGE-USD", "Pepe": "PEPE-USD"
    }

    col1, col2, col3 = st.columns(3)
    with col1:
        nome_moeda = st.selectbox("Escolha a criptomoeda:", list(cripto_opcoes.keys()))
    with col2:
        period = st.selectbox("Período:", ["1mo", "3mo", "6mo", "1y"], index=0)
    with col3:
        interval = st.selectbox("Intervalo:", ["15m", "30m", "1h", "1d"], index=0)

    intervalo_str = st.selectbox("Intervalo entre análises automáticas:", list(interval_options.keys()), index=3)
    intervalo = interval_options[intervalo_str]

    st_autorefresh(interval=intervalo, limit=None, key="analise_crypto")

    symbol = cripto_opcoes[nome_moeda]
    df = obter_dados(symbol, period, interval)

    st.plotly_chart(plot_candlestick(df, nome_moeda), use_container_width=True)
    st.plotly_chart(plot_rsi(df, nome_moeda), use_container_width=True)
    st.plotly_chart(plot_stochrsi(df, nome_moeda), use_container_width=True)
    st.plotly_chart(plot_kdj(df, nome_moeda), use_container_width=True)
    st.plotly_chart(plot_macd(df, nome_moeda), use_container_width=True)
    st.plotly_chart(plot_adx(df, nome_moeda), use_container_width=True)

main()
