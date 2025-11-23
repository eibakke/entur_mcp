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


def generate_searchable_map_html(
    initial_coordinates: Optional[List[Tuple[float, float]]] = None,
    initial_place_names: Optional[List[str]] = None,
    center_lat: float = 59.91,  # Default to Oslo
    center_lon: float = 10.75,
    title: str = "Entur Journey Planner",
) -> str:
    """Generate an interactive HTML map with search and trip planning capabilities.

    This creates a full-featured journey planning interface that can:
    - Search for places using text input
    - Click on map to set origin/destination
    - Display route with markers
    - Send trip planning requests back to the MCP host via postMessage

    Args:
        initial_coordinates: Optional initial route to display
        initial_place_names: Optional place names for initial route
        center_lat: Initial map center latitude (default: Oslo)
        center_lon: Initial map center longitude (default: Oslo)
        title: Title for the map interface

    Returns:
        Complete HTML document string with interactive journey planner
    """
    # Build initial markers if provided
    initial_markers_js = ""
    initial_polyline_js = ""

    if initial_coordinates and len(initial_coordinates) >= 2:
        markers_js_parts = []
        for i, (lat, lon) in enumerate(initial_coordinates):
            if i == 0:
                color = "#22c55e"
                popup = initial_place_names[i] if initial_place_names and i < len(initial_place_names) else "Origin"
            elif i == len(initial_coordinates) - 1:
                color = "#ef4444"
                popup = initial_place_names[i] if initial_place_names and i < len(initial_place_names) else "Destination"
            else:
                color = "#3b82f6"
                popup = initial_place_names[i] if initial_place_names and i < len(initial_place_names) else f"Stop {i}"

            markers_js_parts.append(f"""
            addMarker({lat}, {lon}, '{color}', '{popup}');
            """)

        initial_markers_js = "".join(markers_js_parts)

        polyline_coords = ", ".join([f"[{lat}, {lon}]" for lat, lon in initial_coordinates])
        initial_polyline_js = f"""
        currentRoute = L.polyline([{polyline_coords}], {{
            color: '#3b82f6',
            weight: 4,
            opacity: 0.8,
            dashArray: '10, 10'
        }}).addTo(map);
        map.fitBounds(currentRoute.getBounds(), {{ padding: [50, 50] }});
        """

        # Update center to route center
        center_lat = sum(c[0] for c in initial_coordinates) / len(initial_coordinates)
        center_lon = sum(c[1] for c in initial_coordinates) / len(initial_coordinates)

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
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            flex-direction: column;
            height: 100vh;
        }}

        .search-panel {{
            background: #ffffff;
            padding: 16px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            z-index: 1000;
        }}

        .search-panel h2 {{
            font-size: 18px;
            margin-bottom: 12px;
            color: #1e293b;
        }}

        .search-row {{
            display: flex;
            gap: 12px;
            margin-bottom: 12px;
            flex-wrap: wrap;
        }}

        .search-group {{
            flex: 1;
            min-width: 200px;
        }}

        .search-group label {{
            display: block;
            font-size: 12px;
            font-weight: 600;
            color: #64748b;
            margin-bottom: 4px;
            text-transform: uppercase;
        }}

        .search-input {{
            width: 100%;
            padding: 10px 12px;
            border: 2px solid #e2e8f0;
            border-radius: 8px;
            font-size: 14px;
            transition: border-color 0.2s;
        }}

        .search-input:focus {{
            outline: none;
            border-color: #3b82f6;
        }}

        .search-input.origin-set {{
            border-color: #22c55e;
            background-color: #f0fdf4;
        }}

        .search-input.destination-set {{
            border-color: #ef4444;
            background-color: #fef2f2;
        }}

        .button-row {{
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }}

        .btn {{
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }}

        .btn-primary {{
            background: #3b82f6;
            color: white;
        }}

        .btn-primary:hover {{
            background: #2563eb;
        }}

        .btn-primary:disabled {{
            background: #94a3b8;
            cursor: not-allowed;
        }}

        .btn-secondary {{
            background: #f1f5f9;
            color: #475569;
        }}

        .btn-secondary:hover {{
            background: #e2e8f0;
        }}

        .btn-swap {{
            background: #f1f5f9;
            color: #475569;
            padding: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
        }}

        .instructions {{
            font-size: 12px;
            color: #64748b;
            margin-top: 8px;
        }}

        #map {{
            flex: 1;
            width: 100%;
        }}

        .status-bar {{
            background: #1e293b;
            color: white;
            padding: 8px 16px;
            font-size: 13px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .status-message {{
            color: #94a3b8;
        }}

        .legend {{
            background: white;
            padding: 10px 14px;
            border-radius: 8px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.2);
            font-size: 12px;
            line-height: 1.8;
        }}

        .legend-item {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .legend-dot {{
            width: 10px;
            height: 10px;
            border-radius: 50%;
            border: 2px solid white;
            box-shadow: 0 1px 2px rgba(0,0,0,0.2);
        }}

        .search-results {{
            position: absolute;
            background: white;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            max-height: 200px;
            overflow-y: auto;
            z-index: 2000;
            display: none;
        }}

        .search-result-item {{
            padding: 10px 12px;
            cursor: pointer;
            border-bottom: 1px solid #f1f5f9;
        }}

        .search-result-item:hover {{
            background: #f8fafc;
        }}

        .search-result-item:last-child {{
            border-bottom: none;
        }}

        .search-result-name {{
            font-weight: 500;
            color: #1e293b;
        }}

        .search-result-type {{
            font-size: 11px;
            color: #64748b;
        }}
    </style>
</head>
<body>
    <div class="search-panel">
        <h2>Plan Your Journey</h2>
        <div class="search-row">
            <div class="search-group" style="position: relative;">
                <label>From</label>
                <input type="text" id="origin-input" class="search-input" placeholder="Search or click map...">
                <div id="origin-results" class="search-results"></div>
            </div>
            <button class="btn btn-swap" onclick="swapLocations()" title="Swap origin and destination">
                &#8646;
            </button>
            <div class="search-group" style="position: relative;">
                <label>To</label>
                <input type="text" id="destination-input" class="search-input" placeholder="Search or click map...">
                <div id="destination-results" class="search-results"></div>
            </div>
        </div>
        <div class="button-row">
            <button class="btn btn-primary" id="plan-btn" onclick="planTrip()" disabled>
                Plan Trip
            </button>
            <button class="btn btn-secondary" onclick="clearAll()">
                Clear All
            </button>
        </div>
        <p class="instructions">
            Click on the map to set origin (first click) and destination (second click), or use the search boxes above.
        </p>
    </div>

    <div id="map"></div>

    <div class="status-bar">
        <span id="status-message" class="status-message">Click on the map or search to set your origin</span>
        <span id="coordinates"></span>
    </div>

    <script>
        // State
        let origin = null;  // {{ lat, lon, name }}
        let destination = null;
        let originMarker = null;
        let destinationMarker = null;
        let currentRoute = null;
        let markers = [];
        let clickMode = 'origin';  // 'origin' or 'destination'
        let searchTimeout = null;

        // Initialize map
        const map = L.map('map').setView([{center_lat}, {center_lon}], 12);

        // Add OpenStreetMap tiles
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        }}).addTo(map);

        // Add legend
        const legend = L.control({{ position: 'bottomright' }});
        legend.onAdd = function(map) {{
            const div = L.DomUtil.create('div', 'legend');
            div.innerHTML = `
                <div class="legend-item"><div class="legend-dot" style="background: #22c55e;"></div> Origin</div>
                <div class="legend-item"><div class="legend-dot" style="background: #ef4444;"></div> Destination</div>
                <div class="legend-item"><div class="legend-dot" style="background: #3b82f6;"></div> Route</div>
            `;
            return div;
        }};
        legend.addTo(map);

        // Helper to add marker
        function addMarker(lat, lon, color, popup) {{
            const marker = L.circleMarker([lat, lon], {{
                radius: 10,
                fillColor: color,
                color: '#ffffff',
                weight: 2,
                opacity: 1,
                fillOpacity: 0.9
            }}).addTo(map);
            if (popup) marker.bindPopup('<strong>' + popup + '</strong>');
            markers.push(marker);
            return marker;
        }}

        // Map click handler
        map.on('click', function(e) {{
            const lat = e.latlng.lat;
            const lon = e.latlng.lng;

            if (clickMode === 'origin') {{
                setOrigin(lat, lon, `${{lat.toFixed(5)}}, ${{lon.toFixed(5)}}`);
                clickMode = 'destination';
                updateStatus('Now click to set your destination');
            }} else {{
                setDestination(lat, lon, `${{lat.toFixed(5)}}, ${{lon.toFixed(5)}}`);
                clickMode = 'origin';
            }}
        }});

        function setOrigin(lat, lon, name) {{
            origin = {{ lat, lon, name }};

            if (originMarker) map.removeLayer(originMarker);
            originMarker = addMarker(lat, lon, '#22c55e', name);

            document.getElementById('origin-input').value = name;
            document.getElementById('origin-input').classList.add('origin-set');

            updatePlanButton();
            updateRoute();
        }}

        function setDestination(lat, lon, name) {{
            destination = {{ lat, lon, name }};

            if (destinationMarker) map.removeLayer(destinationMarker);
            destinationMarker = addMarker(lat, lon, '#ef4444', name);

            document.getElementById('destination-input').value = name;
            document.getElementById('destination-input').classList.add('destination-set');

            updatePlanButton();
            updateRoute();
        }}

        function updateRoute() {{
            if (currentRoute) {{
                map.removeLayer(currentRoute);
                currentRoute = null;
            }}

            if (origin && destination) {{
                currentRoute = L.polyline([
                    [origin.lat, origin.lon],
                    [destination.lat, destination.lon]
                ], {{
                    color: '#3b82f6',
                    weight: 4,
                    opacity: 0.6,
                    dashArray: '10, 10'
                }}).addTo(map);

                map.fitBounds(currentRoute.getBounds(), {{ padding: [50, 50] }});
                updateStatus('Ready to plan trip!');
            }}
        }}

        function updatePlanButton() {{
            const btn = document.getElementById('plan-btn');
            btn.disabled = !(origin && destination);
        }}

        function updateStatus(message) {{
            document.getElementById('status-message').textContent = message;
        }}

        function swapLocations() {{
            const tempOrigin = origin;
            const tempDestination = destination;
            const tempOriginMarker = originMarker;
            const tempDestinationMarker = destinationMarker;

            origin = null;
            destination = null;

            if (tempDestination) {{
                setOrigin(tempDestination.lat, tempDestination.lon, tempDestination.name);
            }}
            if (tempOrigin) {{
                setDestination(tempOrigin.lat, tempOrigin.lon, tempOrigin.name);
            }}

            if (!tempDestination) {{
                document.getElementById('origin-input').value = '';
                document.getElementById('origin-input').classList.remove('origin-set');
            }}
            if (!tempOrigin) {{
                document.getElementById('destination-input').value = '';
                document.getElementById('destination-input').classList.remove('destination-set');
            }}
        }}

        function clearAll() {{
            // Clear markers
            if (originMarker) map.removeLayer(originMarker);
            if (destinationMarker) map.removeLayer(destinationMarker);
            markers.forEach(m => map.removeLayer(m));
            if (currentRoute) map.removeLayer(currentRoute);

            origin = null;
            destination = null;
            originMarker = null;
            destinationMarker = null;
            currentRoute = null;
            markers = [];
            clickMode = 'origin';

            document.getElementById('origin-input').value = '';
            document.getElementById('destination-input').value = '';
            document.getElementById('origin-input').classList.remove('origin-set');
            document.getElementById('destination-input').classList.remove('destination-set');

            updatePlanButton();
            updateStatus('Click on the map or search to set your origin');
        }}

        function planTrip() {{
            if (!origin || !destination) return;

            updateStatus('Requesting trip plan...');

            // Send message to MCP host to trigger plan_trip tool
            const message = {{
                type: 'mcp_tool_call',
                tool_name: 'plan_trip_interactive',
                arguments: {{
                    from_latitude: origin.lat,
                    from_longitude: origin.lon,
                    to_latitude: destination.lat,
                    to_longitude: destination.lon
                }}
            }};

            // Post message to parent (MCP host)
            window.parent.postMessage(message, '*');

            // Also log for debugging
            console.log('Trip planning request:', message);
            updateStatus('Trip plan request sent! Waiting for response...');
        }}

        // Search functionality using Entur's geocoder
        async function searchPlaces(query, resultsElementId) {{
            if (query.length < 2) {{
                document.getElementById(resultsElementId).style.display = 'none';
                return;
            }}

            try {{
                // Use Entur's geocoder API
                const url = `https://api.entur.io/geocoder/v1/autocomplete?text=${{encodeURIComponent(query)}}&size=5&lang=en`;
                const response = await fetch(url, {{
                    headers: {{
                        'ET-Client-Name': 'EnturMCP-InteractiveMap'
                    }}
                }});

                if (!response.ok) throw new Error('Search failed');

                const data = await response.json();
                const results = data.features || [];

                const resultsDiv = document.getElementById(resultsElementId);
                resultsDiv.innerHTML = '';

                if (results.length === 0) {{
                    resultsDiv.style.display = 'none';
                    return;
                }}

                results.forEach(feature => {{
                    const props = feature.properties || {{}};
                    const coords = feature.geometry?.coordinates || [];

                    if (coords.length < 2) return;

                    const item = document.createElement('div');
                    item.className = 'search-result-item';
                    item.innerHTML = `
                        <div class="search-result-name">${{props.name || 'Unknown'}}</div>
                        <div class="search-result-type">${{props.locality || props.county || ''}}</div>
                    `;

                    item.onclick = () => {{
                        const lon = coords[0];
                        const lat = coords[1];
                        const name = props.name || `${{lat.toFixed(5)}}, ${{lon.toFixed(5)}}`;

                        if (resultsElementId === 'origin-results') {{
                            setOrigin(lat, lon, name);
                            map.setView([lat, lon], 14);
                        }} else {{
                            setDestination(lat, lon, name);
                            map.setView([lat, lon], 14);
                        }}

                        resultsDiv.style.display = 'none';
                    }};

                    resultsDiv.appendChild(item);
                }});

                // Position results below input
                const input = document.getElementById(resultsElementId.replace('-results', '-input'));
                const rect = input.getBoundingClientRect();
                resultsDiv.style.top = (rect.bottom + window.scrollY) + 'px';
                resultsDiv.style.left = rect.left + 'px';
                resultsDiv.style.width = rect.width + 'px';
                resultsDiv.style.display = 'block';

            }} catch (err) {{
                console.error('Search error:', err);
                document.getElementById(resultsElementId).style.display = 'none';
            }}
        }}

        // Setup search inputs
        document.getElementById('origin-input').addEventListener('input', (e) => {{
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => searchPlaces(e.target.value, 'origin-results'), 300);
        }});

        document.getElementById('destination-input').addEventListener('input', (e) => {{
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => searchPlaces(e.target.value, 'destination-results'), 300);
        }});

        // Close search results when clicking elsewhere
        document.addEventListener('click', (e) => {{
            if (!e.target.closest('.search-group')) {{
                document.getElementById('origin-results').style.display = 'none';
                document.getElementById('destination-results').style.display = 'none';
            }}
        }});

        // Initialize with any existing route
        {initial_markers_js}
        {initial_polyline_js}

        // Listen for messages from MCP host
        window.addEventListener('message', function(event) {{
            console.log('Received message from host:', event.data);
            // Handle response from MCP host if needed
            if (event.data.type === 'trip_result') {{
                updateStatus('Trip planned successfully!');
            }}
        }});
    </script>
</body>
</html>"""

    return html
