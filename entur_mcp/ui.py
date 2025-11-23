"""UI formatting utilities for MCP rich content responses."""

from __future__ import annotations

import base64
import io
import math
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, List, Optional, Tuple

if TYPE_CHECKING:
    from entur_mcp.models import (
        PlaceReference,
        StopDeparture,
        StopDeparturesResult,
        TripItinerary,
        TripLeg,
        TripPlanResult,
    )


def format_time(dt: datetime) -> str:
    """Format datetime to HH:MM string."""
    return dt.strftime("%H:%M")


def format_delay(aimed: datetime, expected: datetime) -> str:
    """Format delay information between aimed and expected times."""
    delay_seconds = (expected - aimed).total_seconds()
    if abs(delay_seconds) < 60:
        return ""
    delay_minutes = int(delay_seconds / 60)
    if delay_minutes > 0:
        return f"+{delay_minutes}min"
    return f"{delay_minutes}min"


def get_status_indicator(realtime: bool, realtime_state: str, aimed: datetime, expected: datetime) -> str:
    """Get a status indicator for a departure."""
    if realtime_state == "cancelled":
        return "CANCELLED"

    delay_seconds = (expected - aimed).total_seconds()
    if not realtime:
        return "Scheduled"
    if abs(delay_seconds) < 60:
        return "On time"
    if delay_seconds > 0:
        return f"Delayed {int(delay_seconds / 60)}min"
    return f"Early {int(abs(delay_seconds) / 60)}min"


def format_departures_table(result: "StopDeparturesResult") -> str:
    """Format stop departures as a markdown table.

    Args:
        result: StopDeparturesResult from the Entur API

    Returns:
        Formatted markdown string with table and header
    """
    stop = result.stop_place
    departures = result.departures

    lines = []
    lines.append(f"## Departures from {stop.name}")
    lines.append(f"*Stop ID: {stop.id}*")
    if stop.latitude and stop.longitude:
        lines.append(f"*Location: {stop.latitude:.5f}, {stop.longitude:.5f}*")
    lines.append("")

    if not departures:
        lines.append("No upcoming departures found.")
        return "\n".join(lines)

    # Table header
    lines.append("| Time | Line | Destination | Platform | Status |")
    lines.append("|------|------|-------------|----------|--------|")

    for dep in departures:
        time_str = format_time(dep.expected_departure_time)
        delay = format_delay(dep.aimed_departure_time, dep.expected_departure_time)
        if delay:
            time_str = f"{time_str} ({delay})"

        line_code = dep.line_public_code or dep.line_name or "?"
        destination = dep.destination_display or "Unknown"
        platform = dep.quay_name or "-"
        status = get_status_indicator(
            dep.realtime,
            dep.realtime_state,
            dep.aimed_departure_time,
            dep.expected_departure_time
        )

        # Escape pipe characters in text
        destination = destination.replace("|", "\\|")
        platform = platform.replace("|", "\\|")

        lines.append(f"| {time_str} | {line_code} | {destination} | {platform} | {status} |")

    return "\n".join(lines)


def format_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable string."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    if hours > 0:
        return f"{hours}h {minutes}min"
    return f"{minutes}min"


def get_mode_emoji(mode: str) -> str:
    """Get an emoji/symbol for transport mode."""
    mode_symbols = {
        "foot": "Walk",
        "rail": "Train",
        "metro": "Metro",
        "bus": "Bus",
        "tram": "Tram",
        "water": "Ferry",
        "air": "Flight",
        "coach": "Coach",
        "funicular": "Funicular",
        "cableway": "Cable",
        "taxi": "Taxi",
    }
    return mode_symbols.get(mode.lower(), mode.capitalize())


def format_trip_itinerary(itinerary: "TripItinerary", index: int) -> str:
    """Format a single trip itinerary as markdown."""
    lines = []

    start = format_time(itinerary.start_time)
    end = format_time(itinerary.end_time)
    duration = format_duration(itinerary.duration_seconds)

    lines.append(f"### Option {index + 1}: {start} - {end} ({duration})")
    lines.append("")

    # Legs table
    lines.append("| Step | Mode | From | To | Departs | Arrives | Line |")
    lines.append("|------|------|------|-----|---------|---------|------|")

    for i, leg in enumerate(itinerary.legs, 1):
        mode = get_mode_emoji(leg.mode)
        from_name = leg.from_place.name if leg.from_place else "-"
        to_name = leg.to_place.name if leg.to_place else "-"

        depart = format_time(leg.expected_start_time or leg.aimed_start_time) if (leg.expected_start_time or leg.aimed_start_time) else "-"
        arrive = format_time(leg.expected_end_time or leg.aimed_end_time) if (leg.expected_end_time or leg.aimed_end_time) else "-"

        line_info = leg.line_public_code or leg.line_name or "-"

        # Escape pipe characters
        from_name = from_name.replace("|", "\\|")[:25]
        to_name = to_name.replace("|", "\\|")[:25]

        lines.append(f"| {i} | {mode} | {from_name} | {to_name} | {depart} | {arrive} | {line_info} |")

    return "\n".join(lines)


def format_trip_plan_table(result: "TripPlanResult") -> str:
    """Format trip plan results as markdown tables.

    Args:
        result: TripPlanResult from the Entur API

    Returns:
        Formatted markdown string with trip options
    """
    lines = []

    from_name = result.from_place.name
    to_name = result.to_place.name

    lines.append(f"## Journey: {from_name} to {to_name}")
    lines.append("")

    if not result.itineraries:
        lines.append("No journey options found.")
        return "\n".join(lines)

    # Summary table
    lines.append("### Summary")
    lines.append("| Option | Departs | Arrives | Duration | Changes |")
    lines.append("|--------|---------|---------|----------|---------|")

    for i, itin in enumerate(result.itineraries):
        depart = format_time(itin.start_time)
        arrive = format_time(itin.end_time)
        duration = format_duration(itin.duration_seconds)
        # Count non-walk legs as changes
        transit_legs = [leg for leg in itin.legs if leg.mode.lower() != "foot"]
        changes = max(0, len(transit_legs) - 1)

        lines.append(f"| {i + 1} | {depart} | {arrive} | {duration} | {changes} |")

    lines.append("")

    # Detailed itineraries
    for i, itin in enumerate(result.itineraries):
        lines.append(format_trip_itinerary(itin, i))
        lines.append("")

    return "\n".join(lines)


def extract_route_coordinates(result: "TripPlanResult") -> List[Tuple[float, float]]:
    """Extract key coordinates from a trip plan for map visualization.

    Returns list of (lat, lon) tuples for all significant points in the route.
    """
    coords = []

    # Add origin
    if result.from_place.latitude and result.from_place.longitude:
        coords.append((result.from_place.latitude, result.from_place.longitude))

    # Use first itinerary for the route
    if result.itineraries:
        itin = result.itineraries[0]
        for leg in itin.legs:
            if leg.from_place and leg.from_place.latitude and leg.from_place.longitude:
                coords.append((leg.from_place.latitude, leg.from_place.longitude))
            if leg.to_place and leg.to_place.latitude and leg.to_place.longitude:
                coords.append((leg.to_place.latitude, leg.to_place.longitude))

    # Add destination
    if result.to_place.latitude and result.to_place.longitude:
        coords.append((result.to_place.latitude, result.to_place.longitude))

    # Remove duplicates while preserving order
    seen = set()
    unique_coords = []
    for coord in coords:
        key = (round(coord[0], 5), round(coord[1], 5))
        if key not in seen:
            seen.add(key)
            unique_coords.append(coord)

    return unique_coords


def generate_static_map_url(
    coordinates: List[Tuple[float, float]],
    width: int = 600,
    height: int = 400,
    zoom: Optional[int] = None
) -> str:
    """Generate a URL for a static map image using OpenStreetMap.

    Uses geoapify static maps API (free tier available) as a fallback-friendly option.

    Args:
        coordinates: List of (lat, lon) tuples
        width: Image width in pixels
        height: Image height in pixels
        zoom: Optional zoom level (auto-calculated if not provided)

    Returns:
        URL to static map image
    """
    if not coordinates:
        return ""

    # Calculate bounding box
    lats = [c[0] for c in coordinates]
    lons = [c[1] for c in coordinates]

    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)

    center_lat = (min_lat + max_lat) / 2
    center_lon = (min_lon + max_lon) / 2

    # Calculate appropriate zoom level if not provided
    if zoom is None:
        lat_diff = max_lat - min_lat
        lon_diff = max_lon - min_lon
        max_diff = max(lat_diff, lon_diff)

        if max_diff < 0.01:
            zoom = 15
        elif max_diff < 0.05:
            zoom = 13
        elif max_diff < 0.1:
            zoom = 12
        elif max_diff < 0.5:
            zoom = 10
        elif max_diff < 1:
            zoom = 9
        else:
            zoom = 7

    # Build marker string for OpenStreetMap static map
    # Using staticmap.geoapify.com (free tier)
    markers = []

    # Origin marker (green)
    if coordinates:
        lat, lon = coordinates[0]
        markers.append(f"lonlat:{lon},{lat};color:%2322c55e;size:large")

    # Destination marker (red)
    if len(coordinates) > 1:
        lat, lon = coordinates[-1]
        markers.append(f"lonlat:{lon},{lat};color:%23ef4444;size:large")

    # Intermediate stops (blue, smaller)
    for lat, lon in coordinates[1:-1]:
        markers.append(f"lonlat:{lon},{lat};color:%233b82f6;size:small")

    marker_str = "&marker=".join(markers)

    # Build URL (uses geoapify free tier - may need API key for production)
    # Alternative: use OSM-based staticmap services
    url = (
        f"https://maps.geoapify.com/v1/staticmap"
        f"?style=osm-bright"
        f"&width={width}&height={height}"
        f"&center=lonlat:{center_lon},{center_lat}"
        f"&zoom={zoom}"
    )

    if markers:
        url += f"&marker={marker_str}"

    return url


async def generate_map_image(
    coordinates: List[Tuple[float, float]],
    width: int = 600,
    height: int = 400,
) -> Optional[bytes]:
    """Generate a static map image as PNG bytes.

    Uses staticmaps library if available, otherwise returns None.

    Args:
        coordinates: List of (lat, lon) tuples
        width: Image width in pixels
        height: Image height in pixels

    Returns:
        PNG image bytes or None if generation fails
    """
    try:
        import staticmaps
    except ImportError:
        return None

    if not coordinates:
        return None

    try:
        context = staticmaps.Context()
        context.set_tile_provider(staticmaps.tile_provider_OSM)

        # Add markers
        for i, (lat, lon) in enumerate(coordinates):
            if i == 0:
                # Origin - green
                color = staticmaps.parse_color("#22c55e")
            elif i == len(coordinates) - 1:
                # Destination - red
                color = staticmaps.parse_color("#ef4444")
            else:
                # Intermediate - blue
                color = staticmaps.parse_color("#3b82f6")

            marker = staticmaps.create_latlng(lat, lon)
            context.add_object(
                staticmaps.Marker(marker, color=color, size=12)
            )

        # Add line connecting points
        if len(coordinates) >= 2:
            line_coords = [staticmaps.create_latlng(lat, lon) for lat, lon in coordinates]
            context.add_object(
                staticmaps.Line(line_coords, color=staticmaps.parse_color("#3b82f6"), width=3)
            )

        # Render to PNG
        image = context.render_pillow(width, height)

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    except Exception:
        return None


def encode_image_base64(image_bytes: bytes) -> str:
    """Encode image bytes to base64 string."""
    return base64.b64encode(image_bytes).decode("utf-8")


def generate_ascii_map(coordinates: List[Tuple[float, float]], width: int = 50, height: int = 20) -> str:
    """Generate a simple ASCII representation of the route.

    Fallback visualization when image generation is not available.

    Args:
        coordinates: List of (lat, lon) tuples
        width: Character width of the map
        height: Character height of the map

    Returns:
        ASCII art representation of the route
    """
    if not coordinates or len(coordinates) < 2:
        return ""

    lats = [c[0] for c in coordinates]
    lons = [c[1] for c in coordinates]

    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)

    # Add padding
    lat_range = max_lat - min_lat or 0.01
    lon_range = max_lon - min_lon or 0.01

    # Create grid
    grid = [[' ' for _ in range(width)] for _ in range(height)]

    # Plot points
    for i, (lat, lon) in enumerate(coordinates):
        x = int((lon - min_lon) / lon_range * (width - 1)) if lon_range > 0 else width // 2
        y = int((max_lat - lat) / lat_range * (height - 1)) if lat_range > 0 else height // 2

        x = max(0, min(width - 1, x))
        y = max(0, min(height - 1, y))

        if i == 0:
            grid[y][x] = 'A'  # Origin
        elif i == len(coordinates) - 1:
            grid[y][x] = 'B'  # Destination
        else:
            grid[y][x] = '*'  # Intermediate

    # Build ASCII output
    lines = []
    lines.append("```")
    lines.append("+" + "-" * width + "+")
    for row in grid:
        lines.append("|" + "".join(row) + "|")
    lines.append("+" + "-" * width + "+")
    lines.append("A = Origin, B = Destination, * = Stop")
    lines.append("```")

    return "\n".join(lines)


def generate_interactive_map_html(
    coordinates: List[Tuple[float, float]],
    place_names: Optional[List[str]] = None,
    title: str = "Journey Route",
) -> str:
    """Generate an interactive HTML map using Leaflet.js.

    This creates a self-contained HTML document with an interactive map
    that can be rendered in an MCP Apps iframe or saved as a standalone file.

    Args:
        coordinates: List of (lat, lon) tuples for the route
        place_names: Optional list of place names corresponding to coordinates
        title: Title for the map

    Returns:
        Complete HTML document string with embedded Leaflet map
    """
    if not coordinates:
        return "<html><body><p>No route coordinates available.</p></body></html>"

    # Calculate center and bounds
    lats = [c[0] for c in coordinates]
    lons = [c[1] for c in coordinates]

    center_lat = sum(lats) / len(lats)
    center_lon = sum(lons) / len(lons)

    # Build markers JavaScript
    markers_js = []
    for i, (lat, lon) in enumerate(coordinates):
        if i == 0:
            color = "#22c55e"  # Green for origin
            label = "A"
            popup = place_names[i] if place_names and i < len(place_names) else "Origin"
        elif i == len(coordinates) - 1:
            color = "#ef4444"  # Red for destination
            label = "B"
            popup = place_names[i] if place_names and i < len(place_names) else "Destination"
        else:
            color = "#3b82f6"  # Blue for intermediate
            label = str(i)
            popup = place_names[i] if place_names and i < len(place_names) else f"Stop {i}"

        markers_js.append(f"""
        L.circleMarker([{lat}, {lon}], {{
            radius: {12 if i == 0 or i == len(coordinates) - 1 else 8},
            fillColor: '{color}',
            color: '#ffffff',
            weight: 2,
            opacity: 1,
            fillOpacity: 0.9
        }}).addTo(map).bindPopup('<strong>{popup}</strong>');
        """)

    # Build polyline coordinates
    polyline_coords = ", ".join([f"[{lat}, {lon}]" for lat, lon in coordinates])

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
        #map {{ width: 100%; height: 100vh; }}
        .legend {{
            background: white;
            padding: 10px 14px;
            border-radius: 8px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.2);
            font-size: 13px;
            line-height: 1.6;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .legend-dot {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
            border: 2px solid white;
            box-shadow: 0 1px 3px rgba(0,0,0,0.3);
        }}
        .title-control {{
            background: white;
            padding: 8px 12px;
            border-radius: 8px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.2);
            font-weight: 600;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div id="map"></div>
    <script>
        // Initialize map
        const map = L.map('map').setView([{center_lat}, {center_lon}], 12);

        // Add OpenStreetMap tiles
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        }}).addTo(map);

        // Add route polyline
        const routeCoords = [{polyline_coords}];
        const polyline = L.polyline(routeCoords, {{
            color: '#3b82f6',
            weight: 4,
            opacity: 0.8,
            dashArray: '10, 10'
        }}).addTo(map);

        // Add markers
        {"".join(markers_js)}

        // Fit map to route bounds with padding
        map.fitBounds(polyline.getBounds(), {{ padding: [50, 50] }});

        // Add legend
        const legend = L.control({{ position: 'bottomright' }});
        legend.onAdd = function(map) {{
            const div = L.DomUtil.create('div', 'legend');
            div.innerHTML = `
                <div class="legend-item"><div class="legend-dot" style="background: #22c55e;"></div> Origin</div>
                <div class="legend-item"><div class="legend-dot" style="background: #3b82f6;"></div> Stop</div>
                <div class="legend-item"><div class="legend-dot" style="background: #ef4444;"></div> Destination</div>
            `;
            return div;
        }};
        legend.addTo(map);

        // Add title
        const titleControl = L.control({{ position: 'topleft' }});
        titleControl.onAdd = function(map) {{
            const div = L.DomUtil.create('div', 'title-control');
            div.innerHTML = '{title}';
            return div;
        }};
        titleControl.addTo(map);
    </script>
</body>
</html>"""

    return html


def generate_trip_map_html(result: "TripPlanResult", itinerary_index: int = 0) -> str:
    """Generate an interactive map HTML for a specific trip itinerary.

    Args:
        result: TripPlanResult from the Entur API
        itinerary_index: Which itinerary to display (default: first one)

    Returns:
        Complete HTML document string with embedded Leaflet map
    """
    coordinates = []
    place_names = []

    # Add origin
    if result.from_place.latitude and result.from_place.longitude:
        coordinates.append((result.from_place.latitude, result.from_place.longitude))
        place_names.append(result.from_place.name)

    # Add itinerary stops
    if result.itineraries and itinerary_index < len(result.itineraries):
        itin = result.itineraries[itinerary_index]
        for leg in itin.legs:
            if leg.from_place and leg.from_place.latitude and leg.from_place.longitude:
                coord = (leg.from_place.latitude, leg.from_place.longitude)
                if not coordinates or coordinates[-1] != coord:
                    coordinates.append(coord)
                    place_names.append(leg.from_place.name)
            if leg.to_place and leg.to_place.latitude and leg.to_place.longitude:
                coord = (leg.to_place.latitude, leg.to_place.longitude)
                if not coordinates or coordinates[-1] != coord:
                    coordinates.append(coord)
                    place_names.append(leg.to_place.name)

    # Ensure destination is included
    if result.to_place.latitude and result.to_place.longitude:
        dest_coord = (result.to_place.latitude, result.to_place.longitude)
        if not coordinates or coordinates[-1] != dest_coord:
            coordinates.append(dest_coord)
            place_names.append(result.to_place.name)

    title = f"{result.from_place.name} to {result.to_place.name}"
    return generate_interactive_map_html(coordinates, place_names, title)
