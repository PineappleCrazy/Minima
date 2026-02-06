from core.data import load_airport_data, AIRCRAFT_MAP
from core.minima import calculate_minima
import re

def recommend_approach(airport, runway, aircraft):
    airport = airport.lower()
    runway = runway.upper()
    aircraft = aircraft.upper()

    data = load_airport_data(airport)
    if not data:
        return {"error": "Unknown airport"}

    if aircraft not in AIRCRAFT_MAP:
        return {"error": "Unknown aircraft"}

    category = AIRCRAFT_MAP[aircraft]

    ils_gls = []
    others = []

    # --- Collect approaches ---
    for key in data.keys():
        if category not in data[key]:
            continue

        # ILS / GLS
        if key.startswith(("il", "gl")) and key.endswith(runway):
            prefix = key[:-len(runway)]
            ils_gls.append(prefix)

        # Everything else
        elif key.endswith(runway):
            prefix = key[:-len(runway)]
            others.append(prefix)

    # --- Helper to test approaches ---
    def is_above_minima(prefix):
        result = calculate_minima(
            airport=airport,
            runway=runway,
            aircraft=aircraft,
            approach=prefix
        )
        return result.get("status") == "ABOVE MINIMA", result.get("required", 0)

    # ============================================================
    # 1️⃣ ILS / GLS logic (CAT I → CAT III)
    # ============================================================
    if ils_gls:
        # Sort CAT I → CAT III
        def cat_rank(p):
            if p.startswith("il"): return int(p[2])
            if p.startswith("gl"): return int(p[3])
            return 9

        ils_gls.sort(key=cat_rank)

        for prefix in ils_gls:
            ok, _ = is_above_minima(prefix)
            if ok:
                return {"recommended": prefix}

    # ============================================================
    # 2️⃣ No ILS/GLS → lowest RVR requirement wins
    # ============================================================
    candidates = []

    for prefix in others:
        ok, required = is_above_minima(prefix)
        if ok and required > 0:
            candidates.append((required, prefix))

    if candidates:
        # Lowest required visibility first
        candidates.sort(key=lambda x: x[0])
        return {"recommended": candidates[0][1]}

    return {"error": "No suitable approach above minima"}
