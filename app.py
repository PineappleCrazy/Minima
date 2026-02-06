from flask import Flask, render_template, request, jsonify
from core.minima import calculate_minima
from core.data import load_airport_data, AIRCRAFT_MAP
from core.metar import get_metar, get_visibility
import re
import os

app = Flask(__name__)

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
    pattern = re.compile(APPROACH_PREFIX_PATTERN + r"(\d{2}[LRC]?)")

    for key in data.keys():
        match = pattern.match(key)
        if match:
            runways.add(match.group(2))

    return jsonify(sorted(runways))

def _get_approaches_list(airport, runway):
    data = load_airport_data(airport)
    if not data or not runway: return [], {}

    approaches = []
    
    for key in data.keys():
        if key.startswith("rnp"):
            rnp_match = re.match(r"^rnp(\d{2}[LRC]?)(?:-(.*))?$", key)
            if rnp_match and rnp_match.group(1) == runway:
                suffix = rnp_match.group(2) or "Approach"
                approaches.append({
                    "type": "RNP",
                    "label": f"RNP {suffix.upper()}",
                    "value": f"rnp-{suffix.lower()}",
                    "raw_key": key,
                    "cat_level": 0 
                })
            continue

        match = re.match(r"^([a-z]{2,3}[123]?|gls)(\d{2}[LRC]?)$", key)
        if match and match.group(2) == runway:
            prefix = match.group(1)
            
            cat_level = 0
            if prefix.startswith("il"):
                label = f"ILS CAT {prefix[2]}"
                cat_level = int(prefix[2])
            elif prefix.startswith("gl") and len(prefix) == 3:
                label = f"GLS CAT {prefix[2]}"
                cat_level = int(prefix[2])
            else:
                label = prefix.upper()

            approaches.append({
                "type": label.split()[0],
                "label": label,
                "value": prefix,
                "raw_key": key,
                "cat_level": cat_level
            })
    
    return approaches, data

@app.route("/approaches")
def approaches():
    airport = request.args.get("airport", "").lower()
    runway = request.args.get("runway", "").upper()
    
    approaches_list, _ = _get_approaches_list(airport, runway)
    
    unique = {a["value"]: a for a in approaches_list}
    return jsonify(list(unique.values()))

@app.route("/recommend", methods=["POST"])
def recommend():
    req = request.json
    airport = req.get("airport", "").lower()
    runway = req.get("runway", "").upper()
    aircraft = req.get("aircraft", "").upper()

    if aircraft not in AIRCRAFT_MAP:
        return jsonify({"error": "Unknown aircraft"})

    category = AIRCRAFT_MAP[aircraft]
    
    approaches_list, full_data = _get_approaches_list(airport, runway)
    
    if not approaches_list:
        return jsonify({"error": "No approaches found"})

    metar = get_metar(airport.upper())
    vis_str = get_visibility(metar, runway)
    
    current_vis = int(vis_str) if str(vis_str).isdigit() else 0

    candidates = []
    for app in approaches_list:
        raw_key = app["raw_key"]
        
        if raw_key in full_data and category in full_data[raw_key]:
            val = full_data[raw_key][category]
            required = int(val) if str(val).isdigit() else 99999
            
            candidates.append({
                **app,
                "required": required,
                "is_flyable": current_vis >= required
            })

    if not candidates:
        return jsonify({"error": "No minima data for aircraft category"})

    flyable = [c for c in candidates if c["is_flyable"]]
    
    selected = None

    if not flyable:
        selected = min(candidates, key=lambda x: x["required"])
    else:
        precision = [c for c in flyable if c["type"] in ["ILS", "GLS"]]
        
        if precision:
            cat1 = next((c for c in precision if c["cat_level"] == 1), None)
            cat3 = next((c for c in precision if c["cat_level"] == 3), None)
            cat2 = next((c for c in precision if c["cat_level"] == 2), None)
            
            if cat1: selected = cat1
            elif cat3: selected = cat3
            elif cat2: selected = cat2
            else: selected = min(precision, key=lambda x: x["required"])
        else:
            selected = min(flyable, key=lambda x: x["required"])

    return jsonify({
        "recommended": selected["value"],
        "label": selected["label"],
        "reason": "Best available based on METAR" if flyable else "Lowest minima (Currently Below Minima)"
    })

if __name__ == "__main__":
    app.run(debug=True)
