import streamlit as st
import pandas as pd
import yfinance as yf
from streamlit_autorefresh import st_autorefresh
import plotly.graph_objs as go

# --- Funções para indicadores técnicos ---

def calcular_ema(df, periodo=14):
    return df['Close'].ewm(span=periodo, adjust=False).mean()

def calcular_rsi(df, periodo=14):
    delta = df['Close'].diff()
    ganho = delta.where(delta > 0, 0)
    perda = -delta.where(delta < 0, 0)
    media_ganho = ganho.rolling(window=periodo).mean()
    media_perda = perda.rolling(window=periodo).mean()
    rs = media_ganho / media_perda
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calcular_macd(df, fast=12, slow=26, signal=9):
    ema_fast = df['Close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['Close'].ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    hist = macd - signal_line
    return macd, signal_line, hist

# --- Função para baixar dados históricos da criptomoeda
def baixar_dados(ticker, periodo="1d", intervalo="1m"):
    df = yf.download(ticker, period=periodo, interval=intervalo)
    df.reset_index(inplace=True)
    return df

# --- Gráfico de velas com Plotly
def grafico_velas(df):
    fig = go.Figure(data=[go.Candlestick(
        x=df['Datetime'],
        open=df['Open'],
        high=df['High'],
        low=df['Low'],
        close=df['Close'],
        increasing_line_color='green',
        decreasing_line_color='red',
        name='Preço'
    )])
    fig.update_layout(
        title='Gráfico de Velas',
        xaxis_title='Data',
        yaxis_title='Preço',
        xaxis_rangeslider_visible=False,
        template='plotly_dark',
        height=500
    )
    return fig

# --- Gráfico RSI
def grafico_rsi(df, rsi):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['Datetime'], y=rsi,
        mode='lines',
        line=dict(color='purple', width=2),
        name='RSI'
    ))
    fig.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="Sobrecomprado (70)")
    fig.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="Sobrevendido (30)")
    fig.update_layout(
        title='RSI (Índice de Força Relativa)',
        xaxis_title='Data',
        yaxis_title='RSI',
        yaxis=dict(range=[0, 100]),
        template='plotly_dark',
        height=300
    )
    return fig

# --- Gráfico MACD
def grafico_macd(df, macd, signal, hist):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['Datetime'], y=macd,
        mode='lines',
        line=dict(color='blue', width=2),
        name='MACD'
    ))
    fig.add_trace(go.Scatter(
        x=df['Datetime'], y=signal,
        mode='lines',
        line=dict(color='orange', width=2),
        name='Linha de Sinal'
    ))
    fig.add_trace(go.Bar(
        x=df['Datetime'], y=hist,
        name='Histograma',
        marker_color=['green' if val >= 0 else 'red' for val in hist]
    ))
    fig.update_layout(
        title='MACD',
        xaxis_title='Data',
        yaxis_title='Valor',
        template='plotly_dark',
        height=300
    )
    return fig

# --- Gráfico EMA e preço
def grafico_ema(df, ema):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['Datetime'], y=df['Close'],
        mode='lines',
        name='Preço Fechamento',
        line=dict(color='lightblue', width=2)
    ))
    fig.add_trace(go.Scatter(
        x=df['Datetime'], y=ema,
        mode='lines',
        name='EMA 14',
        line=dict(color='yellow', width=2, dash='dash')
    ))
    fig.update_layout(
        title='Preço Fechamento e EMA 14',
        xaxis_title='Data',
        yaxis_title='Preço',
        template='plotly_dark',
        height=300
    )
    return fig

# --- Streamlit App ---

st.set_page_config(page_title="Análise Cripto com Indicadores", layout="wide")
st.title("Análise de Criptomoedas com Indicadores Técnicos e Atualização Automática")

# Atualiza a cada 60 segundos
st_autorefresh(interval=60 * 1000, key="auto_refresh")

ticker = st.text_input("Digite o ticker da criptomoeda (ex: BTC-USD):", value="BTC-USD")

if ticker:
    try:
        with st.spinner("Baixando dados..."):
            df = baixar_dados(ticker, periodo="1d", intervalo="1m")

        if df.empty:
            st.error("Nenhum dado encontrado para esse ticker.")
        else:
            df.rename(columns={'Datetime': 'Datetime'}, inplace=True)

            # Calcula indicadores
            ema14 = calcular_ema(df, periodo=14)
            rsi14 = calcular_rsi(df, periodo=14)
            macd_line, signal_line, macd_hist = calcular_macd(df)

            # Mostra dados e gráficos
            st.subheader(f"Últimas 10 linhas dos dados de {ticker}")
            st.dataframe(df.tail(10))

            st.plotly_chart(grafico_velas(df), use_container_width=True)
            st.plotly_chart(grafico_ema(df, ema14), use_container_width=True)
            st.plotly_chart(grafico_rsi(df, rsi14), use_container_width=True)
            st.plotly_chart(grafico_macd(df, macd_line, signal_line, macd_hist), use_container_width=True)

    except Exception as e:
        st.error(f"Erro ao baixar ou processar dados: {e}")