
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
import time
from datetime import datetime
import yfinance as yf

st.set_page_config(layout="wide")
st.title("Analisador de Criptomoedas com Alertas e Indicadores Técnicos")

# Seleção de moeda
moeda = st.selectbox("Escolha a moeda", ["BTCUSDT", "ETHUSDT", "BNBUSDT"], index=0)

# === Funções de Indicadores Técnicos ===

def EMA(df, period=14):
    return df['Close'].ewm(span=period, adjust=False).mean()

def RSI(df, period=14):
    delta = df['Close'].diff()
    gain = delta.clip(lower=0)
    loss = -1 * delta.clip(upper=0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def MACD(df):
    ema12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema26 = df['Close'].ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist

def StochRSI(df, period=14):
    rsi = RSI(df, period)
    min_val = rsi.rolling(window=period).min()
    max_val = rsi.rolling(window=period).max()
    return (rsi - min_val) / (max_val - min_val)

def Bollinger_Bands(df, period=20):
    sma = df['Close'].rolling(window=period).mean()
    std = df['Close'].rolling(window=period).std()
    upper = sma + (2 * std)
    lower = sma - (2 * std)
    return upper, lower

def ADX(df, period=14):
    high = df['High']
    low = df['Low']
    close = df['Close']
    plus_dm = high.diff()
    minus_dm = low.diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm > 0] = 0

    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()

    plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
    minus_di = abs(100 * (minus_dm.rolling(window=period).mean() / atr))
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    adx = dx.rolling(window=period).mean()
    return adx

# === Coleta de Dados ===
data = yf.download(moeda, interval="5m", period="1d")
df = pd.DataFrame(data)

# === Cálculo dos Indicadores ===
rsi_val = RSI(df).iloc[-1]
macd_line, signal_line, hist = MACD(df)
macd_line = macd_line.iloc[-1]
signal_line = signal_line.iloc[-1]
hist = hist.iloc[-1]
stoch = StochRSI(df).iloc[-1]
ema7 = EMA(df, 7).iloc[-1]
ema25 = EMA(df, 25).iloc[-1]
adx_val = ADX(df).iloc[-1]
bb_upper, bb_lower = Bollinger_Bands(df)
bb_upper = bb_upper.iloc[-1]
bb_lower = bb_lower.iloc[-1]
preco_atual = df['Close'].iloc[-1]

# === Geração do Sinal de Trade ===
sinal = "⏳ SINAL: Ainda indefinido, aguarde melhor momento"
if (
    rsi_val < 30 and
    stoch < 0.2 and
    macd_line > signal_line and
    preco_atual < ema25 and
    hist > 0 and
    adx_val > 20
):
    sinal = "🟢 Compra"
elif (
    rsi_val > 70 and
    stoch > 0.8 and
    macd_line < signal_line and
    preco_atual > ema25 and
    hist < 0 and
    adx_val > 20
):
    sinal = "🔴 Venda"

# === Gráfico ===
fig = go.Figure()
fig.add_trace(go.Candlestick(x=df.index,
                             open=df['Open'],
                             high=df['High'],
                             low=df['Low'],
                             close=df['Close'], name='Candles'))
fig.add_trace(go.Scatter(x=df.index, y=EMA(df, 7), line=dict(color='blue', width=1), name='EMA 7'))
fig.add_trace(go.Scatter(x=df.index, y=EMA(df, 25), line=dict(color='orange', width=1), name='EMA 25'))
fig.add_trace(go.Scatter(x=df.index, y=Bollinger_Bands(df)[0], line=dict(color='green', width=1), name='BB Upper'))
fig.add_trace(go.Scatter(x=df.index, y=Bollinger_Bands(df)[1], line=dict(color='red', width=1), name='BB Lower'))

fig.update_layout(title=f"Gráfico de {moeda}", xaxis_rangeslider_visible=False)
st.plotly_chart(fig, use_container_width=True)

st.subheader(f"Sinal: {sinal}")
st.write(f"RSI: {rsi_val:.2f}")
st.write(f"MACD: {macd_line:.2f} | Signal: {signal_line:.2f} | Histograma: {hist:.2f}")
st.write(f"StochRSI: {stoch:.2f}")
st.write(f"EMA 7: {ema7:.2f} | EMA 25: {ema25:.2f}")
st.write(f"ADX: {adx_val:.2f}")
st.write(f"Bollinger Bands: Superior = {bb_upper:.2f} | Inferior = {bb_lower:.2f}")

# === Envio de Alerta no Telegram ===
bot_token = "7507470816:AAFpu1RRtGQYJfv1cuGjRsW4H87ryM1XsRY"
chat_id = "1705586919"

def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": mensagem
    }
    try:
        requests.post(url, data=payload)
    except Exception as e:
        st.error(f"Erro ao enviar para o Telegram: {e}")

agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
mensagem = f"""📢 SINAL DE TRADE - {moeda}

Sinal: {sinal}
Preço: ${preco_atual:.2f}
Horário: {agora}

📊 Indicadores:
• RSI: {rsi_val:.2f}
• MACD: {macd_line:.2f}
• Signal: {signal_line:.2f}
• Histograma: {hist:.2f}
• StochRSI: {stoch:.2f}
• EMA 7: {ema7:.2f}
• EMA 25: {ema25:.2f}
• ADX: {adx_val:.2f}
• BB Superior: {bb_upper:.2f}
• BB Inferior: {bb_lower:.2f}
"""

if sinal == "🟢 Compra" or sinal == "🔴 Venda":
    enviar_telegram(mensagem)
