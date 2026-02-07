import aiohttp
import asyncio
import re

VATSIM_METAR_URL = "https://metar.vatsim.net/{}"


def get_metar(icao: str):
    """
    Fetch METAR synchronously (Flask-friendly wrapper)
    Returns the METAR string or None if unavailable
    """
    return asyncio.run(_fetch_metar(icao))


async def _fetch_metar(icao: str):
    url = VATSIM_METAR_URL.format(icao)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    metar_text = await response.text()
                    # Check if we got actual METAR data
                    if metar_text and metar_text.strip() and not metar_text.startswith("No METAR"):
                        return metar_text
    except Exception:
        pass
    return None  # Return None when METAR is unavailable


def get_visibility(metar: str, runway: str) -> str:
    if not metar:
        return "N/A"

    if "CAVOK" in metar:
        return "9999"

    # RVR (e.g. R27R/0600)
    rw = runway.zfill(2)
    rvr_match = re.search(rf"R{rw}[LCR]?/(\d{{4}})", metar)
    if rvr_match:
        return rvr_match.group(1)

    # Statute miles (e.g. 3SM)
    sm_match = re.search(r"(\d+)SM", metar)
    if sm_match:
        return str(int(sm_match.group(1)) * 1609)

    # Plain visibility (e.g. 4000)
    vis_match = re.search(r"\b(\d{4})\b", metar)
    if vis_match:
        return vis_match.group(1)

    return "N/A"
