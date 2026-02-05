from core.metar import get_metar, get_visibility
from core.data import load_airport_data, AIRCRAFT_MAP

def calculate_minima(airport, runway, aircraft, approach):
    airport = airport.lower()
    aircraft = aircraft.upper()

    data = load_airport_data(airport)
    if not data: return {"error": "Unknown airport"}
    if aircraft not in AIRCRAFT_MAP: return {"error": "Unknown aircraft"}

    category = AIRCRAFT_MAP[aircraft]

    # Reconstruct the JSON key based on selected approach and runway
    if approach.startswith("rnp-"):
        suffix = approach.split("-")[1]
        key = f"rnp{runway}" if suffix == "approach" else f"rnp{runway}-{suffix}"
    else:
        key = f"{approach}{runway}"

    if key not in data or category not in data[key]:
        return {"error": f"Minima not defined for {key} (Cat {category})"}

    # Handle 0m as UNAVAILABLE logic
    val = data[key][category]
    required = int(val) if str(val).isdigit() else 0

    metar = get_metar(airport.upper())
    visibility = get_visibility(metar, runway)

    if required == 0:
        status = "UNAVAILABLE"
    else:
        status = "ABOVE MINIMA"
        if str(visibility).isdigit() and int(visibility) < required:
            status = "BELOW MINIMA"

    return {
        "airport": airport.upper(),
        "runway": runway,
        "required": required,
        "visibility": visibility,
        "status": status,
        "metar": metar
    }