import requests
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.animation import FuncAnimation
from datetime import datetime
from zoneinfo import ZoneInfo
import csv
import os

# Parametrit
MARGINAALI = 0.01
SÄHKÖVERO = 0.026
HUOLTO = 0.002
ALV = 0.255
TASATTU_15MIN = (20+5) / 2880  # kiinteät siirron ja kulutuksen peruskuukausimaksut €/kWh 
SIIRTO_KWH = 0.05  # €/kWh, sähkön siirtomaksu
UPDATE_INTERVAL_MS = 15 * 60 * 1000  # 15 min
CSV_FILE = "porssisahko_lasku.csv"
FIXED_CONSUMPTION_KWH = float(input("Anna kWh kulutus:"))

# Luo CSV otsikoineen, jos ei ole
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            "Timestamp", "SpotPrice", "Marginaali", "Sähkönsiirto_kWh", "Sähkövero",
            "Huoltovarmuus", "TasattuKuukausimaksu", "Loppuhinta",
            "Kulutus_kWh", "Hinta_kWh"
        ])
        

# Data-listat graafia varten
timestamps = []
spot_prices = []
final_prices = []
cost_kwh = []

def get_current_spot_price():
    url = "https://api.spot-hinta.fi/JustNow"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        spot_price = float(data.get("PriceNoTax", 0))
        dt_utc = datetime.fromisoformat(data.get("DateTime"))
        dt_local = dt_utc.astimezone(ZoneInfo("Europe/Helsinki"))
        return dt_local, spot_price
    except requests.RequestException as e:
        print(f"Virhe haettaessa hintaa: {e}")
        return None, None

def calculate_final_price(spot):
    subtotal = (
        spot
        + MARGINAALI
        + SIIRTO_KWH      # 👈 siirron energiamaksu
        + SÄHKÖVERO
        + HUOLTO
        + TASATTU_15MIN   # perusmaksut 5 + 20 €
    )
    return subtotal * (1 + ALV)


# Luo kuvaaja
fig, ax = plt.subplots()
line_spot, = ax.plot([], [], label="Spot-hinta €/kWh", color="blue")
line_final, = ax.plot([], [], label="Loppuhinta €/kWh", color="green")
line_kwh, = ax.plot([], [], label="kulutuksen mukainen hinta €", color="red")
ax.set_xlabel("Aika (Suomi)")
ax.set_ylabel("Hinta")
ax.set_title("Spot-hinta, loppuhinta ja kulutuksen hinta 15 min välein")
ax.legend()
ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
plt.xticks(rotation=45)
plt.tight_layout()

def update(frame):
    dt, spot = get_current_spot_price()
    if dt and spot is not None:
        final = calculate_final_price(spot)
        cost = final * FIXED_CONSUMPTION_KWH

        # Päivitä data listalle
        timestamps.append(dt)
        spot_prices.append(spot)
        final_prices.append(final)
        cost_kwh.append(cost)

        # Päivitä kuvaaja
        line_spot.set_data(timestamps, spot_prices)
        line_final.set_data(timestamps, final_prices)
        line_kwh.set_data(timestamps, cost_kwh)
        ax.relim()
        ax.autoscale_view()
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())

        # Tulosta konsoliin
        print(f"{dt} | Spot: {spot:.5f} | Loppuhinta: {final:.5f} | syötetyn kulutuksen hinta: {cost:.2f} €")

        # Kirjoita CSV:ään
        with open(CSV_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                dt, spot, MARGINAALI, SIIRTO_KWH, SÄHKÖVERO, HUOLTO,
                TASATTU_15MIN, final, FIXED_CONSUMPTION_KWH, cost
            ])
    else:
        print("Tietoja ei saatu haettua.")

# Käynnistä animaatio
ani = FuncAnimation(fig, update, interval=UPDATE_INTERVAL_MS)
plt.show()
