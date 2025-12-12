import folium
from folium import plugins
from folium.plugins import BeautifyIcon
from icecream import ic
import json

def place_map_create(places=None, latitude=None, longitude=None, name=None, zoom_start=10, scroll_wheel_zoom=False):
    """Create a map centered on a place or set of places"""
    try:
        # Modern map configuration with Street tiles as default
        map_kwargs = {
            'prefer_canvas': True,
            'zoom_control': True,
            'tiles': 'OpenStreetMap',
            'tiles_name': 'Street',
            'zoom_start': zoom_start,
            'scrollWheelZoom': scroll_wheel_zoom,
            'dragging': True,
            'control_scale': True,
            'width': '100%',
            'height': '100%',
            'no_css': True,
        }

        # Single place mode
        if places is None and latitude is not None and longitude is not None:
            m = folium.Map(location=[float(latitude), float(longitude)], **map_kwargs)
            if name:
                folium.Marker(
                    [float(latitude), float(longitude)],
                    popup=name,
                    icon=folium.Icon(color='blue', icon='info-sign')
                ).add_to(m)
            map_html = m.get_root().render()
            return map_html

        # Default to Austin center if no places provided
        if not places:
            # ic("Places Map: No places provided, using Austin center")
            m = folium.Map(location=[30.2672, -97.7431], **map_kwargs)
            map_html = m.get_root().render()
            return map_html

        # Calculate map center from active places
        active_places = [p for p in places if p.is_active]
        all_lats = [float(p.latitude) for p in places]
        all_lons = [float(p.longitude) for p in places]

        if active_places:
            active_lats = [float(p.latitude) for p in active_places]
            active_lons = [float(p.longitude) for p in active_places]
            center = [sum(active_lats) / len(active_lats), sum(active_lons) / len(active_lons)]
        else:
            center = [sum(all_lats) / len(all_lats), sum(all_lons) / len(all_lons)]

        # Initialize map with a specific ID that matches what places-map-folium.js expects
        m = folium.Map(location=center, **map_kwargs)
        m._name = "places_overview_map"

        # Add markers
        if places:
            for place in places:
                popup_html = f"<h6>{place.name}</h6>Status: {'Active' if place.is_active else 'Inactive'}"
                folium.Marker(
                    location=[float(place.latitude), float(place.longitude)],
                    popup=folium.Popup(popup_html, max_width=200),
                    icon=folium.Icon(
                        color='blue' if place.is_active else 'red',
                        icon='info-sign'
                    )
                ).add_to(m)

        # Fit map to bounds if multiple places are provided
        if places and len(places) > 1:
            m.fit_bounds([[min(all_lats), min(all_lons)], [max(all_lats), max(all_lons)]])

        return m.get_root().render()

    except Exception as e:
        ic("Error creating map:", str(e))
        return ""
