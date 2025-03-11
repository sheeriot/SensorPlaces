/**
 * Place Map Popout System
 * 
 * Manages the popout map functionality for places view
 * 
 * Configuration:
 * -------------
 * To enable debugging, set debug: true in mapPopoutConfig below
 * Debug mode will:
 * - Show initialization sequence logs
 * - Log map state changes
 * - Show detailed modal events
 */

// System Configuration
const mapPopoutConfig = {
    debug: false,           // Set to true to enable debug mode
    logMapEvents: true,    // Log map view changes and updates
    logModalEvents: true   // Log modal open/close events
};

// Place Map Popout System
const placeMapPopout = {
    map: null,
    metadata: {
        zoom_active: null,
        zoom_all: null,
        center_active: null,
        center_all: null
    },

    initialize() {
        if (mapPopoutConfig.debug) {
            console.group('Place Map Popout System');
            console.log("Initializing popout map system");
        }
        
        // First check if we should initialize on this page
        const mapTrigger = document.getElementById('openPlaceMap');
        if (!mapTrigger || !mapTrigger.hasAttribute('data-place-map-popout')) {
            if (mapPopoutConfig.debug) {
                console.log("No popout map to initialize on this page");
                console.groupEnd();
            }
            return;
        }

        // Get map element
        const mapContainer = document.getElementById('placeMapContainer');
        if (!mapContainer) {
            if (mapPopoutConfig.debug) {
                console.log("No popout map container found");
                console.groupEnd();
            }
            return;
        }

        if (mapPopoutConfig.debug) {
            console.log("Found popout map container");
        }
        
        this.setupMap(mapContainer);
        this.setupEventListeners(mapTrigger);
        
        if (mapPopoutConfig.debug) {
            console.groupEnd();
        }
    },

    setupMap(container) {
        if (mapPopoutConfig.debug) {
            console.group('Setting up popout map');
        }

        // Get place data from container
        const lat = parseFloat(container.dataset.placeLat);
        const lon = parseFloat(container.dataset.placeLon);
        const name = container.dataset.placeName;
        const placeId = container.dataset.placeId;
        const isActive = container.dataset.placeActive === 'true';

        if (!lat || !lon) {
            console.error("Invalid coordinates for map");
            if (mapPopoutConfig.debug) console.groupEnd();
            return;
        }

        if (mapPopoutConfig.debug) {
            console.debug('Place data:', {
                name,
                placeId,
                lat,
                lon,
                isActive
            });
        }

        // Initialize the map
        this.map = L.map(container.id).setView([lat, lon], 13);
        
        // Add the tile layer
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(this.map);

        // Create marker with custom options
        const marker = L.marker([lat, lon], {
            opacity: isActive ? 1 : 0.5,
            title: name
        });

        // Add data attributes to marker element after it's added to map
        marker.on('add', function(e) {
            const markerElement = e.target.getElement();
            if (markerElement) {
                markerElement.dataset.placeId = placeId;
                markerElement.dataset.placeActive = isActive.toString();
                if (!isActive) {
                    markerElement.style.opacity = '0.5';
                }
            }
        });

        // Add marker to map
        marker.addTo(this.map)
            .bindPopup(`
                <div class="marker-popup">
                    <h6 class="mb-1">${name}</h6>
                    <div class="text-muted small">
                        <div>Lat: ${lat}</div>
                        <div>Lon: ${lon}</div>
                        <div class="mt-1">
                            Status: <span class="badge ${isActive ? 'bg-success' : 'bg-danger'}">
                                ${isActive ? 'Active' : 'inactive'}
                            </span>
                        </div>
                    </div>
                </div>
            `);

        // Store initial view
        this.metadata.center_active = [lat, lon];
        this.metadata.zoom_active = 13;

        if (mapPopoutConfig.debug) {
            console.debug('Map setup complete');
            console.groupEnd();
        }
    },

    setupEventListeners(trigger) {
        // Handle modal events to resize map
        const modal = document.getElementById('placeMapModal');
        if (!modal) return;

        modal.addEventListener('shown.bs.modal', () => {
            if (this.map) {
                this.map.invalidateSize();
                if (this.metadata.center_active && this.metadata.zoom_active) {
                    this.map.setView(this.metadata.center_active, this.metadata.zoom_active);
                }
            }
        });

        // Clean up on modal hide
        modal.addEventListener('hide.bs.modal', () => {
            // Store current view
            if (this.map) {
                this.metadata.center_active = this.map.getCenter();
                this.metadata.zoom_active = this.map.getZoom();
            }
        });
    }
};

// Initialize place map popout system when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    if (mapPopoutConfig.debug) {
        console.group('Place Map Popout Initialization');
    }
    
    const openMapBtn = document.getElementById('openPlaceMap');
    if (!openMapBtn) {
        if (mapPopoutConfig.debug) {
            console.log('No map trigger button found on this page');
            console.groupEnd();
        }
        return;
    }

    if (!openMapBtn.hasAttribute('data-place-map-popout')) {
        if (mapPopoutConfig.debug) {
            console.log('Popout map initialization not requested on this page');
            console.groupEnd();
        }
        return;
    }

    if (mapPopoutConfig.debug) {
        console.log('Found map trigger button with initialization flag');
    }
    
    placeMapPopout.initialize();
    
    if (mapPopoutConfig.debug) {
        console.groupEnd();
    }
}); 