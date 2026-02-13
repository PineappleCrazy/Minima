from flask import Flask, render_template, request, jsonify, url_for
from core.minima import calculate_minima
from core.data import load_airport_data, AIRCRAFT_MAP
from core.metar import get_metar, get_visibility
from core.recommend import recommend_approach
import re
import os
import json  # Added import

app = Flask(__name__)

# Valid instrument approach prefixes
APPROACH_PREFIX_PATTERN = r"^(il[123]|gl[123]|vor|ndb|loc|rnp|par)"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/airports")
def airports():
    data_dir = os.path.join(app.root_path, "data")
    if not os.path.exists(data_dir):
        return jsonify([])
    
    airport_list = []
    
    # Iterate over files to find names
    for f in os.listdir(data_dir):
        if f.endswith(".json"):
            code = f[:-5].upper()
            name = ""
            try:
                # Try to read the "name" field from the JSON
                with open(os.path.join(data_dir, f), 'r') as file:
                    content = json.load(file)
                    # Assumes the JSON might have a "name" key at the root
                    name = content.get("name", "") 
            except Exception:
                pass
            
            airport_list.append({"code": code, "name": name})

    # Sort by ICAO code
    return jsonify(sorted(airport_list, key=lambda x: x["code"]))

@app.route("/aircraft")
def aircraft():
    return jsonify(sorted(AIRCRAFT_MAP.keys()))

@app.route("/runways")
def runways():
    airport = request.args.get("airport", "").lower()
    data = load_airport_data(airport)
    if not data:
        return jsonify([])

    runways = set()

    for key in data.keys():
        m = re.search(r"(\d{2}[LRC]?)(?:-[a-z0-9]+)?$", key)
        if m:
            runways.add(m.group(1))

    return jsonify(sorted(runways))


@app.route("/approaches")
def approaches():
    airport = request.args.get("airport", "").lower()
    runway = request.args.get("runway", "").upper()
    aircraft = request.args.get("aircraft", "").upper()

    data = load_airport_data(airport)
    if not data or not runway:
        return jsonify([])

    # Weather (used only for recommendation)
    metar = get_metar(airport.upper())
    visibility = get_visibility(metar, runway)
    vis_val = int(visibility) if visibility.isdigit() else None

    # Aircraft category (OPTIONAL)
    cat_type = AIRCRAFT_MAP.get(aircraft)

    approaches = []

    for key, minima in data.items():

        # ---------- RNP ----------
        rnp_match = re.match(rf"^rnp{runway}(?:-(.+))?$", key)
        if rnp_match:
            suffix = rnp_match.group(1) or "approach"
            approaches.append({
                "type": "RNP",
                "label": f"RNP {suffix.upper()}",
                "value": f"rnp-{suffix.lower()}",
                "required": minima.get(cat_type) if cat_type else None
            })
            continue

        # ---------- ILS / GLS / others ----------
        m = re.match(r"^([a-z]{2,4}[123]?)(\d{2}[LRC]?)$", key)
        if not m or m.group(2) != runway:
            continue

        prefix = m.group(1)

        if prefix.startswith("il"):
            label = f"ILS CAT {prefix[2]}"
            typ = "ILS"
        elif prefix.startswith("gl"):
            label = f"GLS CAT {prefix[-1]}"
            typ = "GLS"
        else:
            label = prefix.upper()
            typ = label

        approaches.append({
            "type": typ,
            "label": label,
            "value": prefix,
            "required": minima.get(cat_type) if cat_type else None
        })

    if not approaches:
        return jsonify([])

    # ------------------------------------------------
    # 2️⃣ RECOMMENDATION (ONLY IF AIRCRAFT SELECTED)
    # ------------------------------------------------
    recommended_value = None

    if cat_type and vis_val is not None:
        # Prefer ILS / GLS CAT I → CAT III
        ils_gls = [
            a for a in approaches
            if a["type"] in ("ILS", "GLS")
            and isinstance(a["required"], int)
            and a["required"] > 0
        ]

        def cat_rank(a):
            return int(a["label"][-1])

        ils_gls.sort(key=cat_rank)

        for a in ils_gls:
            if vis_val >= a["required"]:
                recommended_value = a["value"]
                break

        # Otherwise lowest RVR wins
        if not recommended_value:
            candidates = [
                a for a in approaches
                if isinstance(a["required"], int)
                and a["required"] > 0
                and vis_val >= a["required"]
            ]
            if candidates:
                candidates.sort(key=lambda a: a["required"])
                recommended_value = candidates[0]["value"]

    # ------------------------------------------------
    # 3️⃣ FINAL PAYLOAD (NO AUTO-SELECT)
    # ------------------------------------------------
    for a in approaches:
        a["recommended"] = (a["value"] == recommended_value)
        a.pop("required", None)

    return jsonify(approaches)



@app.route("/recommend", methods=["POST"])
def recommend():
    data = request.json
    return jsonify(
        recommend_approach(
            data["airport"],
            data["runway"],
            data["aircraft"]
        )
    )

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

