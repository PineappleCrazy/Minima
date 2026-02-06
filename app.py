from flask import Flask, render_template, request, jsonify, url_for
from core.minima import calculate_minima
from core.data import load_airport_data, AIRCRAFT_MAP
from core.metar import get_metar, get_visibility
from core.recommend import recommend_approach
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

    # --- Weather ---
    metar = get_metar(airport.upper())
    visibility = get_visibility(metar, runway)
    vis_val = int(visibility) if visibility.isdigit() else 9999

    # --- Aircraft category ---
    cat_type = AIRCRAFT_MAP.get(aircraft)
    if not cat_type:
        return jsonify([])

    approaches = []

    for key, minima in data.items():
        if cat_type not in minima:
            continue

        required = minima.get(cat_type, 0)
        if not isinstance(required, int) or required <= 0:
            continue

        # =======================
        # RNP (with suffix)
        # =======================
        rnp_match = re.match(rf"^rnp{runway}(?:-(.+))?$", key)
        if rnp_match:
            suffix = rnp_match.group(1) or "approach"
            approaches.append({
                "type": "RNP",
                "label": f"RNP {suffix.upper()}",
                "value": f"rnp-{suffix.lower()}",
                "required": required
            })
            continue

        # =======================
        # ILS / GLS / others
        # =======================
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
            "required": required
        })

    recommended = None

    ils_gls = [a for a in approaches if a["type"] in ("ILS", "GLS")]

    def cat_rank(a):
        return int(a["label"][-1])

    ils_gls.sort(key=cat_rank)

    for a in ils_gls:
        if vis_val >= a["required"]:
            recommended = a["value"]
            break

    if not recommended:
        candidates = [a for a in approaches if vis_val >= a["required"]]
        if candidates:
            candidates.sort(key=lambda a: a["required"])
            recommended = candidates[0]["value"]

    for a in approaches:
        a["recommended"] = (a["value"] == recommended)
        del a["required"]

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









