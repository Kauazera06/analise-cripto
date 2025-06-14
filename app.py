import streamlit as st
import pandas as pd
import numpy as np
import requests
import datetime
import plotly.graph_objects as go
import pytz
import time
from streamlit_autorefresh import st_autorefresh

st.set_page_config(layout="wide")
st.title("📈 Analisador de Criptomoedas com Indicadores Técnicos e Alertas Telegram")

# Atualização automática a cada 5 minutos
st_autorefresh(interval=300000, key="refresh")

# Inicializa controle de último sinal
if "ultimo_sinal" not in st.session_state:
    st.session_state.ultimo_sinal = ""

# CONFIG TELEGRAM
TOKEN = "7507470816:AAFpu1RRtGQYJfv1cuGjRsW4H87ryM1XsRY"
CHAT_ID = "1705586919"

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

def get_usd_brl():
    try:
        url = "https://economia.awesomeapi.com.br/last/USD-BRL"
        response = requests.get(url)
        data = response.json()
        return float(data["USDBRL"]["bid"])
    except:
        return None

# Indicadores
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

def floor_dt(dt, delta):
    return dt - (dt - datetime.datetime.min.replace(tzinfo=dt.tzinfo)) % delta

# App
moeda = st.selectbox("Escolha a moeda:", ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "SYRUPUSDT", "ENAUSDT", "PEPEUSDT", "USDTUSDT", "ADAUSDT", "DOGEUSDT", "XRPUSDT", "SHIBUSDT"])
df = get_binance_data(moeda)
usd_brl = get_usd_brl()

if not df.empty and len(df) > 30 and usd_brl:
    tz = pytz.timezone("America/Sao_Paulo")
    df.index = df.index.tz_localize('UTC').tz_convert(tz)
    now = datetime.datetime.now(tz)
    interval = datetime.timedelta(minutes=5)
    now_floor = floor_dt(now, interval)
    df_plot = df[df.index <= now_floor]

    rsi_val = RSI(df).iloc[-1]
    macd_line, signal_line, hist = MACD(df)
    macd_val = macd_line.iloc[-1]
    signal_val = signal_line.iloc[-1]
    hist_val = hist.iloc[-1]
    stoch_val = StochRSI(df).iloc[-1]
    adx_val = ADX(df).iloc[-1]
    close = df["Close"].iloc[-1]
    close_brl = close * usd_brl

    if rsi_val < 30 and stoch_val < 0.2 and macd_val > signal_val and adx_val > 20:
        sinal = "🟢 Compra"
    elif rsi_val > 70 and stoch_val > 0.8 and macd_val < signal_val and adx_val > 20:
        sinal = "🔴 Venda"
    else:
        sinal = "⏳ Neutro"

    st.subheader(f"📊 Sinal Atual: {sinal}")
    st.metric("Preço Atual", f"${close:,.2f} | R$ {close_brl:,.2f}")
    st.write(f"- RSI: **{rsi_val:.2f}**")
    st.write(f"- MACD: **{macd_val:.2f}**, Sinal: **{signal_val:.2f}**, Histograma: **{hist_val:.2f}**")
    st.write(f"- StochRSI: **{stoch_val:.2f}**")
    st.write(f"- ADX: **{adx_val:.2f}**")

    agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    mensagem = f"""📢 SINAL DE TRADE - {moeda}
Sinal: {sinal}
Preço: ${close:,.2f} | R$ {close_brl:,.2f}
Data/Horário: {agora}

📊 Indicadores:
RSI: {rsi_val:.2f}
MACD: {macd_val:.2f}
Sinal MACD: {signal_val:.2f}
Histograma: {hist_val:.2f}
StochRSI: {stoch_val:.2f}
ADX: {adx_val:.2f}
"""

    if st.session_state.ultimo_sinal != sinal:
        if enviar_telegram(mensagem):
            st.success("✅ Alerta enviado no Telegram!")
            st.session_state.ultimo_sinal = sinal
    else:
        st.info("ℹ️ Sinal não mudou, alerta não reenviado.")

    # Gráficos técnicos (mantidos conforme estavam)
    with st.expander("📉 Gráficos Técnicos"):
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["RSI", "MACD", "StochRSI", "ADX", "Preço"])

        with tab1:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df_plot.index, y=RSI(df_plot), name="RSI", line=dict(color='blue')))
            fig.add_hline(y=70, line=dict(dash='dash', color='red'))
            fig.add_hline(y=30, line=dict(dash='dash', color='green'))
            fig.update_layout(title="RSI", height=300)
            st.plotly_chart(fig, use_container_width=True)

        with tab2:
            fig = go.Figure()
            macd_plot_line, signal_plot_line, hist_plot = MACD(df_plot)
            fig.add_trace(go.Scatter(x=df_plot.index, y=macd_plot_line, name="MACD", line=dict(color='blue')))
            fig.add_trace(go.Scatter(x=df_plot.index, y=signal_plot_line, name="Sinal", line=dict(color='orange')))
            fig.add_trace(go.Bar(x=df_plot.index, y=hist_plot, name="Histograma", marker_color='gray'))
            fig.update_layout(title="MACD", height=300)
            st.plotly_chart(fig, use_container_width=True)

        with tab3:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df_plot.index, y=StochRSI(df_plot), name="StochRSI", line=dict(color='purple')))
            fig.add_hline(y=0.8, line=dict(dash='dash', color='red'))
            fig.add_hline(y=0.2, line=dict(dash='dash', color='green'))
            fig.update_layout(title="StochRSI", height=300)
            st.plotly_chart(fig, use_container_width=True)

        with tab4:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df_plot.index, y=ADX(df_plot), name="ADX", line=dict(color='darkcyan')))
            fig.add_hline(y=20, line=dict(dash='dash', color='orange'))
            fig.update_layout(title="ADX", height=300)
            st.plotly_chart(fig, use_container_width=True)

        with tab5:
            fig = go.Figure(data=[
                go.Candlestick(
                    x=df_plot.index,
                    open=df_plot["Open"],
                    high=df_plot["High"],
                    low=df_plot["Low"],
                    close=df_plot["Close"],
                    increasing_line_color='green',
                    decreasing_line_color='red',
                    name='Candlestick'
                )
            ])
            fig.update_layout(title="Candlestick - Preço", height=400, xaxis_rangeslider_visible=False)
            fig.update_xaxes(range=[df_plot.index.min(), df_plot.index.max()])
            st.plotly_chart(fig, use_container_width=True)

else:
    st.warning("⚠️ Dados insuficientes ou erro ao converter dólar para real.")
