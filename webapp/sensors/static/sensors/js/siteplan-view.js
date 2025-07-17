/**
 * Site Plan View System
 * Displays the site plan and location markers using Leaflet (read-only view)
 */

const sitePlanView = {
    // State
    state: {
        debug: false,
        map: null,
        imageOverlay: null,
        markers: new Map(), // slug -> L.Marker
        locations: new Map(), // slug -> location data
        imageBounds: null,
        initialized: false,
        placeSlug: null
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
        if (this.state.debug) {
            console.log(`Assigning icon '${selectedIcon}' to location '${locationName}' (index ${idx} of ${this.buildingIcons.length})`);
        }
        return selectedIcon;
    },

    // Create marker icon
    createIcon(isActive, iconType, locationName) {
        if (this.state.debug) {
            console.log(`Creating ${isActive ? 'active' : 'inactive'} icon for '${locationName}' with type: ${iconType}`);
        }
        return L.divIcon({
            className: 'location-marker', // Keep a base class for potential future styling
            iconSize: null,  // Let it size to content
            iconAnchor: null, // Will be set automatically
            html: `
                <div class="d-inline-flex flex-column align-items-center bg-${isActive ? 'primary' : 'secondary'} border border-2 border-white rounded-3 shadow-sm p-2">
                    <i class="bi bi-${iconType}${isActive ? '-fill' : ''} text-white fs-5"></i>
                    <div class="marker-label text-white small mt-1 text-nowrap">
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
            if (this.state.debug) {
                console.log('Site plan view already initialized');
            }
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
            if (this.state.debug) {
                console.log('Received siteplan update event:', event.detail);
                console.log('Current locations state:');
                console.table(Array.from(this.state.locations.values()));
                console.log('Current markers state:', Array.from(this.state.markers.entries()));
            }
            
            if (event.detail.locations) {
                this.updateLocations(event.detail.locations);
            }
        });

        return new Promise((resolve) => {
            const container = document.getElementById('siteplan-container');
            if (!container) {
                if (this.state.debug) {
                    console.log('No site plan container found - is the template including siteplan_card.html?');
                }
                this.state.initialized = true;
                resolve();
                return;
            }

            // Get the image URL and locations data
            const imageUrl = container.dataset.imageUrl;
            this.state.placeSlug = container.dataset.placeSlug;
            if (!imageUrl) {
                if (this.state.debug) {
                    console.log('No siteplan image configured for this place');
                }
                this.state.initialized = true;
                resolve();
                return;
            }

            // Debug logging
            if (this.state.debug) {
                console.log('Found container');
                console.log('Image URL:', imageUrl);
                console.log('Place Slug:', this.state.placeSlug);
            }

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
                    // Unescape the JSON string before parsing
                    const unescapedData = rawData.replace(/\\u(\w{4})/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)));
                    const locations = JSON.parse(unescapedData);
                    if (this.state.debug) {
                        console.log('Parsed locations:');
                        console.table(locations);
                    }
                    
                    // Store locations in state using string IDs
                    locations.forEach(location => {
                        this.state.locations.set(location.slug, location);
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
                    if (this.state.debug) {
                        console.error('Failed to parse locations data:', error);
                        console.error('Raw data was:', container.dataset.locations);
                    }
                }

                this.state.initialized = true;
                resolve();
            };
            img.onerror = () => {
                if (this.state.debug) {
                    console.log('No siteplan image available or failed to load:', imageUrl);
                }
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
            if (this.state.debug) {
                console.log('Map already initialized');
            }
            return;
        }

        // --- New Sizing Logic ---
        const siteplanWrapper = container.closest('.siteplan-wrapper');
        if (siteplanWrapper) {
            const imageWidth = this.state.imageBounds[1][1];
            const imageHeight = this.state.imageBounds[1][0];
            const aspectRatio = imageHeight / imageWidth;

            // 1. Get the available width from the wrapper.
            const availableWidth = siteplanWrapper.offsetWidth;

            // 2. Calculate the potential height based on aspect ratio.
            let calculatedHeight = availableWidth * aspectRatio;

            // 3. Get max height (e.g., 60% of viewport height).
            const maxHeight = window.innerHeight * 0.6;

            // 4. Set the final height, capped by the max height.
            const finalHeight = Math.min(calculatedHeight, maxHeight);

            // 5. Apply the height to the wrapper element.
            siteplanWrapper.style.height = `${finalHeight}px`;

            if (this.state.debug) {
                console.log('Site Plan Sizing:', {
                    availableWidth,
                    aspectRatio,
                    calculatedHeight,
                    maxHeight,
                    finalHeight
                });
            }
        }
        // --- End New Sizing Logic ---

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
                if (siteplanWrapper) {
                    siteplanWrapper.classList.add('loaded');
                }
            });

        // The aspect ratio is now handled by the explicit height calculation above
        
        // Initial fit
        this.fitMapPerfectly();

        // Create a ResizeObserver for the wrapper
        const resizeObserver = new ResizeObserver(() => {
            requestAnimationFrame(() => this.fitMapPerfectly());
        });

        // Observe both wrapper and container
        if (siteplanWrapper) resizeObserver.observe(siteplanWrapper);
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
        
        if (this.state.debug) {
            console.log('Available icons after shuffle:');
            console.table(this.buildingIcons);
        }
        
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
                if (this.state.debug) {
                    console.log(`Marker clicked for location ${location.slug}`);
                }
                if (this.state.placeSlug) {
                    window.location.href = `/${this.state.placeSlug}/location/${location.slug}/`;
                } else {
                    if (this.state.debug) {
                        console.error('Cannot navigate to location detail, place slug not found.');
                    }
                }
            });

            // Add to map and store reference
            marker.addTo(this.state.map);

            // Storing for later reference
            marker.iconType = iconType;
            this.state.markers.set(location.slug, marker);
        });
    },

    // Update markers visibility based on hide-inactive state
    updateMarkersVisibility(hideInactive) {
        this.state.markers.forEach((marker, slug) => {
            const location = this.state.locations.get(slug);

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
        if (this.state.debug) {
            console.log('Starting updateLocations with:', updates);
        }

        let needsVisibilityCheck = false;

        // The 'updates' object contains key-value pairs of { slug: locationData }
        Object.entries(updates).forEach(([slug, updatedData]) => {
            const existingLocation = this.state.locations.get(slug);
            const existingMarker = this.state.markers.get(slug);

            if (existingLocation && existingMarker) {
                // Merge the updated data into our local state
                const newLocationData = { ...existingLocation, ...updatedData };
                this.state.locations.set(slug, newLocationData);

                // Update the marker's visual representation
                const coords = this.percentToImageCoords(newLocationData.x_pos, newLocationData.y_pos);
                const icon = this.createIcon(newLocationData.is_active, existingMarker.iconType, newLocationData.name);
                
                existingMarker.setLatLng(coords);
                existingMarker.setIcon(icon);

                // Also update the popup content
                existingMarker.setPopupContent(this.createMarkerPopup(newLocationData));
                
                if (this.state.debug) {
                    console.log(`Updated location ${slug} with new data:`, newLocationData);
                }
                
                needsVisibilityCheck = true;
            } else {
                if (this.state.debug) {
                    console.warn(`Location or marker with slug ${slug} not found, skipping update.`);
                }
            }
        });

        if (needsVisibilityCheck) {
            // After all updates, re-evaluate visibility based on the current switch state
            const locationSwitch = document.querySelector('.hideInactive-switch[data-model="location"]');
            this.updateMarkersVisibility(locationSwitch ? locationSwitch.checked : true);
        }
    }
};

// Initialize when DOM is loaded and expose to window
document.addEventListener('DOMContentLoaded', () => {
    // Only initialize if not already initialized
    if (!sitePlanView.state.initialized) {
        sitePlanView.initialize().then(() => {
            if (sitePlanView.state.debug) {
                console.log('Site plan view initialization complete');
            }
        });
    }
});

// Export for use in other modules
window.sitePlanView = sitePlanView; 