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

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    // Initialize place slug from body data attribute
    window.currentPlaceSlug = document.body.dataset.placeSlug || null;

    if (commonConfig.debug) {
        console.group('=== Common System Startup ===');
        console.log('Current place slug:', window.currentPlaceSlug);
        console.groupEnd();

        console.group('=== Toast System Initialization ===');
        console.log('Toast system available:', !!window.toastSystem);
        console.groupEnd();
    }

    // Initialize toast event listeners
    document.addEventListener('sensors:toast:show', (event) => {
        if (commonConfig.debug) {
            console.group('=== Toast Message Processing ===');
            debugLog('Toast event received:', event.detail);
            debugLog('Toast system available:', !!window.toastSystem);
        }

        if (window.toastSystem) {
            const { message, type = 'info', addToHistory = true } = event.detail;
            debugLog('Showing toast:', { message, type, addToHistory });
            window.toastSystem.show(message, type, addToHistory);
        } else {
            debugLog('Warning: Toast system not available');
        }

        if (commonConfig.debug) {
            console.groupEnd();
        }
    });

    // Helper function to show toasts
    window.showToast = function(message, type = 'info', addToHistory = true) {
        debugLog('showToast called:', { message, type, addToHistory });
        document.dispatchEvent(new CustomEvent('sensors:toast:show', {
            detail: { message, type, addToHistory }
        }));
    };

    // Check for server-side toast message
    const serverToastEl = document.getElementById('server-toast-message');
    if (serverToastEl) {
        console.group('=== Server Toast Message Found ===');
        console.log('Server toast element:', serverToastEl);

        try {
            const toastScript = document.getElementById('toast-message-data');
            if (toastScript) {
                console.log('Toast script content:', toastScript.textContent);
                
                const toastData = JSON.parse(toastScript.textContent);
                console.log('Parsed toast data:', toastData);
                
                if (window.toastSystem) {
                    console.group('=== Sending Toast to System ===');
                    console.log('Raw toast data:', toastData);
                    console.log('Message:', toastData.message);
                    console.log('Type:', toastData.type);
                    console.log('Add to history:', toastData.addToHistory);
                    window.toastSystem.show(toastData);
                    serverToastEl.setAttribute('data-processed', 'true');
                    console.groupEnd(); // End "Sending Toast to System" group
                } else {
                    console.warn('Toast system not available for server message');
                }
            } else {
                console.warn('No toast-message-data script element found');
            }
        } catch (e) {
            console.error('Error processing server toast:', e);
        }

        console.groupEnd(); // End "Server Toast Message Found" group
    }
});

// Export toast events for other modules
window.ToastEvents = {
    SHOW: 'sensors:toast:show',
    HISTORY: 'sensors:toast:history',
    CLEAR: 'sensors:toast:clear'
};