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
            place: 'tr.place-row',
            location: 'tr.location-row',
            device: 'tr.device-row',
            sensor: 'tr.sensor-row'
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

            if (hideInactiveConfig.debug) {
                console.log(`Initializing switch for model: ${model}`);
            }

            // Initial row update based on switch state
            this.updateRowVisibility(model, switchEl.checked);

            // Set up change listener
            switchEl.addEventListener('change', (e) => {
                const newState = e.target.checked;
                
                if (hideInactiveConfig.debug) {
                    console.log(`Switch state changed for ${model}: ${newState}`);
                }

                // Update row visibility
                this.updateRowVisibility(model, newState);

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

    updateRowVisibility(model, hideInactive) {
        if (hideInactiveConfig.debug) {
            console.log(`Updating visibility for ${model} rows. Hide inactive: ${hideInactive}`);
        }

        const selector = this.config.rowSelectors[model];
        if (!selector) return;

        // Get rows and group headers if applicable
        let rows;
        const groupHeaderClass = this.config.groupHeaderClasses[model];
        if (groupHeaderClass) {
            rows = document.querySelectorAll(`${selector}, tr.grouped-list-header.${groupHeaderClass}`);
        } else {
            rows = document.querySelectorAll(selector);
        }

        if (hideInactiveConfig.debug) {
            console.log(`Found ${rows.length} rows to process`);
        }

        // Update visibility of rows
        rows.forEach(row => {
            if (row.classList.contains('grouped-list-header')) {
                const parentModel = row.classList.contains('device-location-list') ? 'location' :
                                  row.classList.contains('sensor-device-list') ? 'device' : null;
                if (parentModel) {
                    const isActive = row.dataset[`${parentModel}Active`] === 'true';
                    if (!isActive) {
                        row.classList.toggle('d-none', hideInactive);
                        if (hideInactiveConfig.debug) {
                            console.log(`Toggling visibility of group header for ${parentModel}: ${hideInactive}`);
                        }
                    }
                }
            } else {
                const isActive = row.dataset[`${model}Active`] === 'true';
                if (!isActive) {
                    row.classList.toggle('d-none', hideInactive);
                    if (hideInactiveConfig.debug) {
                        console.log(`Toggling visibility of ${model} row: ${hideInactive}`);
                    }
                }
            }
        });
    }
};

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    if (hideInactiveConfig.debug) {
        console.log('DOM loaded, initializing hideInactiveHandler');
    }
    hideInactiveHandler.initialize();
});