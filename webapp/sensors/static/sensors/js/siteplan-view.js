/**
 * Site Plan View System
 * Displays the site plan and location markers using Leaflet (read-only view)
 */

const sitePlanViewModule = (function () {
    const scriptConfig = {
        debug: true
    };

    const state = {
        maps: {},
        locations: [],
        markers: {}
    };

    const config = {
        active_icons: [
            'bi-geo-alt-fill', 'bi-wifi', 'bi-router-fill', 'bi-broadcast',
            'bi-camera-video-fill', 'bi-mic-fill'
        ],
        inactive_icon: 'bi-geo-alt'
    };

    function createMap(containerId, locationsDataId, isModal) {
        if (scriptConfig.debug) console.log(`[createMap] Attempting to load site plan. Image URL: ${document.getElementById(containerId).dataset.imageUrl}`);
        const locationsDataEl = document.getElementById(locationsDataId);
        if (!locationsDataEl) {
            console.error(`[createMap] Locations data element #${locationsDataId} not found!`);
            return;
        }
        if (scriptConfig.debug) console.log(`[createMap] Raw locations data from #${locationsDataId}: ${locationsDataEl.textContent}`);
        
        const imageUrl = document.getElementById(containerId).dataset.imageUrl;
        if (!imageUrl) {
            console.error(`[createMap] Image URL not found on container #${containerId}!`);
            return;
        }

        const img = new Image();
        img.onload = function () {
            createMapFromImage(img, containerId, locationsDataId, imageUrl, isModal);
        };
        img.onerror = function () {
            console.error(`[createMap] Failed to load image: ${imageUrl}`);
        };
        if (scriptConfig.debug) console.log(`[createMap] Setting image src to start loading: ${imageUrl}`);
        img.src = imageUrl;
    }

    function initializeMainView() {
        const siteplanContainer = document.getElementById('siteplan-container-main');
        if (siteplanContainer) {
            if (scriptConfig.debug) console.log('%c[siteplan-view.js] FOUND main page container #siteplan-container-main.', 'color: green; font-weight: bold;');
            createMap('siteplan-container-main', 'locations-data-main', false);
        } else {
            if (scriptConfig.debug) console.log('%c[siteplan-view.js] FAILED to find main page container #siteplan-container-main!', 'color: red; font-weight: bold;');
        }
    }

    function initializeModal() {
        const modalEl = document.getElementById('mapplan-modal');
        if (!modalEl) return;

        modalEl.addEventListener('shown.bs.modal', function (event) {
            const trigger = event.relatedTarget;
            const isSitePlanView = trigger && trigger.getAttribute('hx-get')?.includes('siteplan/view-modal');

            if (isSitePlanView) {
                if (scriptConfig.debug) console.log('%c[siteplan-view.js] Modal shown, now creating map.', 'color: blue; font-weight: bold;');
                createMap('siteplan-container-modal', 'locations-data-modal', true);
            }
        });
    }

    function createMapFromImage(img, containerId, locationsDataId, imageUrl, isModal) {
        if (scriptConfig.debug) console.log(`[createMapFromImage] Successfully loaded image: ${imageUrl}`);

        const container = document.getElementById(containerId);
        if (!container) {
            if (scriptConfig.debug) console.error(`[createMapFromImage] Container element #${containerId} not found! Cannot create map.`);
            return;
        }

        // Dynamically set container height to maintain image aspect ratio
        const containerWidth = container.offsetWidth;
        const imageAspectRatio = img.naturalHeight / img.naturalWidth;
        const calculatedHeight = containerWidth * imageAspectRatio;
        container.style.height = `${calculatedHeight}px`;
        if (scriptConfig.debug) console.log(`%c[createMapFromImage] Container height dynamically set to ${calculatedHeight}px to maintain aspect ratio.`, 'color: blue; font-weight: bold;');

        if (scriptConfig.debug) console.log(`[createMapFromImage] Container element #${containerId} found.`);
        if (scriptConfig.debug) console.log(`[createMapFromImage] ASSERT: Container dimensions before map creation: ${container.offsetWidth}w x ${container.offsetHeight}h`);

        if (container._leaflet_id) {
            if (scriptConfig.debug) console.warn(`[createMapFromImage] Leaflet ID found on container #${containerId}. It might be already initialized. Removing.`);
            const existingMap = L.DomUtil.getMap(container);
            if (existingMap) {
                if (scriptConfig.debug) console.log(`[createMapFromImage] Found existing map instance on #${containerId}. Removing it.`);
                existingMap.remove();
            }
        }

        if (scriptConfig.debug) console.log(`[createMapFromImage] Proceeding to create Leaflet map for #${containerId}.`);

        const map = L.map(containerId, {
            crs: L.CRS.Simple,
            minZoom: -5,
            maxZoom: 5,
        });
        if (scriptConfig.debug) console.log(`[createMapFromImage] CRS.Simple map created for #${containerId}.`);

        const bounds = [[0, 0], [img.naturalHeight, img.naturalWidth]];
        if (scriptConfig.debug) console.log(`[createMapFromImage] Image bounds calculated:`, bounds);

        L.imageOverlay(imageUrl, bounds).addTo(map);
        if (scriptConfig.debug) console.log(`[createMapFromImage] Image overlay added to map.`);

        const locationsDataEl = document.getElementById(locationsDataId);
        let locations;
        try {
            locations = JSON.parse(locationsDataEl.textContent);
            if (!Array.isArray(locations)) {
                throw new Error("Parsed data is not an array.");
            }
        } catch (e) {
            console.error(`[createMapFromImage] Failed to parse locations JSON from #${locationsDataId}:`, e);
            console.error("Data:", locationsDataEl.textContent);
            map.fitBounds(bounds);
            return;
        }

        if (scriptConfig.debug) console.log(`[createMapFromImage] Parsed ${locations.length} locations. Adding markers.`);

        const markerBounds = [];
        locations.forEach(location => {
            if (location.x_pos === null || location.y_pos === null) return;

            const pixelY = (location.y_pos / 100) * img.naturalHeight;
            const pixelX = (location.x_pos / 100) * img.naturalWidth;

            const simpleIcon = L.divIcon({
                html: `<i class="bi bi-geo-alt-fill"></i>`,
                className: `device-location-icon ${location.devices_active_count > 0 ? 'active' : 'inactive'}`,
                iconSize: [30, 30],
                iconAnchor: [15, 15],
                popupAnchor: [0, -15]
            });

            const marker = L.marker([pixelY, pixelX], { icon: simpleIcon }).addTo(map);
            marker.bindPopup(createMarkerPopup(location), {
                offset: L.point(0, -30)
            });
            markerBounds.push([pixelY, pixelX]);
        });

        if (markerBounds.length > 0) {
            map.fitBounds(markerBounds);
            if (scriptConfig.debug) console.log(`[createMapFromImage] Map fitted to marker bounds.`);
        } else {
            map.fitBounds(bounds);
            if (scriptConfig.debug) console.log(`[createMapFromImage] No markers, map fitted to image bounds.`);
        }

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
            html: `<i class="bi ${iconClass}"></i>`,
            className: `device-location-icon ${location.is_active ? 'active' : 'inactive'}`,
            iconSize: [30, 30],
            iconAnchor: [15, 15],
            popupAnchor: [0, -15]
        });
    }

    window.sitePlanView = {
        initializeMainView: initializeMainView,
        initializeModal: initializeModal,
        state: state,
        createMarkerPopup: createMarkerPopup,
        getRandomIcon: getRandomIcon,
        createIcon: createIcon,
    };

    document.addEventListener('DOMContentLoaded', () => {
        window.sitePlanView.initializeMainView();
        window.sitePlanView.initializeModal();
    });

})();
