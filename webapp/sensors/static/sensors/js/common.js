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

// Global state
window.sensorPlaces = {
    currentPlaceSlug: null,
    toastUnreadCount: 0
};

// Add global error handler for uncaught promise rejections
window.addEventListener('unhandledrejection', event => {
    // Only suppress the specific extension-related error
    if (event.reason && event.reason.message && 
        event.reason.message.includes('message channel closed')) {
        event.preventDefault(); // Prevent the error from appearing in console
    }
});

// Debug logging helper
function debugLog(message, data = null) {
    if (!commonConfig.debug) return;
    const caller = new Error().stack.split('\n')[2].trim().split(' ')[1];
    if (data) {
        console.debug(`[${caller}]`, message, data);
    } else {
        console.debug(`[${caller}]`, message);
    }
}

// Helper function to wait for toast system
function waitForToastSystem(maxAttempts = 10, interval = 100) {
    return new Promise((resolve, reject) => {
        let attempts = 0;
        
        const check = () => {
            debugLog('Checking for toast system availability', {
                attempt: attempts + 1,
                maxAttempts,
                available: !!window.toastSystem
            });

            if (window.toastSystem) {
                debugLog('Toast system found');
                resolve(window.toastSystem);
            } else if (attempts >= maxAttempts) {
                debugLog('Toast system not found after maximum attempts');
                reject(new Error('Toast system not available'));
            } else {
                attempts++;
                setTimeout(check, interval);
            }
        };

        check();
    });
}

// Initialize place slug and other global state
function initializeGlobalState() {
    // Get place slug from body data attribute
    window.sensorPlaces.currentPlaceSlug = document.body.dataset.placeSlug || null;
    window.sensorPlaces.toastUnreadCount = parseInt(document.body.dataset.toastUnreadCount || '0', 10);
    
    debugLog('Global state initialized:', {
        placeSlug: window.sensorPlaces.currentPlaceSlug,
        unreadCount: window.sensorPlaces.toastUnreadCount
    });
    
    // For backward compatibility (can be removed later)
    window.currentPlaceSlug = window.sensorPlaces.currentPlaceSlug;
}

// Initialize toast functionality
async function initializeToastFunctionality() {
    debugLog('Initializing toast functionality');

    try {
        // Wait for toast system to be available
        const toastSystem = await waitForToastSystem();
        debugLog('Toast system ready', {
            initialized: toastSystem.initialized
        });

        // Initialize toast system with unread count
        const unreadCount = window.sensorPlaces.toastUnreadCount;
        debugLog('Set initial unread count:', { unreadCount });

        // Initialize toast event listeners
        document.addEventListener('sensors:toast:show', (event) => {
            debugLog('Toast event received:', event.detail);

            const { message, type = 'info', addToHistory = true } = event.detail;
            toastSystem.show(message, type, addToHistory);
        });

        // Helper function to show toasts
        window.showToast = function(message, type = 'info', addToHistory = true) {
            debugLog('showToast called:', { message, type, addToHistory });
            document.dispatchEvent(new CustomEvent('sensors:toast:show', {
                detail: { message, type, addToHistory }
            }));
        };

        debugLog('Toast functionality initialized successfully');

    } catch (error) {
        debugLog('Failed to initialize toast functionality:', error);
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    debugLog('Document loaded and ready', {
        readyState: document.readyState,
        toastAvailable: !!window.toastSystem
    });

    // Initialize global state first
    initializeGlobalState();

    // Initialize toast functionality
    initializeToastFunctionality().then(() => {
        debugLog('Toast initialization complete');
    }).catch(error => {
        debugLog('Toast initialization failed:', error);
    });

    // Export toast events for other modules
    window.ToastEvents = {
        SHOW: 'sensors:toast:show',
        HISTORY: 'sensors:toast:history',
        CLEAR: 'sensors:toast:clear'
    };
});