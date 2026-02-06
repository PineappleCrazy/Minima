from flask import Flask, render_template, request, jsonify, url_for
from core.minima import calculate_minima
from core.data import load_airport_data, AIRCRAFT_MAP
from core.metar import get_metar, get_visibility
import re
import os

app = Flask(__name__)

# Valid instrument approach prefixes
APPROACH_PREFIX_PATTERN = r"^(il[123]|gl[s123]|vor|ndb|loc|rnp)"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/airports")
def airports():
    data_dir = os.path.join(app.root_path, "data")
    if not os.path.exists(data_dir):
        return jsonify([])
    airports = [f[:-5].upper() for f in os.listdir(data_dir) if f.endswith(".json")]
    return jsonify(sorted(airports))

@app.route("/aircraft")
def aircraft():
    return jsonify(sorted(AIRCRAFT_MAP.keys()))

@app.route("/runways")
def runways():
    airport = request.args.get("airport", "").upper()
    data = load_airport_data(airport)
    if not data: return jsonify([])
    
    # Extract unique runway numbers/letters from JSON keys (e.g., il327R -> 27R)
    runways = set()
    for key in data.keys():
        match = re.search(r"(\d{2}[LRC]?)$", key)
        if match:
            runways.add(match.group(1))
    return jsonify(sorted(list(runways)))

@app.route("/approaches")
def approaches():
    airport = request.args.get("airport", "").lower()
    runway = request.args.get("runway", "").upper()
    aircraft = request.args.get("aircraft", "").upper() # Added to check specific minima
    data = load_airport_data(airport)
    
    if not data or not runway: return jsonify([])

    # Fetch weather once to determine recommendation
    metar = get_metar(airport.upper())
    visibility = get_visibility(metar, runway)
    vis_val = int(visibility) if visibility.isdigit() else 9999
    
    cat_type = AIRCRAFT_MAP.get(aircraft, "c") # Default to Cat C if unknown
    
    found_approaches = []
    for key in data.keys():
        # Handle RNP
        if key.startswith("rnp"):
            rnp_match = re.match(r"^rnp(\d{2}[LRC]?)(?:-(.*))?$", key)
            if rnp_match and rnp_match.group(1) == runway:
                suffix = rnp_match.group(2) or "Approach"
                found_approaches.append({
                    "type": "RNP",
                    "label": f"RNP {suffix.upper()}",
                    "value": f"rnp-{suffix.lower()}",
                    "minima": int(data[key].get(cat_type, 0))
                })
            continue

        # Handle ILS/GLS/Other
        match = re.match(r"^([a-z]{2,3}[123]?|gls[123]?)(\d{2}[LRC]?)$", key)
        if match and match.group(2) == runway:
            prefix = match.group(1)
            label = prefix.upper()
            if prefix.startswith("il"): label = f"ILS CAT {prefix[2]}"
            elif prefix.startswith("gl") and len(prefix) == 4: label = f"GLS CAT {prefix[3]}"

            found_approaches.append({
                "type": label.split()[0],
                "label": label,
                "value": prefix,
                "minima": int(data[key].get(cat_type, 0))
            })

    # Sort: ILS 1 -> 2 -> 3, then GLS, then others
    def sort_key(item):
        v = item["value"]
        if v.startswith("il"): return (0, v)
        if v.startswith("gl"): return (1, v)
        return (2, v)
    
    sorted_list = sorted(found_approaches, key=sort_key)

    # RECOMMENDATION LOGIC:
    # Pick the LOWEST Category (least precise) that is still ABOVE minima.
    recommended_value = None
    
    # Check ILS/GLS specifically for CAT preference
    precision_apps = [a for a in sorted_list if a["type"] in ["ILS", "GLS"]]
    for app in precision_apps:
        # If visibility is better than required, this is our "easiest" valid approach
        if vis_val >= app["minima"] and app["minima"] > 0:
            recommended_value = app["value"]
            break 
    
    # If all are below minima or no precision found, default to the first in list
    if not recommended_value and sorted_list:
        recommended_value = sorted_list[0]["value"]

    # Final response with recommendation flag
    for a in sorted_list:
        a["recommended"] = (a["value"] == recommended_value)
        del a["minima"] # Clean up internal data

    return jsonify(sorted_list)

@app.route("/recommend", methods=["POST"])
def recommend():
    data = request.json
    airport = data.get("airport", "").upper()
    runway = data.get("runway", "").upper()
    aircraft = data.get("aircraft", "").upper()

    airport_data = load_airport_data(airport)
    category = AIRCRAFT_MAP.get(aircraft)

    if not airport_data or not category:
        return jsonify({"error": "Data not found"}), 404

    # Priority ranking (lower index = more preferred)
    priority = [
        "il3", "il2", "il1",  # ILS Categories
        "gl3", "gl2", "gl1", "gls", # GLS
        "rnp-lpv", "rnp-approach", # RNP
        "loc", "vor", "ndb" # Non-Precision
    ]

    best_value = None
    best_rank = len(priority)

    # 1. Gather all valid approach values for this runway
    # We re-use logic from /approaches to ensure values match the frontend <options>
    for key in airport_data.keys():
        if category not in airport_data[key]: continue

        current_value = None
        if key.startswith("rnp"):
            m = re.match(r"^rnp(\d{2}[LRC]?)(?:-(.*))?$", key)
            if m and m.group(1) == runway:
                suffix = m.group(2) or "approach"
                current_value = f"rnp-{suffix.lower()}"
        else:
            m = re.match(r"^([a-z]{2,3}[123]?|gls)(\d{2}[LRC]?)$", key)
            if m and m.group(2) == runway:
                current_value = m.group(1)

        # 2. Check priority
        if current_value in priority:
            rank = priority.index(current_value)
            if rank < best_rank:
                best_rank = rank
                best_value = current_value

    if best_value:
        return jsonify({"recommended": best_value})
    
    return jsonify({"error": "No suitable approach found"}), 404

@app.route("/minima", methods=["POST"])
def minima():
    data = request.json
    result = calculate_minima(
        airport=data["airport"],
        runway=data["runway"],
        aircraft=data["aircraft"],
        approach=data["approach"]
    )
    return jsonify(result)

if __name__ == "__main__":
    app.run(debug=True)


