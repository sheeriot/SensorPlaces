/**
 * Common JavaScript functionality for the sensors application
 *
*/
// System Configuration
const commonConfig = {
    debug: false,
};

// Global state - expanded with body data attributes
window.sensorPlaces = {
    currentPlaceSlug: null,
    toastUnreadCount: 0,
    bodyData: {},  // Will hold all data-* attributes from body
    initialized: {
        activeStatusCheckbox: false,
        deviceForm: false
    }
};

// Add global error handler for uncaught promise rejections
window.addEventListener('unhandledrejection', event => {
    // Only suppress the specific extension-related error
    if (event.reason && event.reason.message &&
        event.reason.message.includes('message channel closed')) {
        event.preventDefault(); // Prevent the error from appearing in console
    }
});

// Initialize body data attributes and global state
function initializeGlobalState() {
    const body = document.body;
    if (!body) {
        if (commonConfig.debug) console.log('[initializeGlobalState] Body not available');
        return false;
    }

    // Get all data attributes from body
    window.sensorPlaces.bodyData = Object.assign({}, body.dataset);

    // Set specific commonly used values
    window.sensorPlaces.currentPlaceSlug = body.dataset.placeSlug || 'none';
    window.sensorPlaces.toastUnreadCount = parseInt(body.dataset.toastUnreadCount || '0', 10);

    if (commonConfig.debug) console.log('[initializeGlobalState] Global state initialized:', {
        placeSlug: window.sensorPlaces.currentPlaceSlug,
        unreadCount: window.sensorPlaces.toastUnreadCount,
        allBodyData: window.sensorPlaces.bodyData
    });

    // For backward compatibility (can be removed later)
    window.currentPlaceSlug = window.sensorPlaces.currentPlaceSlug;

    return true;
}

// Initialize core functionality
function initializeCore() {
    if (commonConfig.debug) console.log('[initializeCore] Starting initialization sequence');

    // Initialize global state first
    initializeGlobalState();

    try {
        // 1. Initialize active status checkbox system
        if (window.activeStatusCheckbox?.initialize) {
            if (commonConfig.debug) console.log('[initializeCore] Initializing active status checkbox');
            window.activeStatusCheckbox.initialize();
            window.sensorPlaces.initialized.activeStatusCheckbox = true;
        }

        // 2. Initialize device form (if present)
        if (window.deviceForm?.initialize) {
            if (commonConfig.debug) console.log('[initializeCore] Initializing device form');
            window.deviceForm.initialize();
            window.sensorPlaces.initialized.deviceForm = true;
        }

        if (commonConfig.debug) console.log('[initializeCore] Initialization complete:', {
            initialized: window.sensorPlaces.initialized
        });

    } catch (error) {
        if (commonConfig.debug) console.log('[initializeCore] Initialization error:', error);
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    if (commonConfig.debug) console.log('[DOMContentLoaded] Starting initialization');
    initializeCore();

    // Initialize all Bootstrap popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Initialize all tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize all dropdowns
    const dropdownTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="dropdown"]'));
    dropdownTriggerList.map(function (dropdownTriggerEl) {
        return new bootstrap.Dropdown(dropdownTriggerEl);
    });

    // Handle accessibility for modals: blur focus before hiding
    const modals = document.querySelectorAll('.modal');
    modals.forEach(modal => {
        modal.addEventListener('hide.bs.modal', function () {
            const focusedElement = document.activeElement;
            if (modal.contains(focusedElement)) {
                focusedElement.blur();
            }
        });
    });

    // HTMX Modal Handling
    document.body.addEventListener('htmx:afterOnLoad', function(evt) {
        const target = evt.detail.target;
        if (target && target.id === 'modal-content') {
            const modalContainer = document.getElementById('modal-container');
            if (modalContainer) {
                const modal = new bootstrap.Modal(modalContainer);
                modal.show();
            }
        }
    });

    // Global listener to close Bootstrap modals based on a custom event
    document.addEventListener('closeModal', function(event) {
        if (commonConfig.debug) console.log('Received closeModal event:', event.detail);
        const modalSelector = event.detail.value || event.detail; // Handle both object and string detail
        if (modalSelector) {
            const modalElement = document.querySelector(modalSelector);
            if (modalElement) {
                const modalInstance = bootstrap.Modal.getInstance(modalElement);
                if (modalInstance) {
                    if (commonConfig.debug) console.log('Hiding modal:', modalSelector);
                    modalInstance.hide();
                } else {
                    console.warn('Could not find a Bootstrap modal instance for selector:', modalSelector);
                }
            } else {
                console.warn('Could not find modal element with selector:', modalSelector);
            }
        }
    });

    // Add HTMX CSRF token configuration
    document.body.addEventListener('htmx:configRequest', function(evt) {
        if (evt.detail.verb === 'post' || evt.detail.verb === 'put' || evt.detail.verb === 'delete') {
            evt.detail.headers['X-CSRFToken'] = window.utils.getCookie('csrftoken');
        }
    });

    // Function to update natural time displays
    function updateTimestamps() {
        const elements = document.querySelectorAll('.updatable-naturaltime');
        elements.forEach(el => {
            const timestamp = el.dataset.timestamp;
            if (timestamp && window.utils && typeof window.utils.getNaturalTime === 'function') {
                el.textContent = window.utils.getNaturalTime(timestamp);
            }
        });
    }

    // Set an interval to update timestamps every 30 seconds
    setInterval(updateTimestamps, 30000);

    // Diagnostic listener for HTMX responses
    document.addEventListener('htmx:afterRequest', function(evt) {
        if (commonConfig.debug) {
            const xhr = evt.detail.xhr;
            console.log('HTMX request completed to:', xhr.responseURL);
            const triggerHeader = xhr.getResponseHeader('HX-Trigger-After-Settle');
            if (triggerHeader) {
                console.log('Server sent HX-Trigger-After-Settle:', triggerHeader);
            }
        }
    });
});

class LiveValueFetcher {
    constructor(placeSlug, interval = 30000) {
        this.placeSlug = placeSlug;
        this.interval = interval;
        this.timer = null;
        this.containers = [];
    }

    start() {
        this.fetch(); // Initial fetch
        if (this.timer) clearInterval(this.timer);
        this.timer = setInterval(() => this.fetch(), this.interval);
    }

    stop() {
        if (this.timer) clearInterval(this.timer);
    }

    forceRefresh() {
        if(commonConfig.debug) console.log('[LiveValueFetcher] Forcing refresh for all live values on page.');
        return this.fetch(true);
    }

    async fetch(force = false) {
        this.containers = document.querySelectorAll('.live-value-container');

        // Filter for containers that are visible and marked as active
        const activeAndVisibleContainers = [...this.containers].filter(c => {
            const isActive = c.dataset.active === 'true';
            const isVisible = c.offsetParent !== null; // A simple visibility check
            return isActive && isVisible;
        });

        const allPksOnPage = [...new Set(activeAndVisibleContainers.map(c => c.dataset.sensorPk).filter(Boolean))];

        if (allPksOnPage.length === 0) {
            if(commonConfig.debug) console.log('[LiveValueFetcher] No active and visible live value containers found on page.');
            return;
        }

        const pksToFetch = new Set();
        const now = new Date().getTime();

        allPksOnPage.forEach(pk => {
            const lastCheck = sessionStorage.getItem(`sensor-${pk}-lastcheck`);
            const cachedDataStr = sessionStorage.getItem(`sensor-${pk}-data`);
            let staleThreshold = this.interval; // Default

            if (cachedDataStr) {
                try {
                    const cachedData = JSON.parse(cachedDataStr);
                    if (cachedData.stale_threshold) {
                        staleThreshold = cachedData.stale_threshold * 1000; // Convert seconds to ms
                    }
                } catch (e) {
                    // Ignore if parsing fails, will use default
                }
            }

            if (force || !lastCheck || (now - parseInt(lastCheck) > staleThreshold)) {
                pksToFetch.add(pk);
            }
        });

        this.updateAllContainersFromCache();

        if (pksToFetch.size === 0) {
            if(commonConfig.debug) console.log('[LiveValueFetcher] All values fresh in cache. Nothing to fetch.');
            return Promise.resolve();
        }

        if(commonConfig.debug) console.log('[LiveValueFetcher] Fetching stale/forced values for pks:', [...pksToFetch]);

        try {
            const url = `/api/${this.placeSlug}/sensors/live-values/?pks=${[...pksToFetch].join(',')}`;
            const response = await fetch(url); // Assuming fetchWithCSRF is a wrapper around fetch

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            if(commonConfig.debug) console.log('[LiveValueFetcher] Received data from API:', data);

            if (data.status === 'success' && data.payload) {
                Object.entries(data.payload).forEach(([pk, sensorData]) => {
                    sessionStorage.setItem(`sensor-${pk}-lastcheck`, now.toString());
                    sessionStorage.setItem(`sensor-${pk}-data`, JSON.stringify(sensorData));

                    // If the fetch was successful, fire an event to tell the card to refresh itself via HTMX
                    if (sensorData.status === 'success') {
                        const event = new CustomEvent(`refresh-live-details-${pk}`);
                        document.body.dispatchEvent(event);
                        if(commonConfig.debug) console.log(`[LiveValueFetcher] Dispatched refresh-live-details-${pk} event.`);
                    }
                });

                // We no longer need to manually update the containers from cache here,
                // as the HTMX swap will handle the entire card update.
                // this.updateAllContainersFromCache();
            } else {
                // Handle cases where the top-level status is not 'success'
                throw new Error(data.message || 'API returned a non-success status');
            }
        } catch (error) {
            console.error('[LiveValueFetcher] Error fetching or processing data:', error);
            // Only render error for the specific containers that were part of this failed fetch
            this.containers.forEach(container => {
                if (pksToFetch.has(container.dataset.sensorPk)) {
                    this.renderErrorForContainer(container, error.message);
                }
            });
        }
    }

    updateAllContainersFromCache() {
        const allContainers = document.querySelectorAll('.live-value-container');
        allContainers.forEach(container => {
            const pk = container.dataset.sensorPk;
            const cachedDataStr = sessionStorage.getItem(`sensor-${pk}-data`);
            if (cachedDataStr) {
                const sensorData = JSON.parse(cachedDataStr);
                this.updateSingleContainer(container, sensorData);
            }
        });
    }

    updateSingleContainer(container, sensorData) {
        let html = '';
        if (sensorData && sensorData.status === 'success') {
            const value = parseFloat(sensorData.value);
            const unit = sensorData.unit_symbol || '';
            const isBoolean = (sensorData.unit_name && sensorData.unit_name.toLowerCase() === 'boolean');

            let valueDisplay;
            if (isBoolean) {
                valueDisplay = value > 0 ? 'True' : 'False';
            } else if (!isNaN(value)) {
                valueDisplay = value.toFixed(sensorData.decimal_places || 1);
            } else {
                valueDisplay = 'N/A'; // Handle case where value is not a number
            }

            const timestamp = sensorData.timestamp ? new Date(sensorData.timestamp) : null;
            const naturalTime = timestamp && window.utils ? window.utils.getNaturalTime(timestamp) : '';

            html = `
                <span class="badge bg-success-subtle text-success-emphasis rounded-1">${valueDisplay}${unit ? ' ' + unit : ''}</span>
                ${naturalTime ? `<small class="text-muted ms-1">(${naturalTime})</small>` : ''}
            `;
        } else if (sensorData && sensorData.status === 'no_reading') {
            html = `<span class="badge bg-secondary-subtle text-secondary-emphasis rounded-1" title="No reading available from source.">No Reading</span>`;
        } else {
            const errorMessage = sensorData ? sensorData.message : 'An error occurred';
            html = `<span class="badge bg-danger-subtle text-danger-emphasis rounded-1" title="${errorMessage}">Error</span>`;
        }
        container.innerHTML = html;

        if (sensorData && sensorData.status === 'success') {
            const pk = container.dataset.sensorPk;
            const wrapper = document.getElementById(`sensor-live-details-wrapper-${pk}`);

            if (wrapper) {
                const timeElements = wrapper.querySelectorAll('.updatable-naturaltime');
                if (timeElements.length > 0 && sensorData.timestamp) {
                    timeElements[0].dataset.timestamp = sensorData.timestamp;
                }
                if (timeElements.length > 1 && sensorData.last_checked_timestamp) {
                    timeElements[1].dataset.timestamp = sensorData.last_checked_timestamp;
                }
            }
        }
    }

    renderErrorForContainer(container, errorMessage) {
        container.innerHTML = `<span class="badge bg-danger-subtle text-danger-emphasis rounded-1" title="${errorMessage}">Error</span>`;
    }

    updateSensorValueFromGraph(sensorId, latestData, unitSymbol, decimalPlaces) {
        if (commonConfig.debug) console.log(`[LiveValueFetcher] Received update from graph for sensor ${sensorId}`, { latestData });
        if (!latestData) return;

        const [timestamp, value] = latestData;
        const cacheKey = `sensor-${sensorId}-data`;
        const cachedDataStr = sessionStorage.getItem(cacheKey);
        let sensorData;

        if (cachedDataStr) {
            sensorData = JSON.parse(cachedDataStr);
        } else {
            // If no data exists, create a shell object from what the graph knows.
            sensorData = {
                status: 'success',
                unit_symbol: unitSymbol,
                decimal_places: decimalPlaces,
            };
        }

        const newTimestamp = new Date(timestamp);
        const currentTimestamp = sensorData.timestamp ? new Date(sensorData.timestamp) : new Date(0);

        // Only update if the new data is newer
        if (newTimestamp > currentTimestamp) {
            if (commonConfig.debug) console.log(`[LiveValueFetcher] Graph data is newer. Updating cache and view for sensor ${sensorId}.`);
            sensorData.value = value;
            sensorData.timestamp = newTimestamp.toISOString();
            sessionStorage.setItem(cacheKey, JSON.stringify(sensorData));
            this.updateAllContainersFromCache();
        } else {
            if (commonConfig.debug) console.log(`[LiveValueFetcher] Graph data is not newer. Ignoring update for sensor ${sensorId}.`);
        }
    }
}

// Explicitly attach to window for other scripts
window.LiveValueFetcher = LiveValueFetcher;

// Export initialization status checker
window.sensorPlaces.isInitialized = function(module) {
    return window.sensorPlaces.initialized[module] || false;
};
