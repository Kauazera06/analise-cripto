import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score
import joblib

# Carregar o dataset
df = pd.read_csv("dataset_cripto.csv")

# Separar X e y
X = df.drop(columns=["Sinal", "moeda", "timestamp"])

y = df["Sinal"]

# Separar treino e teste
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, stratify=y, random_state=42
)

# Treinar modelo com balanceamento de classes
modelo = RandomForestClassifier(n_estimators=100, random_state=42, class_weight="balanced")
modelo.fit(X_train, y_train)

# Avaliação
y_pred = modelo.predict(X_test)

print("🎯 Acurácia:", accuracy_score(y_test, y_pred))
print("\n📊 Relatório de Classificação:\n", classification_report(y_test, y_pred))

# Salvar modelo
joblib.dump(modelo, "modelo_trade_ia.pkl")
print("✅ Modelo salvo como 'modelo_trade_ia.pkl'")
