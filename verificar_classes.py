import pandas as pd

# Carregar o dataset que você gerou
df = pd.read_csv("dataset_cripto.csv")

# Mostrar a contagem de cada classe na coluna 'Sinal'
print("Contagem por classe na coluna 'Sinal':")
print(df["Sinal"].value_counts())
