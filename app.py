import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import time
import plotly.graph_objs as go

# --- Funções de indicadores (mantive igual) ---
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

# --- Gráficos ---
def plot_candlestick(df):
    fig = go.Figure(data=[go.Candlestick(
        x=df.index,
        open=df['Open'],
        high=df['High'],
        low=df['Low'],
        close=df['Close'],
        name="Candlestick"
    ),
    go.Scatter(x=df.index, y=df['EMA_14'], mode='lines', name='EMA 14', line=dict(color='blue'))])
    fig.update_layout(title="Candlestick + EMA 14", height=350, margin=dict(l=10,r=10,t=40,b=10))
    return fig

def plot_rsi(df):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI_14'], mode='lines', name='RSI 14', line=dict(color='orange')))
    fig.add_hline(y=70, line_dash="dash", line_color="red")
    fig.add_hline(y=30, line_dash="dash", line_color="green")
    fig.update_layout(title="RSI 14", height=300, margin=dict(l=10,r=10,t=40,b=10), yaxis=dict(range=[0,100]))
    return fig

def plot_stochrsi(df):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df['StochRSI_K'], mode='lines', name='StochRSI K', line=dict(color='purple')))
    fig.add_trace(go.Scatter(x=df.index, y=df['StochRSI_D'], mode='lines', name='StochRSI D', line=dict(color='pink')))
    fig.add_hline(y=0.8, line_dash="dash", line_color="red")
    fig.add_hline(y=0.2, line_dash="dash", line_color="green")
    fig.update_layout(title="Stochastic RSI", height=300, margin=dict(l=10,r=10,t=40,b=10), yaxis=dict(range=[0,1]))
    return fig

def plot_kdj(df):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df['K'], mode='lines', name='K', line=dict(color='blue')))
    fig.add_trace(go.Scatter(x=df.index, y=df['D'], mode='lines', name='D', line=dict(color='orange')))
    fig.add_trace(go.Scatter(x=df.index, y=df['J'], mode='lines', name='J', line=dict(color='green')))
    fig.add_hline(y=80, line_dash="dash", line_color="red")
    fig.add_hline(y=20, line_dash="dash", line_color="green")
    fig.update_layout(title="KDJ", height=300, margin=dict(l=10,r=10,t=40,b=10), yaxis=dict(range=[0,100]))
    return fig

# --- Enviar alerta Telegram ---
def enviar_alerta_telegram(mensagem):
    token = "7507470816:AAFpu1RRtGQYJfv1cuGjRsW4H87ryM1XsRY"  # seu token
    chat_id = "1705586919"  # seu chat_id
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    params = {"chat_id": chat_id, "text": mensagem}
    try:
        requests.get(url, params=params)
    except Exception as e:
        st.error(f"Erro ao enviar mensagem Telegram: {e}")

# --- Função análise ---
def analisar(symbol, period, interval):
    df = yf.download(symbol, period=period, interval=interval)
    df.dropna(inplace=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df['EMA_14'] = EMA(df)
    df['RSI_14'] = RSI(df)
    df['StochRSI_K'], df['StochRSI_D'] = StochRSI(df)
    df['K'], df['D'], df['J'] = KDJ(df)
    return df

# --- Main ---
def main():
    st.title("🚀 Alerta Cripto Completo - Atualização Automática")

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

    symbol_nome = st.selectbox("Escolha a criptomoeda:", list(opcoes_cripto.keys()))
    symbol = opcoes_cripto[symbol_nome]

    period = st.selectbox("Período para baixar dados:", ["1mo", "3mo", "6mo", "1y"])
    interval = st.selectbox("Intervalo dos candles:", ["15m", "30m", "1h", "1d"])
    intervalo_analise = st.number_input("Intervalo entre análises automáticas (minutos)", min_value=1, max_value=60, value=5)

    if 'ultimo_sinal' not in st.session_state:
        st.session_state.ultimo_sinal = "neutro"
    if 'historico' not in st.session_state:
        st.session_state.historico = []

    # Reservas de espaço para atualizar gráficos e histórico
    placeholder_graficos = st.empty()
    placeholder_historico = st.empty()
    placeholder_status = st.empty()

    while True:
        df = analisar(symbol, period, interval)

        ultimo_rsi = df['RSI_14'].iloc[-1]
        ultimo_stoch_k = df['StochRSI_K'].iloc[-1]
        ultimo_j = df['J'].iloc[-1]

        # Atualizar gráficos na mesma área
        with placeholder_graficos.container():
            col1, col2 = st.columns(2)
            with col1:
                st.plotly_chart(plot_candlestick(df), use_container_width=True)
                st.markdown("""
                **Candlestick + EMA 14:**  
                Candlesticks mostram a movimentação diária do preço (abertura, fechamento, máximo e mínimo).  
                A EMA 14 ajuda a suavizar o preço e indicar tendências.
                """)
                st.plotly_chart(plot_rsi(df), use_container_width=True)
                st.markdown("""
                **RSI:**  
                Mede velocidade e mudança dos movimentos de preço.  
                Valores abaixo de 30 indicam sobrevenda (compra), acima de 70 sobrecompra (venda).
                """)

            with col2:
                st.plotly_chart(plot_stochrsi(df), use_container_width=True)
                st.markdown("""
                **StochRSI:**  
                Indicador que ajuda a identificar sobrecompra e sobrevenda mais rápido,  
                linhas K e D indicam potenciais pontos de entrada e saída.
                """)
                st.plotly_chart(plot_kdj(df), use_container_width=True)
                st.markdown("""
                **KDJ:**  
                Usado para identificar reversões com as linhas K, D e J mostrando momentum e força da tendência.
                """)

        # Definir sinal
        if ultimo_rsi < 30 and ultimo_stoch_k < 0.2 and ultimo_j < 20:
            sinal_atual = "compra"
        elif ultimo_rsi > 70 and ultimo_stoch_k > 0.8 and ultimo_j > 80:
            sinal_atual = "venda"
        else:
            sinal_atual = "neutro"

        # Atualizar histórico com nome da moeda, sem duplicar
        st.session_state.historico.append({
            "timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
            "moeda": symbol_nome,
            "sinal": sinal_atual,
            "RSI": round(ultimo_rsi, 2),
            "StochRSI_K": round(ultimo_stoch_k, 2),
            "KDJ_J": round(ultimo_j, 2)
        })

        # Exibir histórico atualizado no placeholder
        with placeholder_historico.container():
            st.subheader("Histórico dos últimos sinais")
            df_historico = pd.DataFrame(st.session_state.historico)
            st.dataframe(df_historico.sort_values(by="timestamp", ascending=False).reset_index(drop=True))

        # Mensagens de alerta e status atual
        with placeholder_status.container():
            if sinal_atual != st.session_state.ultimo_sinal:
                if sinal_atual == "compra":
                    mensagem = f"🚀 Sinal de COMPRA para {symbol_nome} (RSI {ultimo_rsi:.2f}, StochRSI K {ultimo_stoch_k:.2f}, KDJ J {ultimo_j:.2f})"
                    enviar_alerta_telegram(mensagem)
                    st.success(mensagem)
                elif sinal_atual == "venda":
                    mensagem = f"⚠️ Sinal de VENDA para {symbol_nome} (RSI {ultimo_rsi:.2f}, StochRSI K {ultimo_stoch_k:.2f}, KDJ J {ultimo_j:.2f})"
                    enviar_alerta_telegram(mensagem)
                    st.warning(mensagem)
                else:
                    st.info("Nenhum sinal forte detectado.")
                st.session_state.ultimo_sinal = sinal_atual
            else:
                st.info(f"Sinal atual continua: {sinal_atual}. Sem novo alerta.")

            st.write(f"Próxima análise em {intervalo_analise} minutos...")

        time.sleep(intervalo_analise * 60)

if __name__ == "__main__":
    main()
