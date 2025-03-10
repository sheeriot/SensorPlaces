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
    console.group('=== Document Load Processing ===');
    debugLog('Document loaded and ready');

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

    // Initialize toast system with unread count
    if (window.toastSystem) {
        const unreadCount = document.body.dataset.unreadToasts || '0';
        document.body.dataset.unreadToasts = unreadCount;
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
    debugLog('Searching for server toast element:', { found: !!serverToastEl });

    if (serverToastEl && !serverToastEl.getAttribute('data-processed')) {
        console.group('=== Server Toast Message Found ===');
        debugLog('Found unprocessed server toast message');
        
        try {
            const toastScript = document.getElementById('toast-message-data');
            debugLog('Toast script element found:', { found: !!toastScript });
            
            if (toastScript && window.toastSystem) {
                debugLog('Toast script content:', toastScript.textContent);
                
                // Remove any HTML entities and parse JSON
                const rawContent = toastScript.textContent
                    .replace(/&quot;/g, '"')
                    .replace(/&#34;/g, '"')
                    .replace(/&lt;/g, '<')
                    .replace(/&gt;/g, '>');
                
                debugLog('Cleaned toast content:', rawContent);
                const toastData = JSON.parse(rawContent);
                debugLog('Successfully parsed toast data:', toastData);
                
                // For page-load toasts, don't increment the badge count
                toastData.addToHistory = false;
                
                debugLog('Showing toast with data:', toastData);
                
                // Delay showing the toast slightly to prevent FOUC
                requestAnimationFrame(() => {
                    window.toastSystem.show(toastData);
                    serverToastEl.setAttribute('data-processed', 'true');
                    debugLog('Toast processed and shown');
                });
            } else {
                debugLog('Missing toast script or toast system');
            }
        } catch (e) {
            console.error('Error processing server toast:', e);
            debugLog('Toast processing error:', e);
        }
        console.groupEnd();
    } else {
        debugLog('No unprocessed server toast messages found');
    }
});

// Export toast events for other modules
window.ToastEvents = {
    SHOW: 'sensors:toast:show',
    HISTORY: 'sensors:toast:history',
    CLEAR: 'sensors:toast:clear'
};