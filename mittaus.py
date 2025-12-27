import os
import re
import csv
import subprocess
from datetime import datetime

# =================================================
# 1. Polut (kotihakemisto automaattisesti)
# =================================================
home_dir = os.path.expanduser("~")
html_file = os.path.join(home_dir, "battery_report.html")
csv_file = os.path.join(home_dir, "battery_energy_summary.csv")

# =================================================
# 2. Luo battery report
# =================================================
subprocess.run(
    f'powercfg /batteryreport /output "{html_file}"',
    shell=True,
    check=True
)

# =================================================
# 3. Lue HTML BINÄÄRINÄ ja dekoodaa turvallisesti
# =================================================
with open(html_file, "rb") as f:
    raw = f.read()

try:
    content = raw.decode("utf-16")
except UnicodeDecodeError:
    content = raw.decode("utf-8", errors="ignore")

# =================================================
# 4. Normalisoi sisältö
# =================================================
content = content.replace("\xa0", " ")  # non-breaking space

# =================================================
# 5. Parsitaan ENERGY DRAINED (mWh)
#    Kattaa muodot:
#    10 381'00 mWh
#    -84'00 mWh
# =================================================
total_energy_mwh = 0

pattern = re.compile(r"(-?\d[\d\s']*)\s*mWh")

for match in pattern.findall(content):
    cleaned = match.replace(" ", "").replace("'", "")
    try:
        value = int(cleaned)
        if value > 0:
            total_energy_mwh += value
    except ValueError:
        continue

# =================================================
# 6. Muunnokset
# =================================================
total_energy_wh = total_energy_mwh / 1000
total_energy_kwh = total_energy_mwh / 1_000_000

# =================================================
# 7. Tulostus
# =================================================
print("Battery energy consumption summary")
print("----------------------------------")
print(f"Kokonaienergia: {total_energy_mwh} mWh")
print(f"Kokonaienergia: {total_energy_wh:.2f} Wh")
print(f"Kokonaienergia: {total_energy_kwh:.4f} kWh")

# =================================================
# 8. CSV tallennus
# =================================================
file_exists = os.path.exists(csv_file)

with open(csv_file, "a", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)

    if not file_exists:
        writer.writerow([
            "Timestamp",
            "TotalEnergy_mWh",
            "TotalEnergy_Wh",
            "TotalEnergy_kWh"
        ])

    writer.writerow([
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        total_energy_mwh,
        f"{total_energy_wh:.2f}",
        f"{total_energy_kwh:.4f}"
    ])

print(f"\nCSV tallennettu: {csv_file}")
