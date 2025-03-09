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

// Global state
if (typeof window.currentPlaceSlug === 'undefined') {
    window.currentPlaceSlug = null;
}

// Custom events for toast notifications
const ToastEvents = {
    SHOW: 'sensors:toast:show',
    HISTORY: 'sensors:toast:history',
    CLEAR: 'sensors:toast:clear'
};

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    if (commonConfig.debug) {
        console.group('=== Common System Startup ===');
        console.log('Current place slug:', window.currentPlaceSlug);
        console.groupEnd();
    }

    // Initialize toast event listeners
    document.addEventListener(ToastEvents.SHOW, (event) => {
        debugLog('Toast event received', event.detail);
        if (window.toastSystem) {
            const { message, type = 'info', addToHistory = true } = event.detail;
            window.toastSystem.show(message, type, addToHistory);
        }
    });

    // Helper function to show toasts
    window.showToast = function(message, type = 'info', addToHistory = true) {
        document.dispatchEvent(new CustomEvent(ToastEvents.SHOW, {
            detail: { message, type, addToHistory }
        }));
    };

    // Process any Django messages on page load
    const toastMessageEl = document.getElementById('toast-message');
    if (toastMessageEl && !toastMessageEl.hasAttribute('data-toast-processed')) {
        toastMessageEl.setAttribute('data-toast-processed', 'true');
        try {
            const toastMessage = JSON.parse(toastMessageEl.textContent);
            window.showToast(toastMessage.message, toastMessage.type);
        } catch (e) {
            console.error('Error processing toast message:', e);
        }
    }
});

// Export toast events for other modules
window.ToastEvents = ToastEvents;