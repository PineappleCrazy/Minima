from flask import Flask, render_template, request, jsonify, url_for
from core.minima import calculate_minima
from core.data import load_airport_data, AIRCRAFT_MAP
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
    airport = request.args.get("airport", "").upper()
    runway = request.args.get("runway", "").upper()
    data = load_airport_data(airport)
    
    if not data or not runway: return jsonify([])

    approaches = []
    for key in data.keys():
        # Handle RNP (complex keys with suffixes like -lpv)
        if key.startswith("rnp"):
            rnp_match = re.match(r"^rnp(\d{2}[LRC]?)(?:-(.*))?$", key)
            if rnp_match and rnp_match.group(1) == runway:
                suffix = rnp_match.group(2) or "approach"
                approaches.append({
                    "label": f"RNP {suffix.upper()}",
                    "value": f"rnp-{suffix.lower()}"
                })
            continue

        # Handle standard prefixes (ILS, GLS, VOR, NDB, LOC)
        match = re.match(r"^([a-z]{2,3}[123]?|gls)(\d{2}[LRC]?)$", key)
        if match and match.group(2) == runway:
            prefix = match.group(1)
            if prefix.startswith("il"):
                label = f"ILS CAT {prefix[2]}"
            elif prefix.startswith("gl") and len(prefix) == 3:
                label = f"GLS CAT {prefix[2]}"
            else:
                label = prefix.upper()
            
            approaches.append({"label": label, "value": prefix})

    return jsonify(approaches)

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
