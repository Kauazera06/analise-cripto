import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objs as go
import requests
import time
import datetime
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import MACD, EMAIndicator, ADXIndicator
from ta.volatility import BollingerBands
import telegram

# Telegram bot setup
telegram_token = st.secrets["7507470816:AAFpu1RRtGQYJfv1cuGjRsW4H87ryM1XsRY"]
chat_id = st.secrets["1705586919"]
bot = telegram.Bot(token=telegram_token)

def send_alert(message):
    try:
        bot.send_message(chat_id=chat_id, text=message)
    except Exception as e:
        st.error(f"Erro ao enviar alerta: {e}")

# Função para pegar dados
@st.cache_data(ttl=300)
def get_klines(symbol, interval, limit=500):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    data = requests.get(url).json()
    df = pd.DataFrame(data, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'number_of_trades',
        'taker_buy_base', 'taker_buy_quote', 'ignore'
    ])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    df = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
    return df

# Título
st.title("Análise Técnica de Criptomoedas")
st.markdown("Este sistema utiliza diversos indicadores técnicos para identificar possíveis oportunidades de **compra** ou **venda**. Os gráficos abaixo explicam o comportamento atual da criptomoeda selecionada.")

symbol = st.sidebar.text_input("Símbolo da criptomoeda (ex: BTCUSDT)", value="BTCUSDT")
interval = st.sidebar.selectbox("Intervalo do gráfico", ["1m", "5m", "15m", "1h", "4h", "1d"], index=3)
data = get_klines(symbol, interval)

# Cálculo de indicadores
rsi = RSIIndicator(close=data['close'], window=14).rsi()
stoch = StochasticOscillator(high=data['high'], low=data['low'], close=data['close'], window=14, smooth_window=3)
macd = MACD(close=data['close'])
ema20 = EMAIndicator(close=data['close'], window=20).ema_indicator()
ema50 = EMAIndicator(close=data['close'], window=50).ema_indicator()
bb = BollingerBands(close=data['close'], window=20, window_dev=2)
adx = ADXIndicator(high=data['high'], low=data['low'], close=data['close'], window=14).adx()

# KDJ
low_min = data['low'].rolling(window=14).min()
high_max = data['high'].rolling(window=14).max()
rsv = 100 * (data['close'] - low_min) / (high_max - low_min)
k = rsv.ewm(alpha=1/3).mean()
d = k.ewm(alpha=1/3).mean()
j = 3 * k - 2 * d

# Bollinger bands
upper_band = bb.bollinger_hband()
lower_band = bb.bollinger_lband()

# Sinais baseados nos indicadores principais
latest = -1
rsi_val = rsi.iloc[latest]
stoch_k = stoch.stoch().iloc[latest]
macd_diff = macd.macd_diff().iloc[latest]
macd_cross = "bullish" if macd.macd_diff().iloc[-2] < 0 and macd.macd_diff().iloc[-1] > 0 else "bearish" if macd.macd_diff().iloc[-2] > 0 and macd.macd_diff().iloc[-1] < 0 else "neutro"
close_price = data['close'].iloc[latest]
adx_val = adx.iloc[latest]
k_val, d_val, j_val = k.iloc[latest], d.iloc[latest], j.iloc[latest]

sinal = "neutro"
if (rsi_val < 30 and stoch_k < 20 and j_val < 20 and macd_cross == "bullish" and close_price < lower_band.iloc[latest] and adx_val > 20):
    sinal = "compra"
elif (rsi_val > 70 and stoch_k > 80 and j_val > 80 and macd_cross == "bearish" and close_price > upper_band.iloc[latest] and adx_val > 20):
    sinal = "venda"

st.subheader(f"Sinal gerado: {sinal.upper()}")
if sinal != "neutro":
    send_alert(f"ALERTA {sinal.upper()} detectado para {symbol} no intervalo {interval}!")

# Histórico de sinais
if "historico" not in st.session_state:
    st.session_state.historico = []
st.session_state.historico.append({
    "data": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "cripto": symbol,
    "intervalo": interval,
    "sinal": sinal
})
st.dataframe(pd.DataFrame(st.session_state.historico)[::-1], use_container_width=True)

# GRÁFICOS
fig = go.Figure()
fig.add_trace(go.Candlestick(x=data.index, open=data['open'], high=data['high'], low=data['low'], close=data['close'], name='Candles'))
fig.add_trace(go.Scatter(x=data.index, y=ema20, mode='lines', name='EMA 20'))
fig.add_trace(go.Scatter(x=data.index, y=ema50, mode='lines', name='EMA 50'))
st.subheader("Gráfico Candlestick com Médias Móveis")
st.markdown("Este gráfico mostra o comportamento de preços (candlestick) junto das médias móveis exponenciais de 20 e 50 períodos, úteis para identificar tendências.")
st.plotly_chart(fig, use_container_width=True)

fig_rsi = go.Figure()
fig_rsi.add_trace(go.Scatter(x=data.index, y=rsi, name='RSI'))
fig_rsi.add_hline(y=70, line=dict(color='red', dash='dash'))
fig_rsi.add_hline(y=30, line=dict(color='green', dash='dash'))
st.subheader("RSI - Índice de Força Relativa")
st.markdown("RSI mede a velocidade e mudança dos movimentos de preço. Valores abaixo de 30 indicam sobrevenda (potencial compra); acima de 70 indicam sobrecompra (potencial venda).")
st.plotly_chart(fig_rsi, use_container_width=True)

fig_stoch = go.Figure()
fig_stoch.add_trace(go.Scatter(x=data.index, y=stoch.stoch(), name='%K'))
fig_stoch.add_trace(go.Scatter(x=data.index, y=stoch.stoch_signal(), name='%D'))
st.subheader("Stochastic RSI")
st.markdown("StochRSI é útil para identificar zonas de sobrecompra (>80) e sobrevenda (<20), além de cruzamentos entre %K e %D como sinais.")
st.plotly_chart(fig_stoch, use_container_width=True)

fig_kdj = go.Figure()
fig_kdj.add_trace(go.Scatter(x=data.index, y=k, name='K'))
fig_kdj.add_trace(go.Scatter(x=data.index, y=d, name='D'))
fig_kdj.add_trace(go.Scatter(x=data.index, y=j, name='J'))
st.subheader("KDJ")
st.markdown("KDJ é uma variação do estocástico, onde o J pode antecipar movimentos. Valores extremos (J > 80 ou J < 20) sugerem possíveis reversões.")
st.plotly_chart(fig_kdj, use_container_width=True)

fig_macd = go.Figure()
fig_macd.add_trace(go.Scatter(x=data.index, y=macd.macd(), name='MACD'))
fig_macd.add_trace(go.Scatter(x=data.index, y=macd.macd_signal(), name='Sinal'))
fig_macd.add_trace(go.Bar(x=data.index, y=macd.macd_diff(), name='Histograma'))
st.subheader("MACD")
st.markdown("MACD mostra a relação entre duas EMAs. Cruzamentos entre a linha MACD e a linha de sinal indicam possíveis pontos de entrada ou saída.")
st.plotly_chart(fig_macd, use_container_width=True)

fig_bb = go.Figure()
fig_bb.add_trace(go.Scatter(x=data.index, y=data['close'], name='Close'))
fig_bb.add_trace(go.Scatter(x=data.index, y=upper_band, name='Upper Band'))
fig_bb.add_trace(go.Scatter(x=data.index, y=lower_band, name='Lower Band'))
st.subheader("Bollinger Bands")
st.markdown("Bollinger Bands medem volatilidade. Quando o preço toca a banda inferior ou superior, pode indicar reversão. Bandas estreitas sugerem consolidação.")
st.plotly_chart(fig_bb, use_container_width=True)

fig_adx = go.Figure()
fig_adx.add_trace(go.Scatter(x=data.index, y=adx, name='ADX'))
st.subheader("ADX - Índice de Direção Média")
st.markdown("O ADX mede a força da tendência. Valores acima de 20-25 indicam tendência forte, abaixo disso indicam lateralização.")
st.plotly_chart(fig_adx, use_container_width=True)

st.markdown("---")
st.caption("Todos os sinais e gráficos são apenas educacionais. Faça sua própria análise antes de operar no mercado.")
