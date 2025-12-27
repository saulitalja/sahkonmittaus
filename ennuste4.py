import os
import requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import timedelta
import csv
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense

# =================================================
# 1) Lataa CSV-historia
# =================================================
home_dir = os.path.expanduser("~")
csv_file = os.path.join(home_dir, "battery_energy_summary.csv")
df = pd.read_csv(csv_file)

df["Timestamp"] = pd.to_datetime(df["Timestamp"])
df["Energy_kWh"] = pd.to_numeric(df["TotalEnergy_kWh"], errors='coerce')
df = df.dropna(subset=["Energy_kWh"])

if len(df) == 0:
    raise ValueError("CSV ei sisällä yhtään kelvollista datapistettä.")

daily_data = df.groupby(pd.Grouper(key="Timestamp", freq="D"))["Energy_kWh"].mean().reset_index()
daily_data.rename(columns={"Energy_kWh":"SpotPrice"}, inplace=True)

# =================================================
# 2) Hae Nord Pool spot-hintadataa sahkotin.fi API:sta
# =================================================
start_date = (df["Timestamp"].min() - timedelta(days=1)).strftime("%Y-%m-%dT00:00:00.000Z")
end_date   = (df["Timestamp"].max() + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00.000Z")

try:
    url = f"https://sahkotin.fi/prices?quarter&fix&vat&start={start_date}&end={end_date}"
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json().get("prices", [])

    price_df = pd.DataFrame(data)
    price_df["date"] = pd.to_datetime(price_df["date"])
    price_df.rename(columns={"value":"Price_snt_per_kWh"}, inplace=True)
    price_df["Price_EUR_per_kWh"] = price_df["Price_snt_per_kWh"] / 100  # sentit → eurot

    # Keskiarvota tuntihinnat päivätasolle
    daily_api = price_df.groupby(price_df["date"].dt.floor("D"))["Price_EUR_per_kWh"].mean().reset_index()
    daily_api.rename(columns={"date":"Timestamp","Price_EUR_per_kWh":"SpotPrice"}, inplace=True)

    # Yhdistä CSV-historia ja API-data
    combined_data = pd.concat([daily_data, daily_api])
    combined_data = combined_data.groupby("Timestamp").mean().reset_index()
    combined_data.sort_values("Timestamp", inplace=True)

    daily_data = combined_data
    print("Spot-hinta haettu onnistuneesti API:sta.")

except Exception as e:
    print(f"Nykyhinnan haku epäonnistui: {e}")
    print("Käytetään pelkkää CSV-historiaa LSTM:ään.")

# =================================================
# 3) Parametrit ja skaalaus
# =================================================
sequence_length = 30
future_days = 30

scaler = MinMaxScaler(feature_range=(0, 1))
scaled_data = scaler.fit_transform(daily_data["SpotPrice"].values.reshape(-1,1))

# =================================================
# 4) LSTM-ennuste
# =================================================
if len(scaled_data) > sequence_length:
    X, y = [], []
    for i in range(sequence_length, len(scaled_data)):
        X.append(scaled_data[i-sequence_length:i, 0])
        y.append(scaled_data[i, 0])

    X = np.array(X)
    y = np.array(y)
    X = np.reshape(X, (X.shape[0], X.shape[1], 1))

    model = Sequential()
    model.add(LSTM(50, return_sequences=True, input_shape=(X.shape[1],1)))
    model.add(LSTM(50))
    model.add(Dense(1))
    model.compile(optimizer="adam", loss="mean_squared_error")
    model.fit(X, y, epochs=50, batch_size=16, verbose=0)

    pred_inputs = scaled_data[-sequence_length:].reshape(1, sequence_length, 1)
    predictions = []
    for _ in range(future_days):
        pred = model.predict(pred_inputs, verbose=0)[0][0]
        predictions.append(pred)
        pred_inputs = np.append(pred_inputs[:,1:,:], [[[pred]]], axis=1)

    predicted_values = scaler.inverse_transform(np.array(predictions).reshape(-1,1)).flatten()
else:
    last_value = daily_data["SpotPrice"].iloc[-1]
    predicted_values = [last_value] * future_days

# =================================================
# 5) Laske todellinen hinta (siirto + verot)
# =================================================
SIIRTO_KWH = 0.05
SAHKO_VERO = 0.028
ALV = 0.255

total_price = (np.array(predicted_values) + SIIRTO_KWH + SAHKO_VERO) * (1+ALV)

last_date = daily_data["Timestamp"].max()
future_dates = [last_date + timedelta(days=i+1) for i in range(future_days)]

# =================================================
# 6) Piirrä graafi
# =================================================
plt.figure(figsize=(12,6))
plt.plot(daily_data["Timestamp"], daily_data["SpotPrice"], label="Historiallinen spot-hinta €/kWh", color="blue", marker="o")
plt.plot(future_dates, predicted_values, label="AI-ennuste spot-hinta €/kWh", color="cyan", marker="x")
plt.plot(future_dates, total_price, label="AI-ennuste todellinen hinta €/kWh", color="red", marker="s")
plt.axvline(last_date, color="gray", linestyle="--", label="Nykyhetki")
plt.xlabel("Päivä")
plt.ylabel("Hinta €/kWh")
plt.title("Spot-hinta ja ennuste seuraavalle kuukaudelle")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()

# =================================================
# 7) Kirjoita CSV
# =================================================
output_csv = os.path.join(home_dir, "forecast_output.csv")
with open(output_csv, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["Date","Predicted_kWh","TotalPrice_EUR_per_kWh"])
    for d, val, price in zip(future_dates, predicted_values, total_price):
        writer.writerow([d,val,price])

print(f"Ennuste CSV: {output_csv}")
