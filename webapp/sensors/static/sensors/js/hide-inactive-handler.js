/**
 * Hide Inactive System
 * 
 * Manages and tracks hideInactive switches for places, locations, devices, and sensors.
 * Provides switch state information for other modules.
 */

// Debug Configuration
const hideInactiveConfig = {
    debug: false,            // Set to true to enable debug mode
};

// Hide Inactive System
const hideInactiveManager = {
    // Configuration
    config: {
        switchSelector: '.card-title .hideInactive-switch',
        supportedModels: ['place', 'location', 'device', 'sensor']
    },

    // State tracking
    state: {
        initialized: false,
        switches: new Map()  // Stores model -> {element, state} mapping
    },

    initialize() {
        if (this.state.initialized) {
            if (hideInactiveConfig.debug) console.debug('Hide Inactive System already initialized');
            return;
        }

        try {
            // Find all switches in card titles
            const switches = document.querySelectorAll(this.config.switchSelector);

            if (switches.length === 0) {
                if (hideInactiveConfig.debug) console.debug('No hide inactive switches found');
                return;
            }

            if (hideInactiveConfig.debug) {
                // Log inventory of found switches
                const switchInventory = Array.from(switches).map(sw => ({
                    model: sw.dataset.model,
                    cardId: sw.closest('.card')?.id || 'unnamed',
                    state: sw.checked ? 'Hidden' : 'Visible'
                }));

                console.group('Hide Inactive Switch Inventory:');
                console.table(switchInventory);
                console.groupEnd();
            }

            this.initializeSwitches(switches);
            this.state.initialized = true;

        } catch (error) {
            console.error('Hide Inactive System initialization failed:', error);
        }
    },

    initializeSwitches(switches) {
        try {
            // Store switch states
            Array.from(switches).forEach(el => {
                const model = el.dataset.model;
                if (model && this.config.supportedModels.includes(model)) {
                    // Store both the element and its current state
                    this.state.switches.set(model, {
                        element: el,
                        state: el.checked
                    });
                    this.initializeSwitch(el, model);
                }
            });

        } catch (error) {
            console.error('Switch initialization failed:', error);
        }
    },

    initializeSwitch(switchEl, model) {
        try {
            // Create change handler
            const handleVisibilityChange = (e) => {
                const newState = e.target.checked;
                // Update stored state
                this.state.switches.set(model, {
                    element: switchEl,
                    state: newState
                });
                
                // Dispatch event for other modules to handle visibility changes
                const event = new CustomEvent('hideInactiveChanged', {
                    detail: { model, state: newState }
                });
                document.dispatchEvent(event);
            };

            // Clean up any existing handlers
            switchEl.removeEventListener('change', handleVisibilityChange);
            
            // Add new handler
            switchEl.addEventListener('change', handleVisibilityChange);

        } catch (error) {
            console.error(`Failed to initialize ${model} switch:`, error);
        }
    },

    // Public method to get switch state for a model
    getSwitchState(model) {
        const switchData = this.state.switches.get(model);
        return switchData ? switchData.state : false;
    }
};

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    hideInactiveManager.initialize();
});

// Export for use in other modules
window.hideInactiveManager = hideInactiveManager; 