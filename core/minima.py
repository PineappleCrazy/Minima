from core.metar import get_metar, get_visibility
from core.data import load_airport_data, AIRCRAFT_MAP
from core.wind import parse_wind_data, calculate_wind_components, get_runway_heading

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
    
    # Check if METAR is unavailable
    if metar is None:
        return {
            "airport": airport.upper(),
            "runway": runway,
            "required": required,
            "visibility": "N/A",
            "status": "METAR UNAVAILABLE",
            "metar": "No METAR data available for this aerodrome",
            "wind": None
        }
    
    visibility = get_visibility(metar, runway)

    # Calculate wind components
    wind_data = None
    wind_dir, wind_spd, wind_gust = parse_wind_data(metar)
    runway_hdg = get_runway_heading(runway)
    
    if wind_dir is not None and wind_spd is not None and runway_hdg is not None:
        hw, xw = calculate_wind_components(wind_spd, wind_dir, runway_hdg)
        
        wind_data = {
            "direction": wind_dir,
            "speed": wind_spd,
            "gust": wind_gust,
            "headwind": round(hw, 1),
            "crosswind": round(xw, 1),
            "variable": False
        }
    elif wind_spd is not None:  # Variable wind (VRB)
        wind_data = {
            "direction": "VRB",
            "speed": wind_spd,
            "gust": wind_gust,
            "headwind": None,
            "crosswind": None,
            "variable": True
        }

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
        "metar": metar,
        "wind": wind_data
    }
