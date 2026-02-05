import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
AIRCRAFT_FILE = os.path.join(BASE_DIR, "aircraft.json")


def load_airport_data(airport: str):
    """
    Load airport minima JSON from /data/<icao>.json
    """
    path = os.path.join(DATA_DIR, f"{airport.lower()}.json")

    if not os.path.exists(path):
        return None

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# Load aircraft categories once at startup
if os.path.exists(AIRCRAFT_FILE):
    with open(AIRCRAFT_FILE, "r", encoding="utf-8") as f:
        AIRCRAFT_MAP = {
            k.upper(): v.lower()
            for k, v in json.load(f).items()
        }
else:
    AIRCRAFT_MAP = {}
