import streamlit as st
import pandas as pd
import numpy as np
import requests
import datetime
import plotly.graph_objects as go
import pytz
import joblib
import os
import csv
import matplotlib.pyplot as plt

from streamlit_autorefresh import st_autorefresh

st.set_page_config(layout="wide")
st.title("📈 Analisador de Criptomoedas com Indicadores Técnicos, IA e Sinais de Alerta via Telegram")
st_autorefresh(interval=60000, key="auto_refresh")

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

def get_usd_brl():
    try:
        res = requests.get("https://economia.awesomeapi.com.br/json/last/USD-BRL")
        return float(res.json()["USDBRL"]["bid"])
    except:
        return None

def get_binance_data(symbol="BTCUSDT", interval="5m", limit=100):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        data = requests.get(url).json()
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data, columns=["timestamp", "Open", "High", "Low", "Close", "Volume", "Close_time",
                                         "Quote_asset_volume", "Number_of_trades", "Taker_buy_base_volume",
                                         "Taker_buy_quote_volume", "Ignore"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)
        return df.astype(float)
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
    return 100 - (100 / (1 + rs))

def MACD(df):
    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    return macd_line, signal_line, macd_line - signal_line

def StochRSI(df, period=14):
    rsi = RSI(df, period)
    min_val = rsi.rolling(window=period).min()
    max_val = rsi.rolling(window=period).max()
    return (rsi - min_val) / (max_val - min_val)

def ADX(df, period=14):
    df2 = df.copy()
    df2["TR"] = np.maximum(df2["High"] - df2["Low"], np.maximum(abs(df2["High"] - df2["Close"].shift(1)), abs(df2["Low"] - df2["Close"].shift(1))))
    df2["+DM"] = np.where((df2["High"] - df2["High"].shift(1)) > (df2["Low"].shift(1) - df2["Low"]), np.maximum(df2["High"] - df2["High"].shift(1), 0), 0)
    df2["-DM"] = np.where((df2["Low"].shift(1) - df2["Low"]) > (df2["High"] - df2["High"].shift(1)), np.maximum(df2["Low"].shift(1) - df2["Low"], 0), 0)
    tr14 = df2["TR"].rolling(window=period).sum()
    plus_dm14 = df2["+DM"].rolling(window=period).sum()
    minus_dm14 = df2["-DM"].rolling(window=period).sum()
    plus_di14 = 100 * (plus_dm14 / tr14)
    minus_di14 = 100 * (minus_dm14 / tr14)
    dx = 100 * abs(plus_di14 - minus_di14) / (plus_di14 + minus_di14)
    return dx.rolling(window=period).mean()

def floor_dt(dt, delta):
    seconds = (dt - datetime.datetime.min.replace(tzinfo=dt.tzinfo)).total_seconds()
    delta_seconds = delta.total_seconds()
    floored = seconds - (seconds % delta_seconds)
    return datetime.datetime.min.replace(tzinfo=dt.tzinfo) + datetime.timedelta(seconds=floored)

try:
    modelo_ia = joblib.load("modelo_trade_ia.pkl")
except Exception as e:
    st.error(f"Erro ao carregar modelo IA: {e}")
    modelo_ia = None

moeda = st.selectbox("Escolha a moeda:", ["BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT"])
df = get_binance_data(moeda)

if not df.empty and len(df) > 30:
    tz = pytz.timezone("America/Sao_Paulo")
    df.index = df.index.tz_localize('UTC').tz_convert(tz)
    now = datetime.datetime.now(tz)
    now_floor = floor_dt(now, datetime.timedelta(minutes=5))
    df_plot = df[df.index <= now_floor]

    rsi_val = RSI(df).iloc[-1]
    macd_line, signal_line, hist = MACD(df)
    macd_val, signal_val, hist_val = macd_line.iloc[-1], signal_line.iloc[-1], hist.iloc[-1]
    stoch_val = StochRSI(df).iloc[-1]
    adx_val = ADX(df).iloc[-1]
    close = df["Close"].iloc[-1]
    usd_brl = get_usd_brl()
    preco_brl = close * usd_brl if usd_brl else None

    sinal = "🟢 Compra" if rsi_val < 30 and stoch_val < 0.2 and macd_val > signal_val and adx_val > 20 \
            else "🔴 Venda" if rsi_val > 70 and stoch_val > 0.8 and macd_val < signal_val and adx_val > 20 else "⏳ Neutro"

    if modelo_ia is not None:
        pred = modelo_ia.predict(np.array([[rsi_val, macd_val, signal_val, hist_val, stoch_val, adx_val]]))[0]
        sinal_ia = {0: "🔴 Venda", 1: "⏳ Neutro", 2: "🟢 Compra"}.get(pred, "⏳ Neutro")
    else:
        sinal_ia = "Modelo IA não carregado"

    st.subheader(f"📊 Sinal Atual (Indicadores): {sinal}")
    st.metric("Preço Atual", f"${close:,.2f}" + (f" / R$ {preco_brl:,.2f}" if preco_brl else ""))
    st.write(f"- RSI: **{rsi_val:.2f}**")
    st.write(f"- MACD: **{macd_val:.2f}**, Sinal: **{signal_val:.2f}**, Histograma: **{hist_val:.2f}**")
    st.write(f"- StochRSI: **{stoch_val:.2f}**")
    st.write(f"- ADX: **{adx_val:.2f}**")
    st.subheader(f"🤖 Sinal IA: {sinal_ia}")

    agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    mensagem = f"""📢 SINAL DE TRADE - {moeda}
Sinal: {sinal}
Preço: ${close:,.2f}"""
    if preco_brl:
        mensagem += f" / R$ {preco_brl:,.2f}"
    mensagem += f"""
Data/Horário: {agora}

📊 Indicadores:
RSI: {rsi_val:.2f}
MACD: {macd_val:.2f}
Sinal MACD: {signal_val:.2f}
Histograma: {hist_val:.2f}
StochRSI: {stoch_val:.2f}
ADX: {adx_val:.2f}

🤖 Sinal IA: {sinal_ia}
"""

    ultimo_sinal_path = f"ultimo_sinal_{moeda}.txt"
    historico_csv = f"historico_sinais_{moeda}.csv"

    def sinal_mudou(novo):
        if not os.path.exists(ultimo_sinal_path):
            with open(ultimo_sinal_path, "w", encoding="utf-8") as f:
                f.write(novo)
            return True
        with open(ultimo_sinal_path, "r", encoding="utf-8") as f:
            anterior = f.read().strip()
        if novo != anterior:
            with open(ultimo_sinal_path, "w", encoding="utf-8") as f:
                f.write(novo)
            return True
        return False

    if sinal_mudou(sinal_ia):
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        file_exists = os.path.isfile(historico_csv)
        with open(historico_csv, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow(["timestamp", "sinal_ia"])
            writer.writerow([now_str, sinal_ia])

        if enviar_telegram(mensagem):
            st.success("✅ Novo alerta IA enviado no Telegram!")
    else:
        st.info("ℹ️ Nenhuma mudança de sinal IA. Alerta não enviado.")

    # Mostrar gráfico histórico
    if os.path.exists(historico_csv):
        df_historico = pd.read_csv(historico_csv, parse_dates=["timestamp"])
        mapeamento = {"🔴 Venda": -1, "⏳ Neutro": 0, "🟢 Compra": 1}
        df_historico['sinal_num'] = df_historico['sinal_ia'].map(mapeamento).fillna(0)

        st.subheader("📈 Evolução dos Sinais IA ao longo do tempo")
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(df_historico['timestamp'], df_historico['sinal_num'], marker='o', linestyle='-')
        ax.set_yticks([-1, 0, 1])
        ax.set_yticklabels(["Venda 🔴", "Neutro ⏳", "Compra 🟢"])
        ax.set_xlabel("Data/Hora")
        ax.set_ylabel("Sinal IA")
        ax.grid(True)
        st.pyplot(fig)
    else:
        st.info("Nenhum histórico de sinais IA encontrado ainda.")

    # Gráficos técnicos
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
            macd_l, signal_l, histo = MACD(df_plot)
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df_plot.index, y=macd_l, name="MACD", line=dict(color='blue')))
            fig.add_trace(go.Scatter(x=df_plot.index, y=signal_l, name="Sinal", line=dict(color='orange')))
            fig.add_trace(go.Bar(x=df_plot.index, y=histo, name="Histograma", marker_color='gray'))
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
            fig = go.Figure(data=[go.Candlestick(
                x=df_plot.index,
                open=df_plot["Open"],
                high=df_plot["High"],
                low=df_plot["Low"],
                close=df_plot["Close"],
                increasing_line_color='green',
                decreasing_line_color='red',
                name='Candlestick'
            )])
            fig.update_layout(title="Candlestick - Preço", height=400)
            st.plotly_chart(fig, use_container_width=True)

else:
    st.warning("⚠️ Dados insuficientes. Verifique a conexão com a API ou aguarde alguns minutos.")
