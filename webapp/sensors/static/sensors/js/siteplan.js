/**
 * Site Plan View & Editor System
 * Displays the site plan and location markers using Leaflet
 */
console.log('[siteplan.js] --- SCRIPT LOADED ---');

const sitePlanModule = (function () {
    console.log('[siteplan.js] IIFE executing.');
    const scriptConfig = {
        debug: false,
        version: '{{ APP_VERSION }}'
    };
    console.log('[siteplan.js] scriptConfig:', scriptConfig);

    const state = {
        maps: {},
        locations: [],
        markers: new Map(),
        editorMap: null,
        imageOverlay: null,
        imageBounds: null,
        isDirty: false
    };

    const config = {
        active_icons: [
            'bi-geo-alt-fill', 'bi-wifi', 'bi-router-fill', 'bi-broadcast',
            'bi-camera-video-fill', 'bi-mic-fill'
        ],
        inactive_icon: 'bi-geo-alt'
    };

    function createMap(containerId, locationsDataId, isModal) {
        const locationsDataEl = document.getElementById(locationsDataId);
        if (!locationsDataEl) {
            return;
        }
        const imageUrl = document.getElementById(containerId).dataset.imageUrl;
        if (!imageUrl) {
            return;
        }
        const img = new Image();
        img.onload = function () {
            createMapFromImage(img, containerId, locationsDataId, imageUrl, isModal);
        };
        img.onerror = function () {
            console.error(`[createMap] >>> img.onerror has fired for ${imageUrl}. Image failed to load.`);
        };
        img.src = imageUrl;
    }

    function initializeMainView() {
        const siteplanContainer = document.getElementById('siteplan-container-main');
        if (siteplanContainer) {
            createMap('siteplan-container-main', 'locations-data-main', false);
        } else {
            console.error('[initializeMainView] FAILED to find main page container #siteplan-container-main!');
        }
    }

    function initializeModalView() {
        const siteplanContainer = document.getElementById('siteplan-container-modal');
        if (siteplanContainer) {
            createMap('siteplan-container-modal', 'locations-data-modal', true);
        } else {
            console.error('[initializeModalView] FAILED to find modal container #siteplan-container-modal!');
        }
    }

    function createMapFromImage(img, containerId, locationsDataId, imageUrl, isModal) {
        const container = document.getElementById(containerId);
        if (!container) {
            console.error(`[createMapFromImage] Container element #${containerId} not found! Cannot create map.`);
            return;
        }

        const imageAspectRatio = img.naturalHeight / img.naturalWidth;
        container.style.paddingTop = '0';

        const siteplanWrapper = container.closest('.siteplan-wrapper');
        const calculatedHeight = container.offsetWidth * imageAspectRatio;
        if (siteplanWrapper) {
            siteplanWrapper.style.height = `${calculatedHeight}px`;
        } else {
            container.style.height = `${calculatedHeight}px`;
        }

        if (container._leaflet_id) {
            const existingMap = L.DomUtil.getMap(container);
            if (existingMap) existingMap.remove();
        }

        const bounds = [[0, 0], [img.naturalHeight, img.naturalWidth]];
        const map = L.map(containerId, {
            crs: L.CRS.Simple,
            minZoom: -5,
            maxZoom: 5,
            maxBounds: bounds,
            maxBoundsViscosity: 1.0
        });
        L.imageOverlay(imageUrl, bounds).addTo(map);

        if (siteplanWrapper) {
            siteplanWrapper.classList.add('loaded');
        }

        const locationsDataEl = document.getElementById(locationsDataId);
        let locations;
        try {
            locations = JSON.parse(locationsDataEl.textContent);
            if (!Array.isArray(locations)) throw new Error("Parsed data is not an array.");
        } catch (e) {
            console.error(`Failed to parse locations from #${locationsDataId}:`, e);
            map.fitBounds(bounds);
            return;
        }

        const markerBounds = [];
        locations.forEach(location => {
            if (location.x_pos === null || location.y_pos === null) return;
            const pixelY = (location.y_pos / 100) * img.naturalHeight;
            const pixelX = (location.x_pos / 100) * img.naturalWidth;
            const icon = createIcon(location);
            const marker = L.marker([pixelY, pixelX], { icon }).addTo(map);
            marker.bindPopup(createMarkerPopup(location), { offset: L.point(0, -30) });
            marker.bindTooltip(location.name, {
                permanent: true,
                direction: 'bottom',
                offset: [0, 20],
                className: 'location-label'
            });
            markerBounds.push([pixelY, pixelX]);
        });

        map.fitBounds(bounds);

        state.maps[containerId] = map;
        state.locations = locations;
    }

    function createMarkerPopup(location) {
        let deviceCountText = `${location.devices_active_count} device(s)`;
        if (location.devices_total_count && location.devices_total_count > location.devices_active_count) {
            deviceCountText = `${location.devices_active_count} of ${location.devices_total_count} devices active`;
        }
        return `
            <div class="siteplan-popup">
                <a href="${location.url || '#'}" class="text-decoration-none">
                    <h6 class="mb-1">${location.name}</h6>
                </a>
                <p class="mb-0 small text-muted">${deviceCountText}</p>
            </div>
        `;
    }

    function getRandomIcon() {
        return config.active_icons[Math.floor(Math.random() * config.active_icons.length)];
    }

    function createIcon(location) {
        const iconClass = location.is_active && location.devices_active_count > 0 ? getRandomIcon() : config.inactive_icon;
        return L.divIcon({
            html: `<i class="bi ${iconClass} fs-5"></i>`,
            className: `location-marker ${location.is_active && location.devices_active_count > 0 ? 'active' : 'inactive'}`,
            iconSize: [40, 40],
            iconAnchor: [20, 20],
            popupAnchor: [0, -20]
        });
    }

    const sitePlanSystem = {
        DEFAULT_ZOOM: 2,
        MIN_ZOOM: 0,
        MAX_ZOOM: 4,

        state: state,

        get saveButton() { return document.getElementById('siteplan-save'); },
        get resetButton() { return document.getElementById('siteplan-editor-reset'); },

        initializeEditor(modalEl) {
            this.logDebug('initialization', 'Site plan editor initializing inside modal.');

            const container = modalEl.querySelector('#siteplan-editor-map');
            const viewContainer = document.getElementById('siteplan-container-main');

            if (!container || !viewContainer) {
                this.logDebug('error', 'Editor or view container not found');
                return;
            }

            const imageUrl = viewContainer.dataset.imageUrl;
            if (!imageUrl) {
                this.logDebug('error', 'Image URL not found on view container');
                return;
            }

            const saveButton = modalEl.querySelector('#siteplan-save');
            if (saveButton) {
                saveButton.addEventListener('click', () => this.saveChanges());
            }

            const resetButton = modalEl.querySelector('#siteplan-editor-reset');
            if (resetButton) {
                resetButton.addEventListener('click', () => this.resetView());
            }

            const img = new Image();
            img.onload = () => {
                this.state.imageBounds = [[0, 0], [img.height, img.width]];
                this.initializeEditorMap(container, imageUrl);
            };
            img.src = imageUrl;

            $('#mapplan-modal').one('hidden.bs.modal', () => this.cleanupEditor());
        },

        cleanupEditor() {
            if (this.state.editorMap) {
                this.state.editorMap.off();
                this.state.markers.forEach(({marker}) => {
                    if (marker) {
                        marker.off();
                        marker.remove();
                    }
                });

                this.state.markers.clear();
                this.state.isDirty = false;

                this.state.editorMap.remove();
                this.state.editorMap = null;
                this.state.imageOverlay = null;
                this.state.imageBounds = null;

                this.logDebug('initialization', 'Editor cleaned up');
            }
        },

        setupEditor() {
            const container = this.editorContainer;
            const imageUrl = this.viewContainer.dataset.imageUrl;

            if (!container || !imageUrl) return;

            container.dataset.editorReady = 'false';

            this.logDebug('initialization', 'Initial container dimensions:', {
                width: container.offsetWidth,
                height: container.offsetHeight,
                style: container.style.cssText
            });

            const img = new Image();
            img.onload = () => {
                const aspectRatio = (img.height / img.width) * 100;
                container.style.paddingBottom = `${aspectRatio}%`;

                this.state.imageBounds = [[0, 0], [img.height, img.width]];

                setTimeout(() => {
                    this.logDebug('initialization', 'Container dimensions after modal transition:', {
                        width: container.offsetWidth,
                        height: container.offsetHeight,
                        style: container.style.cssText
                    });

                    this.initializeEditorMap(container, imageUrl);
                }, 300);
            };
            img.src = imageUrl;
        },

        initializeEditorMap(container, imageUrl) {
            const siteplanWrapper = container.closest('.siteplan-wrapper');
            if (siteplanWrapper) {
                const imageWidth = this.state.imageBounds[1][1];
                const imageHeight = this.state.imageBounds[1][0];
                const aspectRatio = imageHeight / imageWidth;
                const availableWidth = siteplanWrapper.offsetWidth;
                let calculatedHeight = availableWidth * aspectRatio;
                const maxHeight = window.innerHeight * 0.8;
                const finalHeight = calculatedHeight;
                siteplanWrapper.style.height = `${finalHeight}px`;
            }

            this.state.editorMap = L.map(container, {
                crs: L.CRS.Simple,
                zoomControl: false,
                dragging: true,
                touchZoom: false,
                scrollWheelZoom: false,
                doubleClickZoom: false,
                boxZoom: false,
                keyboard: false,
                attributionControl: false,
                zoomSnap: 0,
                zoomDelta: 0,
                minZoom: -2,
                maxZoom: 2
            });

            const bounds = this.state.imageBounds;
            this.state.imageOverlay = L.imageOverlay(imageUrl, bounds)
                .addTo(this.state.editorMap)
                .on('load', () => {
                    if (siteplanWrapper) {
                        siteplanWrapper.classList.add('loaded');
                    }
                    container.dataset.editorReady = 'true';
                });

            this.fitMapPerfectly();

            const resizeObserver = new ResizeObserver(() => {
                requestAnimationFrame(() => this.fitMapPerfectly());
            });

            if (siteplanWrapper) resizeObserver.observe(siteplanWrapper);
            resizeObserver.observe(container);

            window.addEventListener('resize', () => {
                requestAnimationFrame(() => this.fitMapPerfectly());
            });

            this.addEditorMarkers();
            this.logDebug('success', 'Editor map fully initialized and ready');
        },

        addEditorMarkers() {
            try {
                const locations = Array.from(window.sitePlanView.state.locations);

                if (!locations || locations.length === 0) {
                    this.logDebug('warning', 'No locations found in sitePlanView state after filtering.');
                    return;
                }

                this.logDebug('markers', `Loading ${locations.length} markers from sitePlanView state.`);

                locations.forEach(location => {
                    const coords = this.percentToImageCoords(location.x_pos, location.y_pos);

                    const viewMarker = state.markers.get(location.slug);
                    const iconType = viewMarker ? viewMarker.iconType : getRandomIcon(location.name);

                    const icon = this.createEditorIcon(location.is_active, iconType, location.name);

                    const marker = L.marker(coords, {
                        icon: icon,
                        title: location.name,
                        draggable: true
                    });

                    marker.bindPopup(this.createEditorMarkerPopup(location), {
                        offset: [0, -10],
                        closeButton: false,
                        className: 'location-popup',
                        autoPan: false,
                        autoPanPadding: [50, 50],
                        keepInView: true
                    });

                    marker.on('mouseover', function() {
                        this.openPopup();
                    });

                    marker.on('mouseout', function() {
                        this.closePopup();
                    });

                    let isDragging = false;
                    let originalPosition = null;

                    marker.on('mousedown', function(e) {
                        isDragging = false;
                        originalPosition = marker.getLatLng();
                        marker.getElement().classList.add('dragging');
                    });

                    marker.on('dragstart', function(e) {
                        isDragging = true;
                        this.closePopup();
                        sitePlanSystem.state.isDirty = true;
                    });

                    marker.on('drag', function(e) {
                        if (isDragging) {
                            this.getElement().style.opacity = '0.8';
                        }
                    });

                    marker.on('dragend', function(e) {
                        isDragging = false;
                        this.getElement().classList.remove('dragging');
                        this.getElement().style.opacity = '1';

                        const newPos = this.getLatLng();
                        const bounds = sitePlanSystem.state.imageBounds;

                        if (!bounds) return;

                        if (newPos.lat < bounds[0][0] || newPos.lat > bounds[1][0] ||
                            newPos.lng < bounds[0][1] || newPos.lng > bounds[1][1]) {
                            this.setLatLng(originalPosition);
                            this.showToast('Marker must stay within the site plan bounds', 'warning');
                        }
                    });

                    marker.addTo(this.state.editorMap);

                    this.state.markers.set(location.slug, {
                        marker,
                        iconType,
                        originalPosition: { x_pos: location.x_pos, y_pos: location.y_pos }
                    });
                });

                this.logDebug('success', `Successfully added ${locations.length} markers to editor`);
            } catch (error) {
                this.logDebug('error', 'Failed to parse locations data:', error);
                if (this.editorContainer) {
                    this.editorContainer.dataset.editorReady = 'error';
                }
            }
        },

        percentToImageCoords(x_pos, y_pos) {
            const bounds = this.state.imageBounds;
            const imageX = (x_pos / 100) * bounds[1][1];
            const imageY = (y_pos / 100) * bounds[1][0];
            return [imageY, imageX];
        },

        imageCoordsToPercent(coords) {
            const bounds = this.state.imageBounds;
            return {
                x_pos: Number((coords.lng / bounds[1][1] * 100).toFixed(2)),
                y_pos: Number((coords.lat / bounds[1][0] * 100).toFixed(2))
            };
        },

        createEditorMarkerPopup(location) {
            return `
                <div class="p-2">
                    <h6 class="mb-1">${location.name}</h6>
                </div>
            `;
        },

        createEditorIcon(is_active, iconType, name) {
            const iconClass = is_active ? iconType : config.inactive_icon;
            return L.divIcon({
                html: `<i class="bi ${iconClass} fs-5"></i>`,
                className: `location-marker ${is_active ? 'active' : 'inactive'}`,
                iconSize: [40, 40],
                iconAnchor: [20, 20],
                popupAnchor: [0, -20]
            });
        },

        resetView() {
            if (!this.state.editorMap || !this.state.imageBounds) return;
            this.state.editorMap.fitBounds(this.state.imageBounds);
            this.logDebug('operation', 'Reset editor view to bounds');
        },

        async saveChanges() {
            this.logDebug('saves', 'saveChanges triggered.');
            if (!this.state.isDirty) {
                this.logDebug('saves', 'No changes detected (isDirty is false). Aborting save.');
                return;
            }

            const changedLocations = Array.from(this.state.markers.entries())
                .map(([slug, {marker, originalPosition}]) => {
                    const currentPos = this.imageCoordsToPercent(marker.getLatLng());
                    const x_pos = currentPos.x_pos;
                    const y_pos = currentPos.y_pos;

                    if (Math.abs(x_pos - originalPosition.x_pos) > 0.01 || Math.abs(y_pos - originalPosition.y_pos) > 0.01) {
                        return { slug, x_pos, y_pos };
                    }
                    return null;
                })
                .filter(loc => loc !== null);

            if (changedLocations.length === 0) {
                this.logDebug('saves', 'No actual location changes detected after diff. Aborting save.');
                return;
            }

            try {
                this.logDebug('saves', 'Saving location updates to backend:', { locations: changedLocations });
                this.showToast('Saving changes...', 'info');

                const data = await window.utils.fetchWithCSRF(
                    `/${document.body.dataset.placeSlug}/siteplan/update/`,                    {
                        method: 'POST',
                        body: JSON.stringify({ locations: changedLocations })
                    }
                );

                this.logDebug('network', 'Parsed response data:', data);

                if (data.type === 'error' || data.type === 'danger') {
                    this.showToast(data.message || 'An unknown error occurred during save.', 'danger');
                    this.logDebug('error', 'Save failed with application error:', data);
                    return;
                }

                this.state.isDirty = false;

                // Create a new array with the updated locations
                const updatedLocations = state.locations.map(loc => {
                    const changedLoc = data.changes.locations.find(c => c.slug === loc.slug);
                    if (changedLoc) {
                        return {
                            ...loc,
                            x_pos: parseFloat(changedLoc.new_position.x_pos),
                            y_pos: parseFloat(changedLoc.new_position.y_pos)
                        };
                    }
                    return loc;
                });

                // Update the shared state
                state.locations = updatedLocations;

                this.logDebug('saves', 'Dispatching siteplan-update event with new locations:', updatedLocations);
                window.dispatchEvent(new CustomEvent('siteplan-update', {
                    detail: { locations: updatedLocations }
                }));

                const modal = bootstrap.Modal.getInstance(document.getElementById('mapplan-modal'));
                if (modal) {
                    modal.hide();
                }

                this.showToast(data.message || 'Changes saved successfully', data.type || 'warning');

                this.logDebug('success', 'Changes saved successfully:', data);

            } catch (error) {
                this.logDebug('error', 'Save failed due to network or unexpected error:', error);
                this.showToast('A network error occurred while saving. Please check your connection.', 'danger');
            }
        },

        fitMapPerfectly() {
            if (!this.state.editorMap || !this.state.imageBounds) return;

            const container = document.getElementById('siteplan-editor-map');
            if (!container || container.offsetWidth === 0) return;

            this.state.editorMap.invalidateSize();
            this.state.editorMap.fitBounds(this.state.imageBounds, {
                animate: false,
                padding: [0, 0]
            });

            this.logDebug('operation', 'Map fit updated', {
                containerSize: `${container.offsetWidth}x${container.offsetHeight}`
            });
        },

        showToast(message, type = 'info') {
            document.dispatchEvent(new CustomEvent('ToastEvents.SHOW', {
                detail: { message, type }
            }));
        },

        logDebug(type, message, data = null) {
            if (!scriptConfig.debug && type !== 'error') return;
            const icon = '🔷';
            const timestamp = new Date().toISOString().split('T')[1].slice(0, -1);
            console.log(`${timestamp} ${icon} ${message}`, data || '');
        }
    };

    window.sitePlanView = {
        initializeMainView: initializeMainView,
        initializeModalView: initializeModalView,
        state: state,
        createMarkerPopup: createMarkerPopup,
        getRandomIcon: getRandomIcon,
        createIcon: createIcon,
    };
    window.sitePlanSystem = sitePlanSystem;

    document.addEventListener('DOMContentLoaded', () => {
        const mainContainer = document.getElementById('siteplan-container-main');
        if (mainContainer) {
            window.sitePlanView.initializeMainView();
        } else {
            console.log('[DOMContentLoaded] No main site plan container found.');
        }
    });

    document.addEventListener('htmx:afterSwap', function(event) {
        if (event.target.id === 'mapplan-modal-content') {
            const editorMapEl = event.target.querySelector('#siteplan-editor-map');
            const viewMapEl = event.target.querySelector('#siteplan-container-modal');

            if (editorMapEl) {
                sitePlanSystem.initializeEditor(document.getElementById('mapplan-modal'));
            } else if (viewMapEl) {
                sitePlanView.initializeModalView();
            } else {
                console.log('[htmx:afterSwap] No map container found in swapped content.');
            }
        }
    });

    window.addEventListener('siteplan-update', (event) => {
        if (scriptConfig.debug) console.log('[siteplan-update] Event received', event.detail);

        // Update the locations data in the main view's data script tag
        const locationsDataEl = document.getElementById('locations-data-main');
        if (locationsDataEl) {
            // The event detail contains the full updated locations array
            locationsDataEl.textContent = JSON.stringify(event.detail.locations);
        }

        // Re-initialize the main view to reflect the updated locations
        const mainContainer = document.getElementById('siteplan-container-main');
        if (mainContainer) {
            // Clear the existing map
            if (state.maps['siteplan-container-main']) {
                state.maps['siteplan-container-main'].remove();
                delete state.maps['siteplan-container-main'];
            }
            // Re-initialize the view
            initializeMainView();
        }
    });

    console.log('[siteplan.js] IIFE finished executing.');
})();
