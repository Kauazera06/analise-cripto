import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
from streamlit_autorefresh import st_autorefresh
import yfinance as yf

st.set_page_config(layout="wide")
st.title("Analisador de Criptomoedas com Alertas e Indicadores Técnicos")

# ----------- FUNÇÕES DE INDICADORES -------------

def EMA(df, period=14):
    return df['Close'].ewm(span=period, adjust=False).mean()

def RSI(df, period=14):
    delta = df['Close'].diff()
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
    low_min = df['Low'].rolling(window=period).min()
    high_max = df['High'].rolling(window=period).max()
    rsv = (df['Close'] - low_min) / (high_max - low_min) * 100
    K = rsv.ewm(com=k_period-1, adjust=False).mean()
    D = K.ewm(com=d_period-1, adjust=False).mean()
    J = 3 * K - 2 * D
    return K, D, J

# ----------- FUNÇÃO PARA ENVIAR ALERTA NO TELEGRAM -------------

def enviar_alerta_telegram(mensagem):
    token = "7507470816:AAFpu1RRtGQYJfv1cuGjRsW4H87ryM1XsRY"  # seu token
    chat_id = "1705586919"  # seu chat_id para teste
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    params = {"chat_id": chat_id, "text": mensagem}
    try:
        requests.get(url, params=params)
    except Exception as e:
        st.error(f"Erro ao enviar mensagem Telegram: {e}")

# ----------- FUNÇÃO PARA OBTER DADOS E CALCULAR INDICADORES -------------

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

    return df

# ----------- FUNÇÕES DE PLOTAGEM -------------

def plot_candlestick(df):
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["Open"],
        high=df["High"],
        low=df["Low"],
        close=df["Close"],
        name="Candlestick",
        increasing_line_color='green', decreasing_line_color='red'
    ))
    fig.add_trace(go.Scatter(x=df.index, y=df["EMA_14"], mode="lines", name="EMA 14", line=dict(color="blue")))
    fig.update_layout(title="Preço + EMA 14", xaxis_title="Data", yaxis_title="Preço (USD)", height=600)
    return fig

def plot_rsi(df):
    fig_rsi = go.Figure()
    fig_rsi.add_trace(go.Scatter(x=df.index, y=df["RSI_14"], mode="lines", name="RSI", line=dict(color="green")))
    fig_rsi.update_layout(title="RSI (14 períodos)", yaxis=dict(range=[0, 100]), height=300)
    return fig_rsi

def plot_stochrsi(df):
    fig_stoch = go.Figure()
    fig_stoch.add_trace(go.Scatter(x=df.index, y=df["StochRSI_K"], mode="lines", name="StochRSI K", line=dict(color="teal")))
    fig_stoch.add_trace(go.Scatter(x=df.index, y=df["StochRSI_D"], mode="lines", name="StochRSI D", line=dict(color="orange")))
    fig_stoch.update_layout(title="Stochastic RSI", yaxis=dict(range=[0, 1]), height=300)
    return fig_stoch

def plot_kdj(df):
    fig_kdj = go.Figure()
    fig_kdj.add_trace(go.Scatter(x=df.index, y=df["K"], mode="lines", name="K", line=dict(color="blue")))
    fig_kdj.add_trace(go.Scatter(x=df.index, y=df["D"], mode="lines", name="D", line=dict(color="red")))
    fig_kdj.add_trace(go.Scatter(x=df.index, y=df["J"], mode="lines", name="J", line=dict(color="purple")))
    fig_kdj.update_layout(title="KDJ", height=300)
    return fig_kdj

# ----------- MAIN DO APP -------------

def main():
    # Opções de intervalo para atualização automática
    interval_options = {
        "10 segundos": 10 * 1000,
        "20 segundos": 20 * 1000,
        "30 segundos": 30 * 1000,
        "1 minuto": 60 * 1000,
        "3 minutos": 3 * 60 * 1000,
        "5 minutos": 5 * 60 * 1000
    }

    opcoes_cripto = {
        "Bitcoin": "BTC-USD",
        "Ethereum": "ETH-USD",
        "Binance Coin": "BNB-USD",
        "Cardano": "ADA-USD",
        "Solana": "SOL-USD",
        "Ripple": "XRP-USD",
        "Polkadot": "DOT-USD",
        "Litecoin": "LTC-USD",
        "Syrup": "SYRUP-USD",
        "Dogecoin": "DOGE-USD",
        "Pepe": "PEPE-USD"
    }

    col1, col2, col3 = st.columns(3)
    with col1:
        symbol_nome = st.selectbox("Escolha a criptomoeda:", list(opcoes_cripto.keys()))
    with col2:
        period = st.selectbox("Período para baixar dados:", ["1mo", "3mo", "6mo", "1y"], index=0)
    with col3:
        interval = st.selectbox("Intervalo dos candles:", ["15m", "30m", "1h", "1d"], index=0)

    intervalo_selecao = st.selectbox("Intervalo entre análises automáticas", list(interval_options.keys()), index=3)
    intervalo_ms = interval_options[intervalo_selecao]

    # Atualização automática a cada intervalo escolhido
    count = st_autorefresh(interval=intervalo_ms, limit=None, key="auto_refresh")

    # Inicializa sessão para guardar histórico e último sinal
    if "historico" not in st.session_state:
        st.session_state["historico"] = []

    if "ultimo_sinal" not in st.session_state:
        st.session_state.ultimo_sinal = "neutro"

    # Obter dados e indicadores
    df = obter_dados(opcoes_cripto[symbol_nome], period, interval)

    if df.empty:
        st.warning("Nenhum dado disponível. Verifique o símbolo ou tente novamente mais tarde.")
        st.stop()

    # Pegar valores últimos para análise de sinais
    ultimo_rsi = df['RSI_14'].iloc[-1]
    ultimo_stoch_k = df['StochRSI_K'].iloc[-1]
    ultimo_j = df['J'].iloc[-1]

    # Definir sinal
    if ultimo_rsi < 30 and ultimo_stoch_k < 0.2 and ultimo_j < 20:
        sinal_atual = "compra"
    elif ultimo_rsi > 70 and ultimo_stoch_k > 0.8 and ultimo_j > 80:
        sinal_atual = "venda"
    else:
        sinal_atual = "neutro"

    # Enviar alerta se mudou o sinal
    if sinal_atual != st.session_state.ultimo_sinal:
        if sinal_atual == "compra":
            mensagem = f"🚀 Sinal de COMPRA detectado para {symbol_nome} (RSI {ultimo_rsi:.2f}, StochRSI K {ultimo_stoch_k:.2f}, KDJ J {ultimo_j:.2f})"
            enviar_alerta_telegram(mensagem)
            st.success(mensagem)
        elif sinal_atual == "venda":
            mensagem = f"⚠️ Sinal de VENDA detectado para {symbol_nome} (RSI {ultimo_rsi:.2f}, StochRSI K {ultimo_stoch_k:.2f}, KDJ J {ultimo_j:.2f})"
            enviar_alerta_telegram(mensagem)
            st.warning(mensagem)
        else:
            st.info("Nenhum sinal forte detectado no momento.")
        st.session_state.ultimo_sinal = sinal_atual
    else:
        st.info(f"Sinal atual continua: {sinal_atual}. Sem novo alerta.")

    # Guardar no histórico (para exibir tabela)
    st.session_state.historico.append({
        "timestamp": pd.Timestamp.now(),
        "sinal": sinal_atual,
        "RSI": round(ultimo_rsi, 2),
        "StochRSI_K": round(ultimo_stoch_k, 2),
        "KDJ_J": round(ultimo_j, 2)
    })

    # Mostrar gráficos lado a lado com descrições
    col_graf1, col_graf2 = st.columns(2)
    with col_graf1:
        st.plotly_chart(plot_candlestick(df), use_container_width=True)
        st.markdown("""
        **Gráfico Candlestick + EMA 14**  
        Mostra o preço de abertura, fechamento, máxima e mínima, além da média móvel exponencial (EMA) de 14 períodos para identificar tendências.
        """)
        st.plotly_chart(plot_rsi(df), use_container_width=True)
        st.markdown("""
        **RSI (Índice de Força Relativa)**  
        Indica condições de sobrecompra (>70) ou sobrevenda (<30) do ativo, ajudando a identificar possíveis reversões.
        """)

    with col_graf2:
        st.plotly_chart(plot_stochrsi(df), use_container_width=True)
        st.markdown("""
        **Stochastic RSI**  
        Mostra a velocidade e a mudança do RSI, indicando possíveis pontos de entrada e saída rápidos com base em sobrecompra/sobrevenda.
        """)
        st.plotly_chart(plot_kdj(df), use_container_width=True)
        st.markdown("""
        **KDJ**  
        Indicador baseado em stochastic, útil para detectar tendências, divergências e pontos de reversão.
        """)

    # Exibir histórico de sinais
    st.subheader("Histórico de sinais")
    df_historico = pd.DataFrame(st.session_state.historico)
    df_historico = df_historico.sort_values(by="timestamp", ascending=False)
    st.dataframe(df_historico)

if __name__ == "__main__":
    main()
