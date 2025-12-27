import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import timedelta
import csv
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense

# =================================================
# 1) Polut ja data
# =================================================
home_dir = os.path.expanduser("~")
csv_file = os.path.join(home_dir, "battery_energy_summary.csv")

df = pd.read_csv(csv_file)
df["Timestamp"] = pd.to_datetime(df["Timestamp"])
df["Energy_kWh"] = pd.to_numeric(df["TotalEnergy_kWh"], errors='coerce')
df = df.dropna(subset=["Energy_kWh"])

if len(df) == 0:
    raise ValueError("CSV ei sisällä yhtään kelvollista datapistettä.")

# Päivitä data päivätasolle säilyttäen datetime64 tyypin
daily_data = df.groupby(pd.Grouper(key="Timestamp", freq="D"))["Energy_kWh"].mean().reset_index()
daily_data.rename(columns={"Energy_kWh":"SpotPrice"}, inplace=True)

# =================================================
# 2) Parametrit ja skaalain
# =================================================
sequence_length = 30
future_days = 30
scaler = MinMaxScaler(feature_range=(0, 1))
scaled_data = scaler.fit_transform(daily_data["SpotPrice"].values.reshape(-1,1))

# =================================================
# 3) Ennustustapa automaattisesti
# =================================================
if len(scaled_data) > sequence_length:
    print("Käytetään LSTM:ää ennustukseen.")

    # Muodosta X ja y
    X, y = [], []
    for i in range(sequence_length, len(scaled_data)):
        X.append(scaled_data[i-sequence_length:i, 0])
        y.append(scaled_data[i, 0])
    X = np.array(X)
    y = np.array(y)
    X = np.reshape(X, (X.shape[0], X.shape[1], 1))

    # =================================================
    # LSTM-malli
    # =================================================
    model = Sequential()
    model.add(LSTM(50, return_sequences=True, input_shape=(X.shape[1],1)))
    model.add(LSTM(50))
    model.add(Dense(1))
    model.compile(optimizer='adam', loss='mean_squared_error')
    model.fit(X, y, epochs=50, batch_size=16, verbose=0)

    # =================================================
    # Ennusta seuraavat 30 päivää
    # =================================================
    pred_inputs = scaled_data[-sequence_length:].reshape(1, sequence_length, 1)
    predictions = []
    for _ in range(future_days):
        pred = model.predict(pred_inputs, verbose=0)[0][0]
        predictions.append(pred)
        pred_inputs = np.append(pred_inputs[:,1:,:], [[[pred]]], axis=1)

    predicted_values = scaler.inverse_transform(np.array(predictions).reshape(-1,1)).flatten()

else:
    print("Liian vähän dataa LSTM:lle. Käytetään staattista ennustetta.")
    last_value = daily_data["SpotPrice"].iloc[-1]
    predicted_values = [last_value] * future_days

# =================================================
# 4) Laske todellinen hinta (sis. siirto ja verot)
# =================================================
SIIRTO_KWH = 0.05
SAHKO_VERO = 0.028
ALV = 0.255
total_price = (np.array(predicted_values) + SIIRTO_KWH + SAHKO_VERO) * (1 + ALV)

# Päivämäärät ennusteelle
last_date = daily_data["Timestamp"].max()
future_dates = [last_date + timedelta(days=i+1) for i in range(future_days)]

# =================================================
# 5) Piirrä graafi
# =================================================
plt.figure(figsize=(12,6))
plt.plot(daily_data["Timestamp"], daily_data["SpotPrice"], label="Historiallinen spot-hinta €/kWh", color="blue", marker='o')
plt.plot(future_dates, predicted_values, label="AI-ennuste spot-hinta €/kWh", color="cyan", marker='x')
plt.plot(future_dates, total_price, label="AI-ennuste todellinen hinta €/kWh (sis. siirto + verot)", color="red", marker='s')
plt.axvline(last_date, color="gray", linestyle="--", label="Nykyhetki")
plt.xlabel("Päivä")
plt.ylabel("Hinta €/kWh")
plt.title("Spot-hinta ja ennuste seuraavalle kuukaudelle")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()

# =================================================
# 6) Kirjoita CSV
# =================================================
output_csv = os.path.join(home_dir, "forecast_output.csv")
with open(output_csv, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(["Date", "Predicted_kWh", "TotalPrice_EUR_per_kWh"])
    for d, val, price in zip(future_dates, predicted_values, total_price):
        writer.writerow([d, val, price])

print(f"Ennuste CSV: {output_csv}")
