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
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Initialize all tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
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
        if(commonConfig.debug) console.log('[LiveValueFetcher] Forcing refresh for all live values.');
        this.fetch(true);
    }

    async fetch(force = false) {
        this.containers = document.querySelectorAll('.live-value-container');
        const allPksOnPage = [...new Set([...this.containers].map(c => c.dataset.sensorPk).filter(Boolean))];

        if (allPksOnPage.length === 0) return;

        const pksToFetch = new Set();
        const now = new Date().getTime();

        allPksOnPage.forEach(pk => {
            const lastCheck = sessionStorage.getItem(`sensor-${pk}-lastcheck`);
            if (force || !lastCheck || (now - parseInt(lastCheck) > this.interval)) {
                pksToFetch.add(pk);
            }
        });

        this.updateAllContainersFromCache();

        if (pksToFetch.size === 0) {
            if(commonConfig.debug) console.log('[LiveValueFetcher] All values fresh in cache. Nothing to fetch.');
            return;
        }

        if(commonConfig.debug) console.log('[LiveValueFetcher] Fetching stale/forced values for pks:', [...pksToFetch]);

        try {
            const url = `/api/${this.placeSlug}/sensors/live-values/?pks=${[...pksToFetch].join(',')}`;
            const response = await window.utils.fetchWithCSRF(url);
            if (!response.ok) throw new Error(`HTTP error ${response.status}`);

            const data = await response.json();
            if (data.status !== 'success') throw new Error(data.message || 'API returned an error');

            Object.entries(data.payload).forEach(([pk, sensorData]) => {
                sessionStorage.setItem(`sensor-${pk}-lastcheck`, now.toString());
                sessionStorage.setItem(`sensor-${pk}-data`, JSON.stringify(sensorData));
            });

            this.updateAllContainersFromCache();

        } catch (error) {
            console.error('[LiveValueFetcher] Error fetching data:', error);
            this.containers.forEach(container => {
                if (pksToFetch.has(container.dataset.sensorPk)) {
                    this.renderErrorForContainer(container, error.message);
                }
            });
        }
    }

    updateAllContainersFromCache() {
        this.containers.forEach(container => {
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
            let valueDisplay = parseFloat(sensorData.value).toFixed(sensorData.decimal_places || 2);
            const unit = sensorData.unit_symbol || '';

            // Handle Boolean type
            const isBoolean = (sensorData.unit_name && sensorData.unit_name.toLowerCase() === 'boolean') ||
                              (sensorData.sensor_type && sensorData.sensor_type.toLowerCase() === 'boolean');

            if (isBoolean) {
                const val = parseFloat(sensorData.value);
                valueDisplay = val > 0 ? 'True' : 'False';
            }

            const timestamp = sensorData.timestamp ? new Date(sensorData.timestamp) : null;
            const naturalTime = timestamp && window.utils ? window.utils.getNaturalTime(timestamp) : '';
            html = `
                <span class="badge bg-success-subtle text-success-emphasis rounded-1">${valueDisplay}${unit ? ' ' + unit : ''}</span>
                ${naturalTime ? `<small class="text-muted">(${naturalTime})</small>` : ''}
            `;
        } else if (sensorData && sensorData.status === 'no_reading') {
            html = `<span class="badge bg-secondary-subtle text-secondary-emphasis rounded-1">No reading</span>`;
        } else {
            const errorMessage = sensorData ? sensorData.message : 'Data not found';
            html = `<span class="badge bg-danger-subtle text-danger-emphasis rounded-1" title="${errorMessage}">Error</span>`;
        }
        container.innerHTML = html;
    }

    renderErrorForContainer(container, errorMessage) {
        container.innerHTML = `<span class="badge bg-danger-subtle text-danger-emphasis rounded-1" title="${errorMessage}">Error</span>`;
    }
}

// Explicitly attach to window for other scripts
window.LiveValueFetcher = LiveValueFetcher;

// Export initialization status checker
window.sensorPlaces.isInitialized = function(module) {
    return window.sensorPlaces.initialized[module] || false;
};

// Global event listeners (moved from base.html)
document.addEventListener('DOMContentLoaded', () => {
    // HTMX Modal Handling
    document.body.addEventListener('htmx:afterOnLoad', function(evt) {
        var target = evt.detail.target;
        if (target && target.id === 'modal-content') {
            var modalContainer = document.getElementById('modal-container');
            if (modalContainer) {
                var modal = new bootstrap.Modal(modalContainer);
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
