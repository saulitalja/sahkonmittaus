import os
import re
import csv
from datetime import datetime
import subprocess

# =================================================
# Luo uusi battery_report.html komennolla powercfg
# =================================================
home_dir = os.path.expanduser("~")
html_file = os.path.join(home_dir, "battery_report.html")

# Suoritetaan powercfg-komento
subprocess.run([
    "powercfg",
    "/batteryreport",
    "/output",
    html_file
], check=True)

# =================================================
# CSV tiedosto kotihakemistoon
# =================================================
csv_file = os.path.join(home_dir, "battery_energy_summary.csv")

# Luo CSV tiedosto, jos ei ole olemassa, ja lisää otsikkorivi
if not os.path.exists(csv_file):
    with open(csv_file, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Timestamp", "TotalEnergy_mWh", "TotalEnergy_Wh", "TotalEnergy_kWh"])

# =================================================
# Lue HTML ja laske energiankulutus
# =================================================
total_energy_mwh = 0

with open(html_file, "r", encoding="utf-8") as f:
    content = f.read()

# Etsi kaikki mWh-arvot tekstistä
matches = re.findall(r"([-\d\s']+) mWh", content)

for value_str in matches:
    # Poista välilyönnit ja heittomerkit
    value_str = value_str.replace(" ", "").replace("'", "")
    try:
        value = int(value_str)
        total_energy_mwh += value
    except ValueError:
        continue

# Muunna Wh ja kWh
total_energy_wh = total_energy_mwh / 1000
total_energy_kwh = total_energy_mwh / 1_000_000

# Tulosta
print(f"Kokonaienergia: {total_energy_mwh} mWh")
print(f"Kokonaienergia: {total_energy_wh:.2f} Wh")
print(f"Kokonaienergia: {total_energy_kwh:.4f} kWh")

# Kirjoita CSV:ään
with open(csv_file, mode="a", newline="") as f:
    writer = csv.writer(f)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    writer.writerow([timestamp, total_energy_mwh, f"{total_energy_wh:.2f}", f"{total_energy_kwh:.4f}"])
