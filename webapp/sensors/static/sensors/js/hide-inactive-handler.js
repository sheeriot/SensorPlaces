/**
 * Hide Inactive Handler
 * 
 * Manages hide-inactive switches and dispatches state change events.
 * Controls visibility of inactive rows based on switch state.
 * 
 * Debug Mode:
 * -----------
 * To enable debug tables and logging, add ?debug=true to your URL:
 * http://your-site/page?debug=true
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

const hideInactiveHandler = {
    config: {
        switchSelector: '.hideInactive-switch',
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
        // Find and initialize all switches
        const switches = document.querySelectorAll(this.config.switchSelector);
        
        // Set up event listeners for each switch
        switches.forEach(switchEl => {
            const model = switchEl.dataset.model;
            if (!model) {
                console.warn('Switch missing model attribute:', switchEl);
                return;
            }

            // Initial row update based on switch state
            this.updateRowVisibility(model, switchEl.checked);

            // Set up change listener
            switchEl.addEventListener('change', (e) => {
                const newState = e.target.checked;
                
                // Update row visibility
                this.updateRowVisibility(model, newState);

                // Dispatch state change event
                window.dispatchEvent(new CustomEvent('hideInactiveStateChanged', {
                    detail: {
                        model,
                        hideInactive: newState,
                        switchId: switchEl.id,
                        timestamp: new Date().toISOString()
                    }
                }));
            });
        });
    },

    updateRowVisibility(model, hideInactive) {
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

        // Update visibility of rows
        rows.forEach(row => {
            if (row.classList.contains('grouped-list-header')) {
                const parentModel = row.classList.contains('device-location-list') ? 'location' :
                                  row.classList.contains('sensor-device-list') ? 'device' : null;
                if (parentModel) {
                    const isActive = row.dataset[`${parentModel}Active`] === 'true';
                    if (!isActive) {
                        row.classList.toggle('d-none', hideInactive);
                    }
                }
            } else {
                const isActive = row.dataset[`${model}Active`] === 'true';
                if (!isActive) {
                    row.classList.toggle('d-none', hideInactive);
                }
            }
        });
    }
};

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    hideInactiveHandler.initialize();
});