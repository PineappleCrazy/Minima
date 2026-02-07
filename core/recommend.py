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

        # RNP approaches (e.g. rnp27R or rnp27R-ar)
        rnp_match = re.match(rf"^rnp{runway}(?:-(.+))?$", key)
        if rnp_match:
            suffix = rnp_match.group(1) or "approach"
            prefix = f"rnp-{suffix.lower()}"
            others.append(prefix)
            continue

        # ILS / GLS
        if key.startswith(("il", "gl")) and key.endswith(runway):
            prefix = key[:-len(runway)]
            ils_gls.append(prefix)

        # Everything else
        elif key.endswith(runway):
            prefix = key[:-len(runway)]
            others.append(prefix)

    # Check if we have any approaches at all
    if not ils_gls and not others:
        return {"error": "No approaches available for this runway"}

    # --- Check if METAR is available ---
    test_prefix = ils_gls[0] if ils_gls else others[0]
    test_result = calculate_minima(
        airport=airport,
        runway=runway,
        aircraft=aircraft,
        approach=test_prefix
    )
    
    metar_unavailable = test_result.get("status") == "METAR UNAVAILABLE"

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
    # METAR UNAVAILABLE → Recommend lowest requirement
    # ============================================================
    if metar_unavailable:
        all_approaches = []
        
        # Prioritize ILS/GLS approaches first (CAT I → CAT III)
        def cat_rank(prefix):
            if prefix.startswith("il"): return int(prefix[2])
            if prefix.startswith("gl"): return int(prefix[3])
            return 999  # Non-ILS/GLS gets low priority
        
        # Collect all ILS/GLS approaches with their requirements
        for prefix in ils_gls:
            result = calculate_minima(
                airport=airport,
                runway=runway,
                aircraft=aircraft,
                approach=prefix
            )
            required = result.get("required", 0)
            if isinstance(required, int) and required > 0:
                all_approaches.append((cat_rank(prefix), required, prefix))
        
        # Collect all other approaches with their requirements
        for prefix in others:
            result = calculate_minima(
                airport=airport,
                runway=runway,
                aircraft=aircraft,
                approach=prefix
            )
            required = result.get("required", 0)
            if isinstance(required, int) and required > 0:
                all_approaches.append((999, required, prefix))
        
        if all_approaches:
            # Sort by: 1) ILS/GLS category (lower is better), 2) lowest requirement
            all_approaches.sort(key=lambda x: (x[0], x[1]))
            return {
                "recommended": all_approaches[0][2],
                "metar_unavailable": True,
                "message": "No METAR available - recommended approach has lowest visibility requirement"
            }
        
        return {"error": "No approaches available with defined minima"}

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
        result = calculate_minima(
            airport=airport,
            runway=runway,
            aircraft=aircraft,
            approach=prefix
        )

        if result.get("status") != "ABOVE MINIMA":
            continue

        required = result.get("required")
        if not isinstance(required, int) or required <= 0:
            continue

        candidates.append((required, prefix))

    if candidates:
        candidates.sort(key=lambda x: x[0])
        return {"recommended": candidates[0][1]}

    return {"error": "No suitable approach above minima"}
