/**
 * Hide Inactive System
 * 
 * Manages visibility of inactive elements (places, locations, devices, sensors)
 * based on their respective hideInactive switches.
 * 
 * Configuration:
 * -------------
 * To enable debugging in code, set debug: true in systemConfig below
 * Debug mode will:
 * - Show visibility audits on initialization
 * - Show visibility audits after each switch change
 * - Display detailed tables of visibility states
 */

// System Configuration
const systemConfig = {
    debug: true,            // Set to true to enable debug mode
    auditOnStartup: true,   // Run audit when system initializes
    auditOnChange: true     // Run audit when switches change
};

// Hide Inactive System
const hideInactiveManager = {
    // Configuration
    config: {
        switchSelector: '.hideInactive-switch',
        modelMap: {
            'hideInactivePlaces': 'place',
            'hideInactiveLocations': 'location',
            'hideInactiveDevices': 'device',
            'hideInactiveSensors': 'sensor'
        },
        debug: systemConfig.debug
    },

    // State tracking
    state: {
        initialized: false,
        activeSwitches: new Map()
    },

    // Enable/disable debug mode
    setDebug(enabled) {
        this.config.debug = enabled;
        if (enabled && this.state.initialized) {
            this.auditVisibilityStates();
        }
    },

    initialize() {
        if (this.state.initialized) {
            return;
        }

        try {
            const switches = document.querySelectorAll(this.config.switchSelector);
            if (!switches.length) return;

            this.initializeSwitches(switches);
            
            if (this.config.debug && systemConfig.auditOnStartup) {
                this.auditVisibilityStates();
            }
            
            this.state.initialized = true;

        } catch (error) {
            console.error('Initialization failed:', error);
        }
    },

    auditVisibilityStates() {
        console.group('=== Visibility State Audit ===');
        
        try {
            for (const [model, switchEl] of this.state.activeSwitches) {
                const elements = document.querySelectorAll(`[data-${model}-active="false"]`);
                if (elements.length === 0) continue;

                console.group(`${model} Visibility Status`);
                
                // Prepare table data
                const tableData = Array.from(elements).map(el => {
                    const name = el.querySelector('.sensor-name')?.textContent || el.id || 'Unknown';
                    const currentState = el.classList.contains('d-none');
                    const expectedState = switchEl.checked;
                    const isCorrect = currentState === expectedState;
                    
                    return {
                        'Name': name,
                        'Should Hide': expectedState ? '✓' : '✗',
                        'Is Hidden': currentState ? '✓' : '✗',
                        'Correct': isCorrect ? '✓' : '✗'
                    };
                });

                // Log summary and table
                const incorrect = tableData.filter(row => row.Correct === '✗').length;
                if (incorrect > 0) {
                    console.warn(`Found ${incorrect} of ${elements.length} ${model}s with incorrect visibility`);
                } else {
                    console.log(`All ${elements.length} ${model}s have correct visibility`);
                }
                console.table(tableData);
                console.groupEnd();
            }
        } catch (error) {
            console.error('Audit failed:', error);
        } finally {
            console.groupEnd();
        }
    },

    initializeSwitches(switches) {
        try {
            // Store switch states
            Array.from(switches).forEach(el => {
                const model = this.config.modelMap[el.id];
                if (model) {
                    this.state.activeSwitches.set(model, el);
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
                this.updateVisibility(model, e.target.checked);
            };

            // Clean up any existing handlers
            switchEl.removeEventListener('change', handleVisibilityChange);
            
            // Add new handler
            switchEl.addEventListener('change', handleVisibilityChange);

        } catch (error) {
            console.error(`Failed to initialize ${model} switch:`, error);
        }
    },

    updateVisibility(model, hideInactive) {
        try {
            const elements = document.querySelectorAll(`[data-${model}-active="false"]`);
            elements.forEach(el => {
                el.classList.toggle('d-none', hideInactive);
            });

            if (this.config.debug && systemConfig.auditOnChange) {
                this.auditVisibilityStates();
            }

        } catch (error) {
            console.error('Visibility update failed:', error);
        }
    }
};

// Export for use in other modules
window.hideInactiveManager = hideInactiveManager; 