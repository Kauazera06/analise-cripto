import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
from streamlit_autorefresh import st_autorefresh
import yfinance as yf

st.set_page_config(layout="wide")
st.title("Analisador de Criptomoedas com Alertas e Indicadores Técnicos")

# ---------------- INDICADORES ----------------

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
    ema_fast = EMA(df, fast)
    ema_slow = EMA(df, slow)
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist

def Bollinger_Bands(df, period=20):
    sma = df['Close'].rolling(window=period).mean()
    std = df['Close'].rolling(window=period).std()
    upper_band = sma + 2 * std
    lower_band = sma - 2 * std
    return sma, upper_band, lower_band

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
    plus_di = 100 * (plus_dm.ewm(alpha=1/period).mean() / atr)
    minus_di = abs(100 * (minus_dm.ewm(alpha=1/period).mean() / atr))
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    adx = dx.ewm(alpha=1/period).mean()
    return adx

# ---------------- ALERTAS TELEGRAM ----------------

def enviar_alerta_telegram(mensagem):
    token = "7507470816:AAFpu1RRtGQYJfv1cuGjRsW4H87ryM1XsRY"
    chat_id = "1705586919"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.get(url, params={"chat_id": chat_id, "text": mensagem})
    except Exception as e:
        st.error(f"Erro ao enviar mensagem Telegram: {e}")

# ---------------- OBTÉM DADOS ----------------

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
    df['MACD'], df['MACD_Signal'], df['MACD_Hist'] = MACD(df)
    df['SMA'], df['BB_Upper'], df['BB_Lower'] = Bollinger_Bands(df)
    df['ADX'] = ADX(df)
    return df

# ---------------- GRÁFICOS ----------------

def plot_candlestick(df, nome):
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"],
        increasing_line_color='green', decreasing_line_color='red'
    ))
    fig.add_trace(go.Scatter(x=df.index, y=df["EMA_14"], name="EMA 14", line=dict(color="blue")))
    fig.add_trace(go.Scatter(x=df.index, y=df["BB_Upper"], name="Bollinger Upper", line=dict(color="purple", dash="dot")))
    fig.add_trace(go.Scatter(x=df.index, y=df["BB_Lower"], name="Bollinger Lower", line=dict(color="purple", dash="dot")))
    fig.update_layout(title=f"{nome} - Preço + Indicadores", height=600)
    return fig

def plot_rsi(df):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df["RSI_14"], name="RSI", line=dict(color="green")))
    fig.update_layout(title="RSI", yaxis=dict(range=[0, 100]), height=300)
    return fig

def plot_stochrsi(df): 
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df["StochRSI_K"], name="StochRSI K", line=dict(color="teal")))
    fig.add_trace(go.Scatter(x=df.index, y=df["StochRSI_D"], name="StochRSI D", line=dict(color="orange")))
    fig.update_layout(title="Stochastic RSI", yaxis=dict(range=[0, 1]), height=300)
    return fig

def plot_kdj(df): 
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df["K"], name="K", line=dict(color="blue")))
    fig.add_trace(go.Scatter(x=df.index, y=df["D"], name="D", line=dict(color="red")))
    fig.add_trace(go.Scatter(x=df.index, y=df["J"], name="J", line=dict(color="purple")))
    fig.update_layout(title="Indicador KDJ", height=300)
    return fig

def plot_macd(df):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df["MACD"], name="MACD", line=dict(color="blue")))
    fig.add_trace(go.Scatter(x=df.index, y=df["MACD_Signal"], name="Signal", line=dict(color="orange")))
    fig.add_trace(go.Bar(x=df.index, y=df["MACD_Hist"], name="Histograma", marker_color="gray"))
    fig.update_layout(title="MACD", height=300)
    return fig

def plot_adx(df):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df["ADX"], name="ADX", line=dict(color="red")))
    fig.update_layout(title="ADX", height=300)
    return fig

# ---------------- APP ----------------

def main():
    cripto_opcoes = {
        "Bitcoin": "BTC-USD", "Ethereum": "ETH-USD", "Solana": "SOL-USD",
        "Binance Coin": "BNB-USD", "ENA":"ENA-USD", "SYRUP":"SYRUP-USD", "Cardano": "ADA-USD", "Dogecoin": "DOGE-USD"
    }

    col1, col2, col3 = st.columns(3)
    with col1:
        nome_moeda = st.selectbox("Criptomoeda:", list(cripto_opcoes.keys()))
    with col2:
        period = st.selectbox("Período:", ["1mo", "3mo", "6mo", "1y"])
    with col3:
        interval = st.selectbox("Intervalo de velas:", ["15m", "30m", "1h", "1d"])

    refresh_opcoes = {
        "10 segundos": 10_000, "20 segundos": 20_000, "30 segundos": 30_000,
        "1 minuto": 60_000, "3 minutos": 180_000, "5 minutos": 300_000
    }
    refresh_select = st.selectbox("Intervalo de atualização automática:", list(refresh_opcoes.keys()), index=3)
    st_autorefresh(interval=refresh_opcoes[refresh_select], limit=None, key="refresh")

    symbol = cripto_opcoes[nome_moeda]

    if "historico" not in st.session_state:
        st.session_state.historico = []
    if "ultimo_sinal" not in st.session_state:
        st.session_state.ultimo_sinal = "neutro"

    df = obter_dados(symbol, period, interval)
    if df.empty or len(df) < 2:
        st.warning("Sem dados suficientes.")
        return

    rsi = df.get('RSI_14', pd.Series()).iloc[-1]
    stoch_k = df.get('StochRSI_K', pd.Series()).iloc[-1]
    j = df.get('J', pd.Series()).iloc[-1]

    sinal = "neutro"
    if pd.notna(rsi) and pd.notna(stoch_k) and pd.notna(j):
        if rsi < 30 and stoch_k < 0.2 and j < 20:
            sinal = "compra"
        elif rsi > 70 and stoch_k > 0.8 and j > 80:
            sinal = "venda"

    if sinal != st.session_state.ultimo_sinal:
        msg = f"{'🚀 COMPRA' if sinal == 'compra' else '⚠️ VENDA'} para {nome_moeda} (RSI={rsi:.2f}, StochRSI_K={stoch_k:.2f}, J={j:.2f})"
        enviar_alerta_telegram(msg)
        st.toast(msg)
        st.session_state.ultimo_sinal = sinal
    else:
        st.info(f"Sinal atual: {sinal}.")

    st.session_state.historico.append({
        "timestamp": pd.Timestamp.now(), "moeda": nome_moeda,
        "sinal": sinal, "RSI": round(rsi, 2),
        "StochRSI_K": round(stoch_k, 2), "KDJ_J": round(j, 2)
    })

    # Gráficos em ordem vertical e explicações detalhadas

    st.plotly_chart(plot_candlestick(df, nome_moeda), use_container_width=True)
    st.markdown("""
### 📈 Candlestick com EMA e Bollinger Bands  
Mostra a ação do preço com:
- **Candlestick**: visual das velas (abertura, máxima, mínima, fechamento).
- **EMA (Exponential Moving Average)**: suaviza a tendência de preço.  
  - Cruzamento de EMA com o preço pode indicar **entrada ou saída**.
- **Bollinger Bands**: faixa de volatilidade.
  - Quando o preço toca a banda inferior → **potencial compra**.
  - Quando toca a banda superior → **potencial venda**.
    """)

    st.plotly_chart(plot_rsi(df), use_container_width=True)
    st.markdown("""
### 💹 RSI (Índice de Força Relativa)  
Mede a velocidade das variações de preço:
- **Referência**:
  - RSI < 30 → **Sobrevendido** → possível oportunidade de **compra**.
  - RSI > 70 → **Sobrecomprado** → possível sinal de **venda**.
- Cruzamentos nesses níveis sugerem reversões de tendência.
    """)

    st.plotly_chart(plot_stochrsi(df), use_container_width=True)
    st.markdown("""
### 📊 Stochastic RSI  
Indica áreas extremas com maior sensibilidade que o RSI:
- **Referência**:
  - K e D < 0.2 → **zona de sobrevenda** → possível **compra**.
  - K e D > 0.8 → **zona de sobrecompra** → possível **venda**.
- Cruzamentos entre K e D também sinalizam reversões.
    """)

    st.plotly_chart(plot_kdj(df), use_container_width=True)
    st.markdown("""
### 🔀 Indicador KDJ  
Variação do estocástico com linha **J**, que amplifica movimentos:
- **Referência**:
  - J < 20 → **compra**.
  - J > 80 → **venda**.
- Cruzamentos entre K, D e J ajudam a antecipar movimentos.
    """)

    st.plotly_chart(plot_macd(df), use_container_width=True)
    st.markdown("""
### 📉 MACD (Moving Average Convergence Divergence)  
Mede divergência entre duas EMAs:
- **MACD vs Signal**:
  - MACD cruza **acima** da Signal → **compra**.
  - MACD cruza **abaixo** da Signal → **venda**.
- O histograma mostra a força do momento (quanto maior, mais forte o movimento).
    """)

    st.plotly_chart(plot_adx(df), use_container_width=True)
    st.markdown("""
### ⚡ ADX (Average Directional Index)  
Mede a **força** da tendência, não a direção:
- ADX > 25 → tendência forte (pode ser de alta ou baixa).
- ADX < 20 → mercado sem direção clara (**lateral**).
Use em conjunto com outros indicadores para entender o **contexto da tendência**.
    """)

    st.subheader("📊 Histórico de Sinais")
    hist = pd.DataFrame(st.session_state.historico)
    st.dataframe(hist.sort_values("timestamp", ascending=False).style.format({
        "RSI": "{:.2f}", "StochRSI_K": "{:.2f}", "KDJ_J": "{:.2f}"
    }), use_container_width=True)

    st.caption(f"⏱ Atualização automática: {refresh_select}.")


if __name__ == "__main__":
    main()