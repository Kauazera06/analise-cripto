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
    return df

# ----------- GRÁFICOS -------------

def plot_candlestick(df, nome):
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"],
        increasing_line_color='green', decreasing_line_color='red'
    ))
    fig.add_trace(go.Scatter(x=df.index, y=df["EMA_14"], mode="lines", name="EMA 14", line=dict(color="blue")))
    fig.update_layout(title=f"{nome} - Preço + EMA 14", xaxis_title="Data", yaxis_title="Preço (USD)", height=600)
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

# ----------- APP PRINCIPAL -------------

def main():

    # Opções de intervalo para atualização automática (em milissegundos)
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

    # Selectbox para escolher intervalo de atualização automática
    intervalo_selecao = st.selectbox("Intervalo entre análises automáticas", list(interval_options.keys()), index=3)
    intervalo_ms = interval_options[intervalo_selecao]

    # Aplica o auto refresh
    st_autorefresh(interval=intervalo_ms, limit=None, key="auto_refresh")

    symbol = cripto_opcoes[nome_moeda]

    if "historico" not in st.session_state:
        st.session_state["historico"] = []
    if "ultimo_sinal" not in st.session_state:
        st.session_state.ultimo_sinal = "neutro"

    df = obter_dados(symbol, period, interval)
    if df.empty:
        st.warning("Nenhum dado disponível.")
        st.stop()

    rsi = df['RSI_14'].iloc[-1]
    stoch_k = df['StochRSI_K'].iloc[-1]
    j = df['J'].iloc[-1]

    if rsi < 30 and stoch_k < 0.2 and j < 20:
        sinal = "compra"
    elif rsi > 70 and stoch_k > 0.8 and j > 80:
        sinal = "venda"
    else:
        sinal = "neutro"

    if sinal != st.session_state.ultimo_sinal:
        if sinal == "compra":
            msg = f"🚀 COMPRA para {nome_moeda} (RSI {rsi:.2f}, StochRSI K {stoch_k:.2f}, KDJ J {j:.2f})"
            enviar_alerta_telegram(msg)
            st.success(msg)
        elif sinal == "venda":
            msg = f"⚠️ VENDA para {nome_moeda} (RSI {rsi:.2f}, StochRSI K {stoch_k:.2f}, KDJ J {j:.2f})"
            enviar_alerta_telegram(msg)
            st.warning(msg)
        st.session_state.ultimo_sinal = sinal
    else:
        st.info(f"Sinal atual: {sinal}. Sem nova mudança.")

    # Adiciona ao histórico com nome da moeda
    st.session_state.historico.append({
        "timestamp": pd.Timestamp.now(),
        "moeda": nome_moeda,
        "sinal": sinal,
        "RSI": round(rsi, 2),
        "StochRSI_K": round(stoch_k, 2),
        "KDJ_J": round(j, 2)
    })

    # Gráficos com descrições
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.plotly_chart(plot_candlestick(df, nome_moeda), use_container_width=True)
        st.markdown("""
        **Gráfico de Candlestick + EMA 14**  
        Mostra o preço da criptomoeda com velas japonesas, que representam abertura, fechamento, máxima e mínima em cada período.  
        A linha EMA 14 (Média Móvel Exponencial) ajuda a identificar tendências:  
        - Se o preço estiver acima da EMA, tendência de alta.  
        - Se estiver abaixo, tendência de baixa.  
        Observe cruzamentos para sinais de compra ou venda.
        """)

        st.plotly_chart(plot_rsi(df, nome_moeda), use_container_width=True)
        st.markdown("""
        **RSI (Índice de Força Relativa)**  
        Indica se a moeda está sobrecomprada (>70) ou sobrevendida (<30).  
        Valores extremos podem indicar possível reversão.
        """)

    with col_g2:
        st.plotly_chart(plot_stochrsi(df, nome_moeda), use_container_width=True)
        st.markdown("""
        **Stochastic RSI**  
        Mede o quão próximo o RSI está das suas extremidades (0 a 1).  
        - Valores abaixo de 0.2 indicam sobrevenda.  
        - Valores acima de 0.8 indicam sobrecompra.
        """)

        st.plotly_chart(plot_kdj(df, nome_moeda), use_container_width=True)
        st.markdown("""
        **Indicador KDJ**  
        Combina o estocástico com médias móveis exponenciais para mostrar o momento e possíveis pontos de reversão.  
        - Cruzamentos das linhas K e D indicam sinais de compra/venda.  
        - Linha J acentua esses sinais.
        """)

    # Exibe histórico dos sinais
    if st.checkbox("Mostrar histórico de sinais"):
        df_hist = pd.DataFrame(st.session_state.historico)
        st.dataframe(df_hist.sort_values(by="timestamp", ascending=False))

if __name__ == "__main__":
    main()
