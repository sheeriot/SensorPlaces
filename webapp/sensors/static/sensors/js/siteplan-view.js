/**
 * Site Plan View System
 * Displays the site plan and location markers using Leaflet (read-only view)
 */

const sitePlanView = {
    // State
    state: {
        map: null,
        imageOverlay: null,
        markers: new Map(), // id -> L.Marker
        locations: new Map(), // id -> location data
        imageBounds: null,
        initialized: false,
        debug: true,  // Add debug flag
        placeSlug: null
    },

    // Debug logging helper
    log(...args) {
        if (this.state.debug) {
            console.log(...args);
        }
    },

    error(...args) {
        if (this.state.debug) {
            console.error(...args);
        }
    },

    // Helper Methods
    percentToImageCoords(xPercent, yPercent) {
        const bounds = this.state.imageBounds;
        const imageX = (xPercent / 100) * bounds[1][1];
        const imageY = (yPercent / 100) * bounds[1][0];
        return [imageY, imageX];
    },

    // Available building icons
    buildingIcons: [
        'building',
        'house',
        'bag-plus',
        'door-closed',
        'buildings',
        'house-heart',
        'hospital'
    ],

    // Get random building icon
    getRandomIcon(locationName) {
        const idx = Math.floor(Math.random() * this.buildingIcons.length);
        const selectedIcon = this.buildingIcons[idx];
        this.log(`Assigning icon '${selectedIcon}' to location '${locationName}' (index ${idx} of ${this.buildingIcons.length})`);
        return selectedIcon;
    },

    // Create marker icon
    createIcon(isActive, iconType, locationName) {
        this.log(`Creating ${isActive ? 'active' : 'inactive'} icon for '${locationName}' with type: ${iconType}`);
        return L.divIcon({
            className: `location-marker bg-${isActive ? 'primary' : 'secondary'} border border-2 border-white rounded-3 shadow-sm p-2`,
            iconSize: null,  // Let it size to content
            iconAnchor: null, // Will be set automatically
            html: `
                <div class="d-flex flex-column align-items-center">
                    <i class="bi bi-${iconType}${isActive ? '-fill' : ''} text-white fs-5"></i>
                    <div class="marker-label text-white small mt-1">
                        ${locationName}
                    </div>
                </div>
            `
        });
    },

    // Create marker popup
    createMarkerPopup(location) {
        return `
            <div class="p-2">
                <h6 class="mb-1">${location.name}</h6>
                ${location.description ? `<p class="mb-1 small text-muted">${location.description}</p>` : ''}
                ${location.devices_active_count ? `
                    <div class="text-success small">
                        <i class="bi bi-circle-fill me-1"></i>
                        ${location.devices_active_count} active device${location.devices_active_count !== 1 ? 's' : ''}
                    </div>
                ` : ''}
            </div>
        `;
    },

    // Initialize the view
    initialize() {
        // Prevent multiple initializations
        if (this.state.initialized) {
            this.log('Site plan view already initialized');
            return Promise.resolve();
        }

        // Listen for hide-inactive state changes
        window.addEventListener('hideInactiveStateChanged', (event) => {
            if (event.detail.model === 'location') {
                this.updateMarkersVisibility(event.detail.hideInactive);
            }
        });

        // Listen for siteplan updates
        window.addEventListener('siteplan-update', (event) => {
            this.log('Received siteplan update event:', event.detail);
            this.log('Current locations state:', Array.from(this.state.locations.entries()));
            this.log('Current markers state:', Array.from(this.state.markers.entries()));
            
            if (event.detail.locations) {
                this.updateLocations(event.detail.locations);
            }
        });

        return new Promise((resolve) => {
            const container = document.getElementById('siteplan-container');
            if (!container) {
                this.log('No site plan container found - is the template including siteplan_card.html?');
                this.state.initialized = true;
                resolve();
                return;
            }

            // Get the image URL and locations data
            const imageUrl = container.dataset.imageUrl;
            this.state.placeSlug = container.dataset.placeSlug;
            if (!imageUrl) {
                this.log('No siteplan image configured for this place');
                this.state.initialized = true;
                resolve();
                return;
            }

            // Debug logging
            this.log('Found container:', container);
            this.log('Image URL:', imageUrl);
            this.log('Place Slug:', this.state.placeSlug);
            this.log('Locations data:', container.dataset.locations);

            // Create a temporary image to get dimensions
            const img = new Image();
            img.onload = () => {
                // Store image bounds
                this.state.imageBounds = [[0, 0], [img.height, img.width]];
                
                // Initialize the map
                this.initializeMap(container, imageUrl);
                
                // Add markers if we have location data
                try {
                    const rawData = container.dataset.locations || '[]';
                    this.log('Attempting to parse:', rawData);
                    // Unescape the JSON string before parsing
                    const unescapedData = rawData.replace(/\\u(\w{4})/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)));
                    this.log('Unescaped data:', unescapedData);
                    const locations = JSON.parse(unescapedData);
                    this.log('Parsed locations:', locations);
                    
                    // Store locations in state
                    locations.forEach(location => {
                        this.state.locations.set(location.id, location);
                    });
                    
                    this.addMarkers(locations);

                    // Set initial visibility based on switch state
                    const locationSwitch = document.querySelector('.hideInactive-switch[data-model="location"]');
                    if (locationSwitch) {
                        // If switch exists, use its state
                        this.updateMarkersVisibility(locationSwitch.checked);
                    } else {
                        // If no switch exists, hide inactive locations by default
                        this.updateMarkersVisibility(true);
                    }
                } catch (error) {
                    this.error('Failed to parse locations data:', error);
                    this.error('Raw data was:', container.dataset.locations);
                }

                this.state.initialized = true;
                resolve();
            };
            img.onerror = () => {
                this.log('No siteplan image available or failed to load:', imageUrl);
                this.state.initialized = true;
                resolve();
            };
            img.src = imageUrl;
        });
    },

    // Initialize Leaflet map
    initializeMap(container, imageUrl) {
        // Check if map is already initialized
        if (this.state.map) {
            this.log('Map already initialized');
            return;
        }

        // Get wrapper for loading state
        const wrapper = container.closest('.siteplan-wrapper');

        // Initialize the map with minimal controls
        this.state.map = L.map(container, {
            crs: L.CRS.Simple,
            zoomControl: false,
            dragging: false,
            touchZoom: false,
            scrollWheelZoom: false,
            doubleClickZoom: false,
            boxZoom: false,
            keyboard: false,
            attributionControl: false,
            zoomSnap: 0,
            zoomDelta: 0,
            minZoom: -2,         // Match editor settings
            maxZoom: 2          // Match editor settings
        });

        // Add image overlay with loading handler
        this.state.imageOverlay = L.imageOverlay(imageUrl, this.state.imageBounds)
            .addTo(this.state.map)
            .on('load', () => {
                // Mark as loaded once image is ready
                if (wrapper) {
                    wrapper.classList.add('loaded');
                }
            });

        if (wrapper) {
            const aspectRatio = (this.state.imageBounds[1][0] / this.state.imageBounds[1][1]) * 100;
            wrapper.style.paddingBottom = `${aspectRatio}%`;
            
            // Clear any existing styles that might interfere
            wrapper.style.height = '';
            wrapper.style.minHeight = '';
            wrapper.style.maxHeight = '';
            container.style.position = 'absolute';
        }

        // Initial fit
        this.fitMapPerfectly();

        // Create a ResizeObserver for the wrapper
        const resizeObserver = new ResizeObserver(() => {
            requestAnimationFrame(() => this.fitMapPerfectly());
        });

        // Observe both wrapper and container
        if (wrapper) resizeObserver.observe(wrapper);
        resizeObserver.observe(container);

        // Also handle window resize
        window.addEventListener('resize', () => {
            requestAnimationFrame(() => this.fitMapPerfectly());
        });
    },

    // Update fitMapPerfectly method to match editor's implementation
    fitMapPerfectly() {
        if (!this.state.map || !this.state.imageBounds) return;
        
        // Force a size update
        this.state.map.invalidateSize();
        
        // Fit bounds exactly
        this.state.map.fitBounds(this.state.imageBounds, {
            animate: false,
            padding: [0, 0]
        });
    },

    // Add markers to the map
    addMarkers(locations) {
        if (!this.state.map || !this.state.imageBounds) return;

        // Shuffle available icons before assigning
        this.buildingIcons = this.buildingIcons
            .map(value => ({ value, sort: Math.random() }))
            .sort((a, b) => a.sort - b.sort)
            .map(({ value }) => value);
        
        this.log('Available icons after shuffle:', this.buildingIcons);
        
        locations.forEach(location => {
            const coords = this.percentToImageCoords(location.x_pos, location.y_pos);
            
            // Get random icon type for this location
            const iconType = this.getRandomIcon(location.name);
            
            // Create marker with popup
            const marker = L.marker(coords, {
                icon: this.createIcon(location.is_active, iconType, location.name),
                title: location.name
            });

            // Add popup with location info
            marker.bindPopup(this.createMarkerPopup(location), {
                offset: [0, -10],
                closeButton: false,
                className: 'location-popup',
                autoPan: false,
                autoPanPadding: [50, 50],
                keepInView: true
            });

            // Show popup on hover
            marker.on('mouseover', function() {
                this.openPopup();
            });
            
            marker.on('mouseout', function() {
                this.closePopup();
            });

            // Add click event to scroll to the location
            marker.on('click', () => {
                this.log(`Marker clicked for location ${location.id}`);
                if (this.state.placeSlug) {
                    window.location.href = `/${this.state.placeSlug}/location/${location.id}/`;
                } else {
                    this.error('Cannot navigate to location detail, place slug not found.');
                }
            });

            // Add to map and store reference
            marker.addTo(this.state.map);

            // Storing for later reference
            marker.iconType = iconType;
            this.state.markers.set(location.id, marker);
        });
    },

    // Update markers visibility based on hide-inactive state
    updateMarkersVisibility(hideInactive) {
        this.state.markers.forEach((marker, id) => {
            const location = this.state.locations.get(id);

            // A location might not (yet) exist for a marker during updates, so we check.
            if (location && !location.is_active) {
                const element = marker.getElement();
                if (element) {
                    element.classList.toggle('d-none', hideInactive);
                }
            }
        });
    },

    updateLocations(updates) {
        this.log('Starting updateLocations with:', updates);
        this.log('Current locations state:', Array.from(this.state.locations.entries()));
        this.log('Current markers state:', Array.from(this.state.markers.entries()));
        
        let changed = false;
        
        // Update locations that already exist
        Object.entries(updates).forEach(([id, location]) => {
            if (this.state.locations.has(id)) {
                // Update local data store
                this.state.locations.set(id, { ...this.state.locations.get(id), ...location });
                const updatedLocation = this.state.locations.get(id);

                // Update marker on map
                const existingMarker = this.state.markers.get(id);
                if (existingMarker) {
                    const coords = this.percentToImageCoords(updatedLocation.x_pos, updatedLocation.y_pos);
                    const icon = this.createIcon(updatedLocation.is_active, existingMarker.iconType, updatedLocation.name);
                    existingMarker.setLatLng(coords);
                    existingMarker.setIcon(icon);
                    this.log(`Updated marker for ${updatedLocation.name}`);
                }
            } else {
                // If location is new, add it
                this.addMarkers([location]);
                this.log(`Added new marker for ${location.name}`);
            }
        });

        // Remove markers for deleted locations
        const updatedIds = new Set(Object.keys(updates).map(id => parseInt(id, 10)));
        const currentIds = Array.from(this.state.locations.keys());
        const deletedIds = currentIds.filter(id => !updatedIds.has(id));

        deletedIds.forEach(id => {
            const marker = this.state.markers.get(id);
            if (marker) {
                marker.remove();
                this.state.markers.delete(id);
                this.state.locations.delete(id);
                this.log(`Removed marker for deleted location ID: ${id}`);
            }
        });
        
        if (changed) {
            // Update visibility based on current switch state
            const locationSwitch = document.querySelector('.hideInactive-switch[data-model="location"]');
            if (locationSwitch && locationSwitch.checked) {
                this.updateMarkersVisibility(true);
            }
            
            this.log('Final locations state:', Array.from(this.state.locations.entries()));
            this.log('Final markers state:', Array.from(this.state.markers.entries()));
        }
    }
};

// Initialize when DOM is loaded and expose to window
document.addEventListener('DOMContentLoaded', () => {
    // Only initialize if not already initialized
    if (!sitePlanView.state.initialized) {
        sitePlanView.initialize().then(() => {
            sitePlanView.log('Site plan view initialization complete');
        });
    }
});

// Export for use in other modules
window.sitePlanView = sitePlanView; 