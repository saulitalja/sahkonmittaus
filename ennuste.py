import os
import pandas as pd
import requests
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

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
# 4) Päivitetään päivittäiset hinnat ja kulutus
# =================================================
price_df["Date"] = price_df["date"].dt.date
df["Date"] = df["Timestamp"].dt.date

daily_price = price_df.groupby("Date")["Price_EUR_per_kWh"].mean().reset_index()
daily_consumption = df.groupby("Date")["Energy_kWh"].sum().reset_index()

merged = pd.merge(daily_price, daily_consumption, on="Date", how="inner")

# =================================================
# 5) Lisää sähkönsiirto ja verot
# =================================================
SIIRTO_KWH = 0.05       # €/kWh
SAHKO_VERO = 0.028      # €/kWh (sähkövero + huoltovarmuus)
ALV = 0.255             # 25.5 %

# Todellinen hinta sisältäen siirron ja verot
merged["TotalPrice_EUR_per_kWh"] = (
    merged["Price_EUR_per_kWh"] + SIIRTO_KWH + SAHKO_VERO
) * (1 + ALV)

# Päivittäinen kokonaiskustannus
merged["Cost_EUR"] = merged["Energy_kWh"] * merged["TotalPrice_EUR_per_kWh"]

# =================================================
# 6) Piirrä kaksiakselinen graafi
# =================================================
fig, ax1 = plt.subplots(figsize=(12,6))

# Vasemman puolen akseli: spot-hinta
ax1.set_xlabel("Päivä")
ax1.set_ylabel("Spot-hinta €/kWh", color="blue")
ax1.plot(merged["Date"], merged["Price_EUR_per_kWh"], color="blue", marker='o', label="Spot-hinta €/kWh")
ax1.tick_params(axis='y', labelcolor="blue")

# Oikean puolen akseli: kulutus ja kustannus
ax2 = ax1.twinx()
ax2.set_ylabel("Kulutus kWh / kustannus €", color="green")
ax2.plot(merged["Date"], merged["Energy_kWh"], color="green", marker='x', label="Kulutus kWh")
ax2.plot(merged["Date"], merged["Cost_EUR"], color="red", marker='s', label="Kustannus € (sis. siirto + verot)")
ax2.tick_params(axis='y', labelcolor="green")

# Yhteinen legend
lines_1, labels_1 = ax1.get_legend_handles_labels()
lines_2, labels_2 = ax2.get_legend_handles_labels()
ax2.legend(lines_1 + lines_2, labels_1 + labels_2, loc="upper left")

plt.title("Sähkön spot-hinta, kulutus ja todellinen kustannus (sis. siirto ja verot)")
plt.grid(True)
plt.tight_layout()
plt.show()
