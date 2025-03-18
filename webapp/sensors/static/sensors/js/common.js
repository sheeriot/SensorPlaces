/**
 * Common JavaScript functionality for the sensors application
 * 
 * Configuration:
 * -------------
 * To enable debugging, set debug: true in commonConfig below
 */

// System Configuration
const commonConfig = {
    debug: true  // Set to true to enable debug mode
};

// Global state - expanded with body data attributes
window.sensorPlaces = {
    currentPlaceSlug: null,
    toastUnreadCount: 0,
    bodyData: {},  // Will hold all data-* attributes from body
    initialized: {
        activeStatusCheckbox: false,
        deviceForm: false,
        toast: false
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

// Helper function to wait for toast system
function waitForToastSystem(maxAttempts = 10, interval = 100) {
    return new Promise((resolve, reject) => {
        let attempts = 0;
        
        const check = () => {
            if (commonConfig.debug) console.log('[check] Checking for toast system availability:', {
                attempt: attempts + 1,
                maxAttempts,
                available: !!window.toastSystem
            });

            if (window.toastSystem) {
                if (commonConfig.debug) console.log('[check] Toast system found');
                resolve(window.toastSystem);
            } else if (attempts >= maxAttempts) {
                if (commonConfig.debug) console.log('[check] Toast system not found after maximum attempts');
                reject(new Error('Toast system not available'));
            } else {
                attempts++;
                setTimeout(check, interval);
            }
        };

        check();
    });
}

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

// Initialize toast functionality
async function initializeToastFunctionality() {
    if (commonConfig.debug) console.log('[initializeToastFunctionality] Initializing toast functionality');

    try {
        // Wait for toast system to be available
        const toastSystem = await waitForToastSystem();
        if (commonConfig.debug) console.log('[initializeToastFunctionality] Toast system ready:', {
            initialized: toastSystem.initialized
        });

        // Initialize toast system with unread count
        const unreadCount = window.sensorPlaces.toastUnreadCount;
        if (commonConfig.debug) console.log('[initializeToastFunctionality] Set initial unread count:', { unreadCount });

        // Initialize toast event listeners
        document.addEventListener('sensors:toast:show', (event) => {
            if (commonConfig.debug) console.log('[Toast Event] Toast event received:', event.detail);

            const { message, type = 'info', addToHistory = true } = event.detail;
            toastSystem.show(message, type, addToHistory);
        });

        // Helper function to show toasts
        window.showToast = function(message, type = 'info', addToHistory = true) {
            if (commonConfig.debug) console.log('[showToast] Called with:', { message, type, addToHistory });
            
            // Handle object format
            if (typeof message === 'object' && message !== null) {
                type = message.type || type;
                addToHistory = 'addToHistory' in message ? message.addToHistory : addToHistory;
                message = message.message;
            }
            
            // First try using toast events
            try {
                document.dispatchEvent(new CustomEvent('sensors:toast:show', {
                    detail: { message, type, addToHistory }
                }));
            } catch (e) {
                if (commonConfig.debug) console.error('[showToast] Error dispatching event:', e);
            }
            
            // As a fallback, try to use toastSystem directly
            if (window.toastSystem && typeof window.toastSystem.show === 'function') {
                try {
                    window.toastSystem.show(message, type, addToHistory);
                } catch (e) {
                    if (commonConfig.debug) console.error('[showToast] Error using toastSystem.show:', e);
                }
            }
            
            // Ultimate fallback: create a toast manually
            if (!window.toastSystem || typeof window.toastSystem.show !== 'function') {
                try {
                    // Create the container if it doesn't exist
                    let container = document.querySelector('.toast-container');
                    if (!container) {
                        container = document.createElement('div');
                        container.className = 'toast-container position-fixed top-0 end-0 p-3';
                        container.style.zIndex = '1050';
                        document.body.appendChild(container);
                    }
                    
                    // Create toast element
                    const toastEl = document.createElement('div');
                    toastEl.className = `toast text-${type}`;
                    toastEl.style.pointerEvents = 'auto';
                    toastEl.innerHTML = `
                        <div class="d-flex align-items-center">
                            <div class="toast-body d-flex align-items-center flex-grow-1">
                                <i class="bi bi-${
                                    type === 'success' ? 'check-circle' : 
                                    type === 'danger' ? 'exclamation-circle' :
                                    type === 'warning' ? 'exclamation-triangle' : 
                                    'info-circle'
                                } me-2"></i>
                                <span>${message}</span>
                            </div>
                            <button type="button" class="btn-close me-2" data-bs-dismiss="toast"></button>
                        </div>
                    `;
                    
                    container.appendChild(toastEl);
                    
                    // Show the toast
                    if (typeof bootstrap !== 'undefined' && bootstrap.Toast) {
                        const toast = new bootstrap.Toast(toastEl, {
                            delay: 5000,
                            autohide: true
                        });
                        toast.show();
                    } else {
                        // Basic fallback
                        toastEl.style.display = 'block';
                        toastEl.style.opacity = '1';
                        
                        // Remove after 5 seconds
                        setTimeout(() => {
                            toastEl.style.opacity = '0';
                            setTimeout(() => toastEl.remove(), 500);
                        }, 5000);
                    }
                } catch (e) {
                    if (commonConfig.debug) console.error('[showToast] Error creating manual toast:', e);
                    // Last resort - alert
                    alert(`${type.toUpperCase()}: ${message}`);
                }
            }
        };

        if (commonConfig.debug) console.log('[initializeToastFunctionality] Toast functionality initialized successfully');

    } catch (error) {
        if (commonConfig.debug) console.log('[initializeToastFunctionality] Failed to initialize:', error);
    }
}

// Initialize core functionality
async function initializeCore() {
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

        // 3. Initialize toast system
        await initializeToastFunctionality();
        window.sensorPlaces.initialized.toast = true;

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

    // Export toast events for other modules
    window.ToastEvents = {
        SHOW: 'sensors:toast:show',
        HISTORY: 'sensors:toast:history',
        CLEAR: 'sensors:toast:clear'
    };

    // Initialize bootstrap components
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Initialize all Bootstrap popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
    
    // Initialize any Bootstrap toasts with the 'show' class
    var toasts = document.querySelectorAll('.toast.show');
    toasts.forEach(function(toastEl) {
        new bootstrap.Toast(toastEl).show();
    });
});

// Export initialization status checker
window.sensorPlaces.isInitialized = function(module) {
    return window.sensorPlaces.initialized[module] || false;
};