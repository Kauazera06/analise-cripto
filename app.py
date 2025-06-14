import streamlit as st
import pandas as pd
import numpy as np
import requests
import datetime

st.set_page_config(layout="wide")
st.title("🔍 Analisador de Criptomoedas com Indicadores Técnicos e Alertas Telegram")

# ========== CONFIGURAÇÕES ==========
TOKEN = "7507470816:AAFpu1RRtGQYJfv1cuGjRsW4H87ryM1XsRY"
CHAT_ID = "1705586919"

# ========== FUNÇÕES ==========

def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": mensagem}
    try:
        response = requests.post(url, data=data)
        return response.status_code == 200
    except:
        return False

def get_binance_data(symbol="BTCUSDT", interval="5m", limit=100):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        response = requests.get(url)
        data = response.json()
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data, columns=[
            "timestamp", "Open", "High", "Low", "Close", "Volume",
            "Close_time", "Quote_asset_volume", "Number_of_trades",
            "Taker_buy_base_volume", "Taker_buy_quote_volume", "Ignore"
        ])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)
        df = df.astype(float)
        return df
    except Exception as e:
        st.error(f"Erro ao buscar dados da Binance: {e}")
        return pd.DataFrame()

def RSI(df, period=14):
    delta = df["Close"].diff()
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    avg_gain = pd.Series(gain).rolling(window=period).mean()
    avg_loss = pd.Series(loss).rolling(window=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def MACD(df):
    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def StochRSI(df, period=14):
    rsi = RSI(df, period)
    min_val = rsi.rolling(window=period).min()
    max_val = rsi.rolling(window=period).max()
    stoch_rsi = (rsi - min_val) / (max_val - min_val)
    return stoch_rsi

def ADX(df, period=14):
    df["TR"] = np.maximum(df["High"] - df["Low"],
                          np.maximum(abs(df["High"] - df["Close"].shift(1)),
                                     abs(df["Low"] - df["Close"].shift(1))))
    df["+DM"] = np.where((df["High"] - df["High"].shift(1)) > (df["Low"].shift(1) - df["Low"]),
                         np.maximum(df["High"] - df["High"].shift(1), 0), 0)
    df["-DM"] = np.where((df["Low"].shift(1) - df["Low"]) > (df["High"] - df["High"].shift(1)),
                         np.maximum(df["Low"].shift(1) - df["Low"], 0), 0)
    tr14 = df["TR"].rolling(window=period).sum()
    plus_dm14 = df["+DM"].rolling(window=period).sum()
    minus_dm14 = df["-DM"].rolling(window=period).sum()
    plus_di14 = 100 * (plus_dm14 / tr14)
    minus_di14 = 100 * (minus_dm14 / tr14)
    dx = 100 * abs(plus_di14 - minus_di14) / (plus_di14 + minus_di14)
    adx = dx.rolling(window=period).mean()
    return adx

def Bollinger_Bands(df, window=20, num_std=2):
    rolling_mean = df["Close"].rolling(window).mean()
    rolling_std = df["Close"].rolling(window).std()
    upper = rolling_mean + (rolling_std * num_std)
    lower = rolling_mean - (rolling_std * num_std)
    return upper, lower

# ========== EXECUÇÃO ==========
moeda = st.selectbox("Escolha a moeda:", ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"])
df = get_binance_data(moeda)

if not df.empty and len(df) > 30:
    rsi_val = RSI(df).iloc[-1]
    macd_line, signal_line, hist = MACD(df)
    macd_val = macd_line.iloc[-1]
    signal_val = signal_line.iloc[-1]
    hist_val = hist.iloc[-1]
    stoch_val = StochRSI(df).iloc[-1]
    adx_val = ADX(df).iloc[-1]
    close = df["Close"].iloc[-1]

    # ========== LÓGICA DE SINAL ==========
    if rsi_val < 30 and stoch_val < 0.2 and macd_val > signal_val and adx_val > 20:
        sinal = "🟢 Compra"
    elif rsi_val > 70 and stoch_val > 0.8 and macd_val < signal_val and adx_val > 20:
        sinal = "🔴 Venda"
    else:
        sinal = "⏳ Neutro"

    st.subheader(f"📊 Sinal Atual: {sinal}")
    st.metric("Preço Atual", f"${close:,.2f}")
    st.write(f"- RSI: **{rsi_val:.2f}**")
    st.write(f"- MACD: **{macd_val:.2f}**, Sinal: **{signal_val:.2f}**, Histograma: **{hist_val:.2f}**")
    st.write(f"- StochRSI: **{stoch_val:.2f}**")
    st.write(f"- ADX: **{adx_val:.2f}**")

    # ========== ALERTA TELEGRAM ==========
    agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    mensagem = f"""📢 SINAL DE TRADE - {moeda}
Sinal: {sinal}
Preço: ${close:,.2f}
Horário: {agora}

📊 Indicadores:
RSI: {rsi_val:.2f}
MACD: {macd_val:.2f}
Sinal MACD: {signal_val:.2f}
Histograma: {hist_val:.2f}
StochRSI: {stoch_val:.2f}
ADX: {adx_val:.2f}
"""

    if enviar_telegram(mensagem):
        st.success("✅ Alerta enviado no Telegram!")
    else:
        st.warning("⚠️ Erro ao enviar o alerta no Telegram.")
else:
    st.warning("Dados insuficientes para análise. Verifique a conexão com a API da Binance.")
