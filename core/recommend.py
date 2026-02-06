from core.data import load_airport_data, AIRCRAFT_MAP
from core.minima import calculate_minima

CAT_ORDER = ["1", "2", "3"]

def recommend_approach(airport, runway, aircraft):
    airport = airport.lower()
    runway = runway.upper()
    aircraft = aircraft.upper()

    data = load_airport_data(airport)
    if not data:
        return {"error": "Unknown airport"}

    if aircraft not in AIRCRAFT_MAP:
        return {"error": "Unknown aircraft"}

    # --- Collect ILS / GLS approaches ---
    ils_gls = []

    for key in data.keys():
        if key.startswith(("il", "gl")) and key.endswith(runway):
            # il1, il2, il3 → CAT 1/2/3
            cat = key[2] if key.startswith("il") else key[3]
            ils_gls.append((key[:-len(runway)], cat))

    # Sort CAT I → CAT III
    ils_gls.sort(key=lambda x: CAT_ORDER.index(x[1]))

    # --- Try ILS / GLS first ---
    for prefix, cat in ils_gls:
        result = calculate_minima(
            airport=airport,
            runway=runway,
            aircraft=aircraft,
            approach=prefix
        )

        if result.get("status") == "ABOVE MINIMA":
            return {"recommended": prefix}

    # --- Fallback: try anything else ---
    for key in data.keys():
        if key.endswith(runway):
            prefix = key.replace(runway, "")
            result = calculate_minima(
                airport=airport,
                runway=runway,
                aircraft=aircraft,
                approach=prefix
            )
            if result.get("status") == "ABOVE MINIMA":
                return {"recommended": prefix}

    return {"error": "No suitable approach above minima"}
