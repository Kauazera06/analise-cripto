import pandas as pd

df = pd.read_csv("dataset_cripto.csv")

print("Contagem completa das classes Sinal:")
print(df["Sinal"].value_counts())

print("\nExemplos onde Sinal == 2:")
print(df[df["Sinal"] == 2])
