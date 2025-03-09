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
        imageBounds: null,
        initialized: false
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
        console.log(`Assigning icon '${selectedIcon}' to location '${locationName}' (index ${idx} of ${this.buildingIcons.length})`);
        return selectedIcon;
    },

    // Create marker icon
    createIcon(isActive, iconType, locationName) {
        console.log(`Creating ${isActive ? 'active' : 'inactive'} icon for '${locationName}' with type: ${iconType}`);
        return L.divIcon({
            className: `location-marker bg-${isActive ? 'primary' : 'secondary'} border border-2 border-white rounded-3 shadow-sm d-flex align-items-center justify-content-center p-1`,
            iconSize: [48, 36],
            iconAnchor: [24, 18],
            html: `
                <div class="d-flex flex-column align-items-center">
                    <i class="bi bi-${iconType}${isActive ? '-fill' : ''} text-white fs-5"></i>
                </div>
            `
        });
    },

    // Initialize the view
    initialize() {
        // Prevent multiple initializations
        if (this.state.initialized) {
            console.log('Site plan view already initialized');
            return Promise.resolve();
        }

        // Listen for hide-inactive state changes
        window.addEventListener('hideInactiveStateChanged', (event) => {
            if (event.detail.model === 'location') {
                this.updateMarkersVisibility(event.detail.hideInactive);
            }
        });

        return new Promise((resolve) => {
            const container = document.getElementById('site-plan-container');
            if (!container) {
                console.log('No site plan container found');
                this.state.initialized = true;
                resolve();
                return;
            }

            // Get the image URL and locations data
            const imageUrl = container.dataset.imageUrl;
            if (!imageUrl) {
                console.log('No image URL found');
                this.state.initialized = true;
                resolve();
                return;
            }

            // Debug: Log the raw locations data
            console.log('Raw locations data:', container.dataset.locations);

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
                    console.log('Attempting to parse:', rawData);
                    // Unescape the JSON string before parsing
                    const unescapedData = rawData.replace(/\\u(\w{4})/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)));
                    console.log('Unescaped data:', unescapedData);
                    const locations = JSON.parse(unescapedData);
                    console.log('Parsed locations:', locations);
                    this.addMarkers(locations);

                    // Set initial visibility based on switch state
                    const locationSwitch = document.querySelector('.hideInactive-switch[data-model="location"]');
                    if (locationSwitch && locationSwitch.checked) {
                        this.updateMarkersVisibility(true);
                    }
                } catch (error) {
                    console.error('Failed to parse locations data:', error);
                    console.error('Raw data was:', container.dataset.locations);
                }

                this.state.initialized = true;
                resolve();
            };
            img.onerror = () => {
                console.error('Failed to load site plan image');
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
            console.log('Map already initialized');
            return;
        }

        // Initialize the map
        this.state.map = L.map(container, {
            crs: L.CRS.Simple,
            zoomControl: false,
            dragging: false,
            touchZoom: false,
            scrollWheelZoom: false,
            doubleClickZoom: false,
            boxZoom: false,
            keyboard: false
        });

        // Add image overlay
        this.state.imageOverlay = L.imageOverlay(imageUrl, this.state.imageBounds).addTo(this.state.map);

        // Fit map to bounds
        this.state.map.fitBounds(this.state.imageBounds);
    },

    // Add markers to the map
    addMarkers(locations) {
        if (!this.state.map || !this.state.imageBounds) return;

        const bounds = this.state.imageBounds;
        
        // Shuffle the buildingIcons array before starting
        this.buildingIcons = this.buildingIcons
            .map(value => ({ value, sort: Math.random() }))
            .sort((a, b) => a.sort - b.sort)
            .map(({ value }) => value);
        
        console.log('Available icons after shuffle:', this.buildingIcons);
        
        locations.forEach(location => {
            // Convert percentage coordinates to image coordinates
            const imageX = (location.x / 100) * bounds[1][1];
            const imageY = (location.y / 100) * bounds[1][0];

            // Get random icon type for this location
            const iconType = this.getRandomIcon(location.name);

            // Create marker with popup
            const marker = L.marker([imageY, imageX], {
                icon: this.createIcon(location.is_active, iconType, location.name),
                title: location.name
            });

            // Add popup with location info
            marker.bindPopup(`
                <div class="p-2 ${!location.is_active ? 'text-muted' : ''}">
                    <h6 class="mb-1">${location.name}</h6>
                    ${location.active_devices_count > 0 ? `
                        <div class="text-muted small">
                            ${location.active_devices_count} active device${location.active_devices_count !== 1 ? 's' : ''}
                        </div>
                    ` : ''}
                    ${!location.is_active ? '<div class="small">(Inactive)</div>' : ''}
                </div>
            `);

            // Add to map and store reference with active state
            marker.addTo(this.state.map);
            this.state.markers.set(location.id, {
                marker,
                is_active: location.is_active,
                iconType // Store the icon type for visibility updates
            });
        });
    },

    // Update markers visibility based on hide-inactive state
    updateMarkersVisibility(hideInactive) {
        this.state.markers.forEach(({marker, is_active, iconType}) => {
            if (!is_active) {
                const element = marker.getElement();
                if (element) {
                    element.classList.toggle('d-none', hideInactive);
                }
            }
        });
    }
};

// Initialize when DOM is loaded and expose to window
document.addEventListener('DOMContentLoaded', () => {
    // Only initialize if not already initialized
    if (!sitePlanView.state.initialized) {
        sitePlanView.initialize().then(() => {
            console.log('Site plan view initialization complete');
        });
    }
});

// Export for use in other modules
window.sitePlanView = sitePlanView; 