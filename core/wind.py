import math
import re


def parse_wind_data(metar):
    """
    Extract wind direction and speed from METAR string.
    Returns (direction, speed, gust) tuple or (None, None, None) if not found.
    """
    if not metar:
        return None, None, None
    
    wind_pattern = r'(\d{3}|VRB)(\d{2,3})(G(\d{2,3}))?KT'
    match = re.search(wind_pattern, metar)
    
    if match:
        direction_str = match.group(1)
        speed_str = match.group(2)
        gust_str = match.group(4)  # group(3) is the full "G\d{2,3}", group(4) is just the number
        
        if direction_str == "VRB":
            # Variable wind - return None for direction
            return None, int(speed_str), int(gust_str) if gust_str else None
            
        return int(direction_str), int(speed_str), int(gust_str) if gust_str else None
    
    return None, None, None


def calculate_wind_components(wind_speed, wind_from_direction, runway_heading):
    """
    Calculate headwind and crosswind components.
    
    Args:
        wind_speed: Wind speed in knots
        wind_from_direction: Direction wind is coming from (degrees)
        runway_heading: Runway heading/track (degrees)
    
    Returns:
        (headwind, crosswind) tuple in knots
        - Positive headwind = headwind, negative = tailwind
        - Positive crosswind = from right, negative = from left
    """
    if wind_from_direction is None or wind_speed is None:
        return None, None
    
    angle_diff = wind_from_direction - runway_heading
    angle_rad = math.radians(angle_diff)

    headwind = wind_speed * math.cos(angle_rad)
    crosswind = wind_speed * math.sin(angle_rad)
    
    return headwind, crosswind


def get_runway_heading(runway):
    """
    Extract magnetic heading from runway identifier.
    E.g., "27L" -> 270, "09R" -> 90, "36" -> 360
    """
    # Extract just the numeric part
    match = re.match(r'(\d{2})', runway)
    if match:
        heading = int(match.group(1)) * 10
        return heading
    return None
