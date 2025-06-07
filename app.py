import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import time

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

# ----------- FUNÇÃO DE ANÁLISE -------------

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

# ----------- MAIN DO APP -------------

def main():
    st.title("🚀 Alerta Cripto Completo - 24h Online")

    # Lista de criptomoedas (você pode adicionar outras)
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

    if st.button("▶️ Iniciar análise automática (fica rodando 24h)"):
        st.write(f"Iniciando análises automáticas para {symbol_nome} a cada {intervalo_analise} minutos...")

        while True:
            df = analisar(symbol, period, interval)

            ultimo_rsi = df['RSI_14'].iloc[-1]
            ultimo_stoch_k = df['StochRSI_K'].iloc[-1]
            ultimo_j = df['J'].iloc[-1]

            # Mostrar gráficos no Streamlit
            st.line_chart(df[['Close', 'EMA_14']])
            st.line_chart(df[['RSI_14']])
            st.line_chart(df[['StochRSI_K', 'StochRSI_D']])
            st.line_chart(df[['K', 'D', 'J']])

            # Definir sinal
            if ultimo_rsi < 30 and ultimo_stoch_k < 0.2 and ultimo_j < 20:
                sinal_atual = "compra"
            elif ultimo_rsi > 70 and ultimo_stoch_k > 0.8 and ultimo_j > 80:
                sinal_atual = "venda"
            else:
                sinal_atual = "neutro"

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

            st.write(f"Próxima análise em {intervalo_analise} minutos...")
            time.sleep(intervalo_analise * 60)

if __name__ == "__main__":
    main()
