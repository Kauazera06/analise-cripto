import pandas as pd
import numpy as np
import requests

def get_binance_data(symbol="BTCUSDT", interval="5m", limit=1000):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Erro ao buscar dados para {symbol}: {response.status_code}")
        return pd.DataFrame()
    data = response.json()
    if not data or len(data) == 0:
        print(f"Sem dados para {symbol}")
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

def RSI(df, period=14):
    delta = df["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
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

def gerar_dataset_moedas(lista_moedas, limit=500):
    dfs = []
    for moeda in lista_moedas:
        print(f"Gerando dados para {moeda}...")
        df = get_binance_data(moeda, limit=limit)
        print(f"{moeda} - Dados crus: {df.shape}")
        if df.empty:
            print(f"Dados vazios para {moeda}, pulando...")
            continue

        df["RSI"] = RSI(df)
        macd_line, signal_line, hist = MACD(df)
        df["MACD"] = macd_line
        df["Signal_MACD"] = signal_line
        df["Hist_MACD"] = hist
        df["StochRSI"] = StochRSI(df)
        df["ADX"] = ADX(df)
        df["Close"] = df["Close"].astype(float)

        df.dropna(inplace=True)
        print(f"{moeda} - Dados após dropna: {df.shape}")

        if df.empty:
            print(f"Sem dados suficientes após limpeza para {moeda}, pulando...")
            continue

        # Critérios mais flexíveis para gerar sinais
        conditions = [
            (df["RSI"] < 40) & (df["StochRSI"] < 0.4) & (df["MACD"] > df["Signal_MACD"]) & (df["ADX"] > 15),
            (df["RSI"] > 60) & (df["StochRSI"] > 0.6) & (df["MACD"] < df["Signal_MACD"]) & (df["ADX"] > 15)
        ]
        choices = [2, 0]  # 2 = Compra, 0 = Venda (ou vice-versa dependendo da sua definição)
        df["Sinal"] = np.select(conditions, choices, default=1)  # 1 = Neutro

        df["moeda"] = moeda

        dfs.append(df[["RSI", "MACD", "Signal_MACD", "Hist_MACD", "StochRSI", "ADX", "Sinal", "moeda"]])

    if dfs:
        dataset_final = pd.concat(dfs)
        dataset_final.to_csv("dataset_cripto.csv")
        print("Dataset salvo em 'dataset_cripto.csv'.")
    else:
        print("Nenhum dado válido para salvar.")


if __name__ == "__main__":
    moedas = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT"]
    gerar_dataset_moedas(moedas)
