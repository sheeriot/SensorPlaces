/**
 * Places Map Folium System
 * Handles Folium map initialization and marker management
 * 
 * Debug Mode:
 * -----------
 * To enable debug tables and logging, add ?debug=true to your URL:
 * http://your-site/page?debug=true
 * 
 * Debug Output:
 * - Initialization status and source (URL vs code setting)
 * - Hide/Show inactive state changes
 * - Marker system analysis with visibility states
 * - Map bounds and view updates
 * 
 * Example URLs:
 * http://localhost:8000/sensors/?debug=true
 * http://localhost:8000/sensors/places/?debug=true
 */

const placesMapFoliumSystem = {
    state: {
        map: null,
        hideInactiveState: false,
        userHasAdjustedView: false,
        debug: false  // Default to false, will be updated in initialize()
    },

    async initialize() {
        // Check for debug mode in URL
        const urlParams = new URLSearchParams(window.location.search);
        this.state.debug = this.state.debug || urlParams.get('debug') === 'true';

        if (this.state.debug) {
            console.group('Places Map: Initialization');
            console.table([{
                component: 'Places Map',
                status: 'Starting',
                debugSource: urlParams.get('debug') === 'true' ? 'URL Parameter' : 'Code Setting',
                timestamp: new Date().toLocaleTimeString()
            }]);
            console.groupEnd();
        }

        const mapContainer = document.getElementById('places-map-folium');
        if (!mapContainer) return;

        try {
            const foliumMap = await this.waitForFoliumMap(mapContainer);
            if (!foliumMap) return;

            // Set initial state from map data
            try {
                const boundsData = JSON.parse(foliumMap.dataset.mapBounds || '{}');
                this.state.hideInactiveState = !!boundsData.initial_state?.hide_inactive;
            } catch (e) {
                console.warn('Failed to parse initial state:', e);
            }

            await this.initializeMapInstance(foliumMap);
            await this.setupHideInactiveListeners();
        } catch (error) {
            console.error('Map initialization error:', error);
        }
    },

    waitForFoliumMap(container) {
        return new Promise(resolve => {
            const findMap = () => {
                const map = container.querySelector('.folium-map');
                return map?.classList.contains('leaflet-container') ? map : null;
            };
            
            const map = findMap();
            if (map) {
                resolve(map);
                return;
            }
            
            const observer = new MutationObserver((mutations, obs) => {
                const map = findMap();
                if (map) {
                    obs.disconnect();
                    resolve(map);
                }
            });

            observer.observe(container, {
                childList: true,
                subtree: true,
                attributes: true,
                attributeFilter: ['class']
            });
        });
    },

    async initializeMapInstance(foliumMap) {
        if (this.state.debug) {
            console.log('Initializing map:', foliumMap.id);
        }

        // Wait for Folium's initialization script to run
        const leafletMap = await new Promise(resolve => {
            if (window[foliumMap.id]) {
                resolve(window[foliumMap.id]);
                return;
            }

            const checkInterval = setInterval(() => {
                if (window[foliumMap.id]) {
                    clearInterval(checkInterval);
                    resolve(window[foliumMap.id]);
                }
            }, 100);

            setTimeout(() => {
                clearInterval(checkInterval);
                resolve(null);
            }, 5000);
        });

        if (!leafletMap) {
            throw new Error('Could not find Leaflet map instance');
        }

        this.state.map = leafletMap;
        
        // Track user view adjustments
        this.state.map.on('zoomend dragend', () => {
            this.state.userHasAdjustedView = true;
        });

        this.setupMapEventHandlers(foliumMap);
        this.initializeMarkerSystem();

        window.dispatchEvent(new CustomEvent('leafletMapReady', {
            detail: { containerId: 'places-map-folium' }
        }));
    },

    setupHideInactiveListeners() {
        if (this.state.debug) {
            console.group('Hide Inactive System State');
            console.table([{
                component: 'Places Map',
                initialState: this.state.hideInactiveState ? 'Hidden' : 'Shown',
                source: 'map_bounds.initial_state',
                timestamp: new Date().toLocaleTimeString()
            }]);
            console.groupEnd();
        }

        // Listen for state changes
        window.addEventListener('hideInactiveStateChanged', (e) => {
            if (e.detail.model === 'place') {
                if (this.state.debug) {
                    console.group('State Change Event');
                    console.table([{
                        event: 'Hide Inactive',
                        model: e.detail.model,
                        from: this.state.hideInactiveState ? 'Hidden' : 'Shown',
                        to: e.detail.hideInactive ? 'Hidden' : 'Shown',
                        switchId: e.detail.switchId || 'N/A',
                        timestamp: new Date().toLocaleTimeString()
                    }]);
                    console.groupEnd();
                }

                this.state.hideInactiveState = e.detail.hideInactive;
                this.state.userHasAdjustedView = false;
                this.updateMarkersVisibility(e.detail.hideInactive);
            }
        });
    },

    updateMarkersVisibility(hideInactive) {
        const markerPane = document.querySelector('.leaflet-marker-pane');
        if (!markerPane) return;

        const markers = markerPane.querySelectorAll('.leaflet-marker-icon');
        const visibleMarkers = [];
        
        markers.forEach(marker => {
            const placeMarker = marker.querySelector('.place-marker');
            if (!placeMarker) return;

            const isActive = placeMarker.dataset.placeActive === 'true';

            // Handle inactive markers visibility
            if (!isActive) {
                marker.style.display = hideInactive ? 'none' : '';
                placeMarker.classList.toggle('d-none', hideInactive);
            }

            // Collect coordinates for visible markers
            if (isActive || !hideInactive) {
                const lat = parseFloat(placeMarker.dataset.placeLat);
                const lon = parseFloat(placeMarker.dataset.placeLon);
                if (!isNaN(lat) && !isNaN(lon)) {
                    visibleMarkers.push([lat, lon]);
                }
            }
        });

        if (visibleMarkers.length > 0 && this.state.map && !this.state.userHasAdjustedView) {
            this.fitMapToMarkers(visibleMarkers);
        }
    },

    fitMapToMarkers(markers) {
        const mapEl = document.querySelector('.folium-map');
        if (!mapEl || !this.state.map) return;

        try {
            const boundsData = JSON.parse(mapEl.dataset.mapBounds || '{}');
            const boundsType = this.state.hideInactiveState ? 'active' : 'all';
            
            // Use pre-calculated bounds if available
            const bounds = boundsData[boundsType] ? 
                [boundsData[boundsType].sw, boundsData[boundsType].ne] :
                L.latLngBounds(markers).pad(0.1);

            if (this.state.debug) {
                console.log('Fitting map to bounds:', {
                    type: boundsType,
                    bounds: bounds
                });
            }
            
            this.state.map.fitBounds(bounds);
        } catch (error) {
            console.error('Error fitting map to bounds:', error);
            this.state.map.fitBounds(L.latLngBounds(markers).pad(0.1));
        }
    },

    setupMapEventHandlers(mapElement) {
        // Only handle resize events to ensure map displays correctly
        const resizeObserver = new ResizeObserver(() => {
            if (this.state.map) {
                this.state.map.invalidateSize();
            }
        });
        
        resizeObserver.observe(mapElement);
    },

    initializeMarkerSystem() {
        const markerPane = document.querySelector('.leaflet-marker-pane');
        if (!markerPane) return;

        // First, analyze all markers without modifying them
        const markers = Array.from(markerPane.querySelectorAll('.leaflet-marker-icon'));
        const markerStates = markers
            .map(marker => {
                const placeMarker = marker.querySelector('.place-marker');
                if (!placeMarker) return null;

                const isActive = placeMarker.dataset.placeActive === 'true';
                const shouldBeHidden = !isActive && this.state.hideInactiveState;
                const isCurrentlyHidden = placeMarker.classList.contains('d-none');
                const lat = parseFloat(placeMarker.dataset.placeLat);
                const lon = parseFloat(placeMarker.dataset.placeLon);
                
                return {
                    name: placeMarker.dataset.placeName || 'Unnamed',
                    id: placeMarker.dataset.placeId || 'N/A',
                    active: isActive ? '✓' : '✗',
                    isHidden: isCurrentlyHidden ? '✓' : '✗',
                    shouldBeHidden: shouldBeHidden ? '✓' : '✗',
                    correct: shouldBeHidden === isCurrentlyHidden ? '✓' : '✗',
                    location: `${lat.toFixed(5)},${lon.toFixed(5)}`
                };
            })
            .filter(state => state !== null);

        if (this.state.debug) {
            console.group('Marker System Analysis');
            console.table(markerStates);
            console.log('Total Markers:', markerStates.length);
            console.groupEnd();
        }

        // Now process markers
        markers.forEach(this.processMarker.bind(this));

        // Watch for new markers
        new MutationObserver(mutations => {
            mutations.forEach(mutation => {
                if (mutation.addedNodes) {
                    Array.from(mutation.addedNodes)
                        .filter(node => node instanceof Element)
                        .forEach(this.processMarker.bind(this));
                }
            });
        }).observe(markerPane, {
            childList: true,
            subtree: true
        });
    },

    processMarker(node) {
        if (!(node instanceof Element) || !node.classList.contains('leaflet-marker-icon')) return;

        const placeMarker = node.querySelector('.place-marker');
        if (!placeMarker) return;

        const isActive = placeMarker.dataset.placeActive === 'true';
        
        if (!isActive) {
            node.classList.add('opacity-50', 'text-muted');
            node.style.opacity = '0.5';
            
            node.style.display = this.state.hideInactiveState ? 'none' : '';
            placeMarker.classList.toggle('d-none', this.state.hideInactiveState);
        }

        window.dispatchEvent(new CustomEvent('placeMarkerProcessed', {
            detail: {
                id: placeMarker.dataset.placeId || 'unknown',
                name: placeMarker.dataset.placeName || 'Unnamed',
                active: isActive,
                coordinates: [
                    parseFloat(placeMarker.dataset.placeLat),
                    parseFloat(placeMarker.dataset.placeLon)
                ]
            }
        }));
    }
};

document.addEventListener('DOMContentLoaded', () => {
    placesMapFoliumSystem.initialize();
}); 