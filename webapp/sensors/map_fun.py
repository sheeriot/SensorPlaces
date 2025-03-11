import folium
from folium import plugins
from folium.plugins import BeautifyIcon
from icecream import ic
import json

def place_map_create(places=None, latitude=None, longitude=None, name=None, zoom_start=13):
    """Create a map centered on a place or set of places"""
    try:
        # Modern map configuration with Street tiles as default
        map_kwargs = {
            'prefer_canvas': True,
            'zoom_control': True,
            'tiles': 'OpenStreetMap',
            'tiles_name': 'Street',
            'zoom_start': zoom_start,
            'scrollWheelZoom': True,
            'dragging': True,
            'control_scale': True,
            'width': '100%',
            'height': '100%'
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
        
        # Initialize map
        m = folium.Map(location=center, **map_kwargs)
        m._name = "places_overview_map"
        
        # Tell Folium not to include resources we already have
        m.default_css = []
        m.default_js = []
        
        # Add markers
        for place in places:
            popup_html = f"""
            <div class="place-popup">
                <h4>{place.name}</h4>
                <p>Status: {'Active' if place.is_active else 'inactive'}</p>
            </div>
            """
            
            # Create marker with all options
            icon_html = f'''
                <div class="awesome-marker-icon-{'blue' if place.is_active else 'red'} awesome-marker place-marker{' d-none opacity-50 text-muted' if not place.is_active else ''}"
                    data-place-slug="{place.slug}"
                    data-place-active="{str(place.is_active).lower()}"
                    data-place-lat="{str(place.latitude)}"
                    data-place-lon="{str(place.longitude)}"
                    data-place-name="{place.name}"
                    style="margin-left: -17px; margin-top: -42px; width: 35px; height: 45px;"
                >
                    <i class="bi bi-{'info-circle' if place.is_active else 'question-circle'} icon-white"></i>
                </div>
            '''
            
            marker = folium.Marker(
                location=[float(place.latitude), float(place.longitude)],
                popup=folium.Popup(popup_html, max_width=300),
                icon=folium.DivIcon(html=icon_html),
                name=f"place_marker_{place.slug}"
            )
            marker.add_to(m)
        
        # Calculate bounds for both active and all places
        bounds_data = {
            "initial_state": {
                "hide_inactive": True  # Start with inactive places hidden
            }
        }
        
        # Active places bounds
        if active_places:
            bounds_data["active"] = {
                "sw": [min(active_lats), min(active_lons)],
                "ne": [max(active_lats), max(active_lons)]
            }
            # Fit map to active places initially
            m.fit_bounds([bounds_data["active"]["sw"], bounds_data["active"]["ne"]])
        
        # All places bounds
        if places:
            bounds_data["all"] = {
                "sw": [min(all_lats), min(all_lons)],
                "ne": [max(all_lats), max(all_lons)]
            }
            # If no active places, fit to all places
            if not active_places:
                m.fit_bounds([bounds_data["all"]["sw"], bounds_data["all"]["ne"]])
        
        # Get the map HTML
        map_html = m.get_root().render()
        
        # Add the bounds data as a proper JSON attribute
        map_html = map_html.replace(
            'class="folium-map"',
            f'class="folium-map" data-map-bounds=\'{json.dumps(bounds_data)}\''
        )
        
        # ic("Generated map HTML length:", len(map_html))
        return map_html
    
    except Exception as e:
        ic("Error creating map:", str(e))
        return "" 