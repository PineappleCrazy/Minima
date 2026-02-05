from flask import Flask, render_template, request, jsonify
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

@app.route("/runways")
def runways():
    airport = request.args.get("airport", "").lower()
    data = load_airport_data(airport)
    if not data: return jsonify([])

    runways = set()
    # Regex ensures we extract runway digits from valid prefixes only
    pattern = re.compile(APPROACH_PREFIX_PATTERN + r"(\d{2}[LRC]?)")

    for key in data.keys():
        match = pattern.match(key)
        if match:
            runways.add(match.group(2))

    return jsonify(sorted(runways))

@app.route("/approaches")
def approaches():
    airport = request.args.get("airport", "").lower()
    runway = request.args.get("runway", "").upper()
    data = load_airport_data(airport)
    
    if not data or not runway: return jsonify([])

    approaches = []
    for key in data.keys():
        # Handle RNP (complex keys with suffixes like -lpv)
        if key.startswith("rnp"):
            rnp_match = re.match(r"^rnp(\d{2}[LRC]?)(?:-(.*))?$", key)
            if rnp_match and rnp_match.group(1) == runway:
                suffix = rnp_match.group(2) or "Approach"
                approaches.append({
                    "type": "RNP",
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

            approaches.append({
                "type": label.split()[0],
                "label": label,
                "value": prefix
            })

    unique = {a["value"]: a for a in approaches}
    return jsonify(list(unique.values()))

if __name__ == "__main__":
    app.run(debug=True)