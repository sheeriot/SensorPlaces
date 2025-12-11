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

    if (commonConfig.debug) {
        console.log('[initializeGlobalState] Global state initialized:');
        console.table({
            'Place Slug': window.sensorPlaces.currentPlaceSlug,
            'Unread Count': window.sensorPlaces.toastUnreadCount,
        });
    }

    // For backward compatibility (can be removed later)
    window.currentPlaceSlug = window.sensorPlaces.currentPlaceSlug;

    return true;
}

/**
 * Initializes and manages the state of auto-refresh polling toggles for sensors.
 * It uses localStorage to persist the user's preference for each sensor.
 */
function initializePollingToggles(container) {
    const toggles = (container || document).querySelectorAll('.refresh-toggle');
    if (commonConfig.debug && toggles.length > 0) {
        console.log(`[PollingToggles] Found ${toggles.length} refresh toggles.`);
    }

    toggles.forEach(toggle => {
        const pollTargetSelector = toggle.dataset.pollTarget;
        const pollTarget = document.querySelector(pollTargetSelector);
        const sensorId = pollTargetSelector.split('-').pop(); // A bit fragile, but works for now
        const storageKey = `sensor-refresh-${sensorId}`;

        if (!pollTarget) {
            console.warn(`[PollingToggles] Could not find polling target: ${pollTargetSelector}`);
            return;
        }

        // Function to update the trigger attribute
        const updateTrigger = (isPolling) => {
            const currentTrigger = pollTarget.getAttribute('hx-trigger') || 'load';
            let triggers = currentTrigger.split(',').map(t => t.trim());

            // Remove existing polling trigger to avoid duplicates
            triggers = triggers.filter(t => !t.startsWith('every'));

            if (isPolling) {
                triggers.push('every 30s');
                if (commonConfig.debug) console.log(`[PollingToggles] Enabling polling for ${sensorId}`);
            } else {
                if (commonConfig.debug) console.log(`[PollingToggles] Disabling polling for ${sensorId}`);
            }

            pollTarget.setAttribute('hx-trigger', triggers.join(', '));
        };

        // Set initial state from localStorage
        const savedState = localStorage.getItem(storageKey);
        // Default to polling 'on' if no setting is saved
        const shouldPoll = savedState === null ? true : savedState === 'true';
        toggle.checked = shouldPoll;
        updateTrigger(shouldPoll);

        // Add change event listener
        toggle.addEventListener('change', () => {
            const isPolling = toggle.checked;
            localStorage.setItem(storageKey, isPolling);
            updateTrigger(isPolling);
        });
    });
}

/**
 * Initializes and manages the state of Bootstrap popovers, tooltips, and dropdowns.
 * This function is called on both DOMContentLoaded and htmx:afterSwap to ensure
 * components are always correctly initialized.
 */
function initializeBootstrap(element) {
    if (commonConfig.debug) console.log('[initializeBootstrap] Initializing Bootstrap components in', element);

    // Initialize all Bootstrap popovers
    const popoverTriggerList = element.querySelectorAll('[data-bs-toggle="popover"]');
    [...popoverTriggerList].map(popoverTriggerEl => new bootstrap.Popover(popoverTriggerEl, {
        container: 'body' // Append popovers to the body to avoid positioning issues
    }));

    // Initialize all tooltips
    const tooltipTriggerList = element.querySelectorAll('[data-bs-toggle="tooltip"]');
    [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));

    // Initialize all dropdowns
    const dropdownTriggerList = element.querySelectorAll('[data-bs-toggle="dropdown"]');
    [...dropdownTriggerList].map(dropdownTriggerEl => new bootstrap.Dropdown(dropdownTriggerEl));
};


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
    initializePollingToggles(document.body);
    initializeBootstrap(document.body);

    // Before a request that might replace a popover, dispose of it first to prevent errors.
    document.body.addEventListener('htmx:beforeRequest', function(evt) {
        const requestingElement = evt.detail.elt;
        let swapTarget;

        // Determine the actual target of the swap.
        const targetSelector = requestingElement.getAttribute('hx-target');
        if (targetSelector) {
            swapTarget = htmx.find(targetSelector);
        } else {
            swapTarget = requestingElement;
        }

        if (swapTarget && swapTarget.id.startsWith('sensor-live-value-')) {
            if (commonConfig.debug) console.log(`[htmx:beforeRequest] Preparing to swap ${swapTarget.id}. Checking for popovers.`);
            const popoverTrigger = swapTarget.querySelector('[data-bs-toggle="popover"]');
            if (popoverTrigger) {
                const instance = bootstrap.Popover.getInstance(popoverTrigger);
                if (instance) {
                    if (commonConfig.debug) console.log(`[htmx:beforeRequest] Disposing of active popover instance for ${swapTarget.id}.`);
                    instance.dispose();
                }
            }
        }
    });

    // Dispose of Bootstrap components before they are swapped out by HTMX
    document.body.addEventListener('htmx:beforeSwap', function(evt) {
        // This is a broader cleanup. The beforeRequest handler is more targeted.
        const target = evt.detail.target;
        if (target) {
            const popovers = target.querySelectorAll('[data-bs-toggle="popover"]');
            popovers.forEach(el => {
                const instance = bootstrap.Popover.getInstance(el);
                if (instance) {
                    instance.dispose();
                }
            });
            const tooltips = target.querySelectorAll('[data-bs-toggle="tooltip"]');
            tooltips.forEach(el => {
                const instance = bootstrap.Tooltip.getInstance(el);
                if (instance) {
                    instance.dispose();
                }
            });
        }
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

    // Run toggle initializer after any HTMX swap
    document.body.addEventListener('htmx:afterSwap', function(evt) {
        initializePollingToggles(evt.detail.target);
        initializeBootstrap(evt.detail.target);
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
            console.table({
                'URL': xhr.responseURL,
                'Status': xhr.status,
                'Success': evt.detail.successful,
                'Target': evt.detail.target.id,
            });
            const triggerHeader = xhr.getResponseHeader('HX-Trigger-After-Settle');
            if (triggerHeader) {
                console.log('Server sent HX-Trigger-After-Settle:', triggerHeader);
            }
        }
    });

    // Device Class Filtering
    const filterSelect = document.getElementById('device-class-filter');
    if (filterSelect) {
        const deviceList = document.getElementById('sensor-list-table');

        const filterDevices = () => {
            const selectedClass = filterSelect.value;
            const deviceRows = deviceList.querySelectorAll('.device-row');
            const locationRows = deviceList.querySelectorAll('.location-row');
            const hideInactiveSwitch = document.getElementById('hide-inactive-switch-device');
            const hideInactive = hideInactiveSwitch && hideInactiveSwitch.checked;

            // Filter device rows
            deviceRows.forEach(row => {
                const deviceClass = row.dataset.deviceClass;
                const isActive = row.dataset.deviceActive === 'true';

                const shouldBeHiddenByInactive = hideInactive && !isActive;
                const shouldBeHiddenByFilter = !(selectedClass === 'all' || deviceClass === selectedClass);

                if (shouldBeHiddenByInactive || shouldBeHiddenByFilter) {
                    row.classList.add('d-none');
                } else {
                    row.classList.remove('d-none');
                }
            });

            // Update visibility of location headers
            locationRows.forEach(locationRow => {
                const locationId = locationRow.dataset.locationId;
                const devicesInLocation = deviceList.querySelectorAll(`.device-row[data-location-id="${locationId}"]`);
                const anyVisible = Array.from(devicesInLocation).some(deviceRow => !deviceRow.classList.contains('d-none'));

                if (anyVisible) {
                    locationRow.classList.remove('d-none');
                } else {
                    locationRow.classList.add('d-none');
                }
            });
        };

        filterSelect.addEventListener('change', filterDevices);

        const hideInactiveSwitch = document.getElementById('hide-inactive-switch-device');
        if (hideInactiveSwitch) {
            hideInactiveSwitch.addEventListener('change', filterDevices);
        }

        // Initial filter on page load
        filterDevices();
    }
});

// Export initialization status checker
window.sensorPlaces.isInitialized = function(module) {
    return window.sensorPlaces.initialized[module] || false;
};
