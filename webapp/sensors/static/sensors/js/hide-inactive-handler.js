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

            // Restore state from localStorage
            const storedStateJSON = localStorage.getItem(`hideInactive_${model}`);
            const storedState = storedStateJSON ? JSON.parse(storedStateJSON) : null;
            
            if (hideInactiveConfig.debug) {
                console.log(`[${model}] Initializing switch. Stored state: ${storedState}, Server-rendered state: ${switchEl.checked}`);
                if (storedState !== null && storedState !== switchEl.checked) {
                    console.warn(`[${model}] Mismatch between stored state (${storedState}) and server-rendered state (${switchEl.checked}).`);
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
        if (!selector) {
            if (hideInactiveConfig.debug) console.error(`No selector found for model: ${model}`);
            return;
        }

        // Get rows and group headers if applicable
        let rows;
        const groupHeaderClass = this.config.groupHeaderClasses[model];
        if (groupHeaderClass) {
            rows = document.querySelectorAll(`${selector}, tr.grouped-list-header.${groupHeaderClass}`);
        } else {
            rows = document.querySelectorAll(selector);
        }

        if (hideInactiveConfig.debug) {
            console.log(`Using selector: "${selector}". Found ${rows.length} rows to process.`);
        }

        // Update visibility of rows
        rows.forEach(row => {
            const isHeader = row.classList.contains('grouped-list-header');
            const dataAttrModel = isHeader 
                ? (row.classList.contains('device-location-list') ? 'location' : 'device')
                : model;
            
            const isActive = row.dataset[`${dataAttrModel}Active`] === 'true';

            if (!isActive) {
                const wasHidden = row.classList.contains('d-none');
                row.classList.toggle('d-none', hideInactive);
                const isHidden = row.classList.contains('d-none');

                if (hideInactiveConfig.debug) {
                    const logPrefix = isHeader ? `Group Header for inactive ${dataAttrModel}` : `Inactive ${model} row`;
                    console.log(`  - ${logPrefix}. Toggling visibility. Hidden: ${isHidden}`, row);
                    if (wasHidden !== isHidden) {
                        console.log(`    > Visibility changed from ${wasHidden} to ${isHidden}`);
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