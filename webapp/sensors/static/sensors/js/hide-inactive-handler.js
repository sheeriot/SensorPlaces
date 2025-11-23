/**
 * Hide Inactive Handler
 *
 * Manages hide-inactive switches and dispatches state change events.
 * Controls visibility of inactive rows based on switch state.
 *
 * Debug Mode:
 * -----------
 * To enable debug mode, either:
 * 1. Add ?debug=true to your URL: http://your-site/page?debug=true
 * 2. Set hideInactiveConfig.debug = true in the console
 *
 * Debug Output:
 * - Switch initialization status
 * - State change events with timestamps
 * - Row visibility updates
 *
 * Example URLs:
 * http://localhost:8000/sensors/?debug=true
 * http://localhost:8000/sensors/places/?debug=true
 *
 * Switch Requirements:
 * - Must have class 'hideInactive-switch'
 * - Must have data-model attribute with valid model name
 */

const hideInactiveConfig = {
    debug: false
};

// Initialize debug mode from URL parameter
const urlParams = new URLSearchParams(window.location.search);
if (urlParams.get('debug') === 'true') {
    hideInactiveConfig.debug = true;
}

const hideInactiveHandler = {
    config: {
        switchSelector: '.hide-inactive-switch',
        modelSwitchSelector: (model) => `.hide-inactive-${model}-switch`,
        rowSelectors: {
            place: '.place-row',
            location: '.location-row',
            device: '.device-row',
            sensor: '.sensor-row'
        },
        groupHeaderClasses: {
            device: 'device-location-list',
            sensor: 'sensor-device-list'
        }
    },

    initialize() {
        if (hideInactiveConfig.debug) {
            console.log('Initializing hideInactiveHandler...');
        }

        // Find and initialize all switches
        const switches = document.querySelectorAll(this.config.switchSelector);

        if (hideInactiveConfig.debug) {
            console.log(`Found ${switches.length} hide-inactive switches`);
        }

        // Set up event listeners for each switch
        switches.forEach(switchEl => {
            const model = switchEl.dataset.model;
            if (!model) {
                console.warn('Switch missing model attribute:', switchEl);
                return;
            }

            // Check URL for override parameter
            const urlParams = new URLSearchParams(window.location.search);
            const urlHideInactive = urlParams.get('hide_inactive');

            if (urlHideInactive !== null) {
                // URL parameter takes precedence
                const hide = urlHideInactive.toLowerCase() !== 'false';
                switchEl.checked = hide;
                localStorage.setItem(`hideInactive_${model}`, JSON.stringify(hide));
                document.cookie = `hideInactive_${model}=${hide};path=/;max-age=31536000;samesite=lax`;
                if (hideInactiveConfig.debug) {
                    console.log(`[${model}] State overridden by URL parameter. New state: ${hide}`);
                }
                // Immediately update visibility based on URL override
                this.updateAllRowVisibility(hide, switchEl.closest('.card'));
            } else {
                // Restore state from localStorage if no URL override
                const storedStateJSON = localStorage.getItem(`hideInactive_${model}`);
                const storedState = storedStateJSON ? JSON.parse(storedStateJSON) : null;

                if (hideInactiveConfig.debug) {
                    const serverState = switchEl.checked;
                    console.log(`[${model}] Initializing switch. Stored state: ${storedState}, Server-rendered state: ${serverState}`);
                    if (storedState !== null && storedState !== serverState) {
                        console.warn(`[${model}] Mismatch between stored state (${storedState}) and server-rendered state (${serverState}). Server state is used.`);
                    }
                }
            }

            // Set up change listener
            switchEl.addEventListener('change', (e) => {
                const newState = e.target.checked;

                // Save state to localStorage
                localStorage.setItem(`hideInactive_${model}`, JSON.stringify(newState));

                // Set a cookie for the server to read
                document.cookie = `hideInactive_${model}=${newState};path=/;max-age=31536000;samesite=lax`;

                if (hideInactiveConfig.debug) {
                    console.log(`[${model}] Switch state changed to: ${newState}. Stored in localStorage and cookie.`);
                }

                this.updateAllRowVisibility(newState, e.target.closest('.card'));

                // Dispatch state change event
                const eventDetail = {
                    model,
                    hideInactive: newState,
                    switchId: switchEl.id,
                    timestamp: new Date().toISOString()
                };

                if (hideInactiveConfig.debug) {
                    console.log('Dispatching state change event:', eventDetail);
                }

                window.dispatchEvent(new CustomEvent('hideInactiveStateChanged', {
                    detail: eventDetail
                }));
            });
        });
    },

    updateAllRowVisibility(hideInactive, contextElement = document) {
        if (!contextElement) {
            if (hideInactiveConfig.debug) {
                console.warn('updateAllRowVisibility called without a valid context element. Defaulting to document.');
            }
            contextElement = document;
        }

        if (hideInactiveConfig.debug) {
            console.log(`Updating row visibility within context:`, contextElement);
            console.log(`Updating all row visibility. Hide inactive: ${hideInactive}`);
        }

        const inactiveLocations = contextElement.querySelectorAll('.location-row[data-location-active="false"]');
        const inactiveDevices = contextElement.querySelectorAll('.device-row[data-device-active="false"]');
        const inactiveSensors = contextElement.querySelectorAll('.sensor-row[data-sensor-active="false"]');

        if (hideInactiveConfig.debug) {
            console.log('Found inactive elements:', {
                locations: inactiveLocations.length,
                devices: inactiveDevices.length,
                sensors: inactiveSensors.length
            });
        }

        // First, handle hiding
        if (hideInactive) {
            inactiveLocations.forEach(row => row.classList.add('d-none'));
            inactiveDevices.forEach(row => row.classList.add('d-none'));
            inactiveSensors.forEach(row => row.classList.add('d-none'));
            return; // Exit after hiding
        }

        // Now, handle showing
        // Show all inactive items first
        inactiveLocations.forEach(row => row.classList.remove('d-none'));
        inactiveDevices.forEach(row => row.classList.remove('d-none'));
        inactiveSensors.forEach(row => row.classList.remove('d-none'));

        // For any shown sensor, ensure its parent device and location are visible
        inactiveSensors.forEach(sensorRow => {
            const deviceId = sensorRow.dataset.deviceId;
            if (deviceId) {
                const deviceRow = contextElement.querySelector(`.device-row[data-device-id="${deviceId}"]`);
                if (deviceRow) {
                    deviceRow.classList.remove('d-none');
                    const locationId = deviceRow.dataset.locationId;
                    if (locationId) {
                        const locationRow = contextElement.querySelector(`.location-row[data-location-id="${locationId}"]`);
                        if (locationRow) {
                            locationRow.classList.remove('d-none');
                        }
                    }
                }
            }
        });

        // For any shown device, ensure its parent location is visible
        inactiveDevices.forEach(deviceRow => {
            const locationId = deviceRow.dataset.locationId;
            if (locationId) {
                const locationRow = contextElement.querySelector(`.location-row[data-location-id="${locationId}"]`);
                if (locationRow) {
                    locationRow.classList.remove('d-none');
                }
            }
        });
    },

    updateRowVisibility(model, hideInactive) {
        // This function is now deprecated in favor of updateAllRowVisibility,
        // but kept for now to avoid breaking other parts of the application
        // that might still be calling it. It's recommended to migrate all
        // calls to updateAllRowVisibility.
        if (hideInactiveConfig.debug) {
            console.warn('updateRowVisibility is deprecated. Use updateAllRowVisibility instead.');
        }
        this.updateAllRowVisibility(hideInactive, document);
    },

    showParentRows(row) {
        // This function is now deprecated as its logic is included in updateAllRowVisibility.
        if (hideInactiveConfig.debug) {
            console.warn('showParentRows is deprecated.');
        }
    }
};

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    if (hideInactiveConfig.debug) {
        console.log('DOM loaded, initializing hideInactiveHandler');
    }
    hideInactiveHandler.initialize();
});
