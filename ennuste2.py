import os
import pandas as pd
import requests
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# Ennustemalli
from prophet import Prophet

# =================================================
# 1) Polut
# =================================================
home_dir = os.path.expanduser("~")
csv_file = os.path.join(home_dir, "battery_energy_summary.csv")

# =================================================
# 2) Lue kulutusdata CSV:stä
# =================================================
df = pd.read_csv(csv_file)
df["Timestamp"] = pd.to_datetime(df["Timestamp"])
df["Energy_kWh"] = df["TotalEnergy_kWh"].astype(float)

# =================================================
# 3) Hae Nord Pool spot-hintadataa sahkotin.fi API:sta
# =================================================
start_date = (df["Timestamp"].min() - timedelta(days=1)).strftime("%Y-%m-%dT00:00:00.000Z")
end_date   = (df["Timestamp"].max() + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00.000Z")

url = f"https://sahkotin.fi/prices?quarter&fix&vat&start={start_date}&end={end_date}"
resp = requests.get(url)
resp.raise_for_status()
data = resp.json().get("prices", [])

price_df = pd.DataFrame(data)
price_df["date"] = pd.to_datetime(price_df["date"])
price_df.rename(columns={"value":"Price_snt_per_kWh"}, inplace=True)
price_df["Price_EUR_per_kWh"] = price_df["Price_snt_per_kWh"] / 100  # sentit → eurot

# =================================================
# 4) Päivittäiset hinnat
# =================================================
price_df["Date"] = price_df["date"].dt.date
daily_price = price_df.groupby("Date")["Price_EUR_per_kWh"].mean().reset_index()

# =================================================
# 5) Ennuste Prophetillä
# =================================================
prophet_df = daily_price.rename(columns={"Date":"ds", "Price_EUR_per_kWh":"y"})
model = Prophet(daily_seasonality=True)
model.fit(prophet_df)

future = model.make_future_dataframe(periods=30)  # 30 päivää eteenpäin
forecast = model.predict(future)

# =================================================
# 6) Laske ennusteen kustannus mukaan siirto, vero ja ALV
# =================================================
SIIRTO_KWH = 0.05
SAHKO_VERO = 0.028
ALV = 0.255

forecast["TotalPrice_EUR_per_kWh"] = (forecast["yhat"] + SIIRTO_KWH + SAHKO_VERO) * (1 + ALV)

# =================================================
# 7) Graafi
# =================================================
plt.figure(figsize=(12,6))
plt.plot(forecast["ds"], forecast["yhat"], color="blue", label="Spot-hinta historiallinen & ennuste €/kWh")
plt.plot(forecast["ds"], forecast["TotalPrice_EUR_per_kWh"], color="red", label="Todellinen hinta €/kWh (sis. siirto + verot)")
plt.axvline(daily_price["Date"].max(), color="gray", linestyle="--", label="Nykyhetki")
plt.xlabel("Päivä")
plt.ylabel("Hinta €/kWh")
plt.title("Spot-hinta ja arvioitu todellinen hinta seuraavalle kuukaudelle")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()
