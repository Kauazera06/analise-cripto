import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
import time
from datetime import datetime
from binance.client import Client

# ========== API CONFIG ==========
API_KEY = ""
API_SECRET = ""
client = Client(API_KEY, API_SECRET)

# ========== INDICADORES ==========
def EMA(df, period=14):
    return df['close'].ewm(span=period, adjust=False).mean()

def RSI(df, period=14):
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def StochRSI(df, period=14, smoothK=3, smoothD=3):
    rsi = RSI(df, period)
    min_rsi = rsi.rolling(window=period).min()
    max_rsi = rsi.rolling(window=period).max()
    stochrsi = (rsi - min_rsi) / (max_rsi - min_rsi)
    K = stochrsi.rolling(window=smoothK).mean()
    D = K.rolling(window=smoothD).mean()
    return K, D

def KDJ(df, period=9, k_period=3, d_period=3):
    low_min = df['low'].rolling(window=period).min()
    high_max = df['high'].rolling(window=period).max()
    rsv = (df['close'] - low_min) / (high_max - low_min) * 100
    K = rsv.ewm(com=k_period-1, adjust=False).mean()
    D = K.ewm(com=d_period-1, adjust=False).mean()
    J = 3 * K - 2 * D
    return K, D, J

# ========== PLOT FUNÇÕES ==========
def plot_candlestick(df):
    fig = go.Figure(data=[go.Candlestick(
        x=df.index,
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='Candlestick'),
        go.Scatter(x=df.index, y=df['EMA_14'], line=dict(color='orange'), name='EMA 14')
    ])
    fig.update_layout(title='Candlestick com EMA 14', height=500)
    return fig

def plot_rsi(df):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI_14'], name='RSI'))
    fig.update_layout(title='RSI', height=400)
    return fig

def plot_stochrsi(df):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df['StochRSI_K'], name='%K'))
    fig.add_trace(go.Scatter(x=df.index, y=df['StochRSI_D'], name='%D'))
    fig.update_layout(title='Stochastic RSI', height=400)
    return fig

def plot_kdj(df):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df['K'], name='K'))
    fig.add_trace(go.Scatter(x=df.index, y=df['D'], name='D'))
    fig.add_trace(go.Scatter(x=df.index, y=df['J'], name='J'))
    fig.update_layout(title='KDJ', height=400)
    return fig

# ========== TELEGRAM ALERTA ==========
def enviar_alerta_telegram(mensagem):
    token = "7507470816:AAFpu1RRtGQYJfv1cuGjRsW4H87ryM1XsRY"
    chat_id = "1705586919"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    params = {"chat_id": chat_id, "text": mensagem}
    try:
        requests.get(url, params=params)
    except Exception as e:
        st.error(f"Erro ao enviar mensagem Telegram: {e}")

# ========== ANALISAR ==========
def analisar(symbol, intervalo):
    try:
        klines = client.get_klines(symbol=symbol, interval=intervalo, limit=500)
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time',
            'quote_asset_volume', 'number_of_trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'])

        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        df = df.astype(float)

        df['EMA_14'] = EMA(df)
        df['RSI_14'] = RSI(df)
        df['StochRSI_K'], df['StochRSI_D'] = StochRSI(df)
        df['K'], df['D'], df['J'] = KDJ(df)
        return df
    except Exception as e:
        st.error(f"Erro na API da Binance: {e}")
        return pd.DataFrame()

# ========== APP STREAMLIT ==========
st.set_page_config(layout="wide")
st.title("📊 Análise Automática de Criptomoedas com Alertas Telegram")

moeda = st.text_input("Símbolo da Criptomoeda (ex: BTCUSDT):", value="BTCUSDT").upper()
intervalo = st.selectbox("Intervalo dos Candles:", ["1m", "5m", "15m", "1h", "4h", "1d"])
tempo = st.number_input("Tempo entre atualizações (em minutos):", min_value=1, value=5)

if 'historico' not in st.session_state:
    st.session_state.historico = []
if 'ultimo_sinal' not in st.session_state:
    st.session_state.ultimo_sinal = "neutro"

placeholder_graficos = st.empty()
placeholder_historico = st.empty()

while True:
    df = analisar(moeda, intervalo)
    if df.empty:
        st.warning("Nenhum dado disponível. Verifique o símbolo ou tente novamente mais tarde.")
        break

    ultimo_rsi = df['RSI_14'].iloc[-1]
    ultimo_k = df['StochRSI_K'].iloc[-1]
    ultimo_j = df['J'].iloc[-1]

    # Define sinal de alerta
    if ultimo_rsi < 30 and ultimo_k < 0.2 and ultimo_j < 20:
        sinal_atual = "compra"
    elif ultimo_rsi > 70 and ultimo_k > 0.8 and ultimo_j > 80:
        sinal_atual = "venda"
    else:
        sinal_atual = "neutro"

    # Atualiza gráficos
    with placeholder_graficos.container():
        st.subheader(f"🔎 Análise da moeda: {moeda}")

        st.plotly_chart(plot_candlestick(df), use_container_width=True)
        st.markdown("""
        **Candlestick + EMA 14:**
        Mostra os movimentos do preço e a média exponencial de 14 períodos para indicar tendências.
        """)

        st.plotly_chart(plot_rsi(df), use_container_width=True)
        st.markdown("""
        **RSI:**
        Mede a força e velocidade das variações de preço. Abaixo de 30 = possível compra, acima de 70 = possível venda.
        """)

        st.plotly_chart(plot_stochrsi(df), use_container_width=True)
        st.markdown("""
        **Stochastic RSI:**
        Mostra momentos de sobrecompra ou sobrevenda mais rapidamente. K e D ajudam a prever reversões.
        """)

        st.plotly_chart(plot_kdj(df), use_container_width=True)
        st.markdown("""
        **KDJ:**
        Combina o estocástico com a linha J para prever reversões de tendência com mais sensibilidade.
        """)

    # Envia alerta e atualiza histórico
    horario = datetime.now().strftime("%H:%M:%S")
    if sinal_atual != st.session_state.ultimo_sinal:
        if sinal_atual == "compra":
            msg = f"🚀 SINAL DE COMPRA ({moeda}) às {horario} | RSI: {ultimo_rsi:.2f} | StochK: {ultimo_k:.2f} | J: {ultimo_j:.2f}"
            enviar_alerta_telegram(msg)
            st.success(msg)
        elif sinal_atual == "venda":
            msg = f"⚠️ SINAL DE VENDA ({moeda}) às {horario} | RSI: {ultimo_rsi:.2f} | StochK: {ultimo_k:.2f} | J: {ultimo_j:.2f}"
            enviar_alerta_telegram(msg)
            st.warning(msg)
        st.session_state.ultimo_sinal = sinal_atual
        st.session_state.historico.append((horario, moeda, sinal_atual))
    else:
        st.session_state.historico.append((horario, moeda, sinal_atual))

    with placeholder_historico.container():
        st.subheader("📜 Histórico de Sinais")
        historico_df = pd.DataFrame(st.session_state.historico, columns=["Horário", "Moeda", "Sinal"])
        st.dataframe(historico_df.tail(20), use_container_width=True)

    time.sleep(tempo * 60)
