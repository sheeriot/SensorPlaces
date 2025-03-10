/**
 * Toast UI Manager
 * 
 * Core functionality:
 * - Shows toast notifications
 * - Updates notification badge count
 * - Handles history button click events
 */

// System Configuration
const toastConfig = {
    debug: true  // Set to true to enable debug mode
};

// Debug logging helper
function debugLog(message, data = null) {
    if (!toastConfig.debug) return;
    const caller = new Error().stack.split('\n')[2].trim().split(' ')[1];
    if (data) {
        console.debug(`[${caller}]`, message, data);
    } else {
        console.debug(`[${caller}]`, message);
    }
}

// Toast UI Manager
const toastSystem = {
    initialized: false,
    historyButton: null,
    historyBadge: null,
    toastCount: 0,
    pendingMessages: [],

    initialize() {
        if (this.initialized) {
            debugLog('Toast system already initialized');
            return true;
        }
        
        debugLog('Starting initialization...');
        
        // Find UI elements once with detailed logging
        this.historyButton = document.getElementById('toast-history-button');
        debugLog('History button search result:', {
            found: !!this.historyButton,
            element: this.historyButton,
            buttonId: 'toast-history-button'
        });

        this.historyBadge = document.getElementById('toast-history-badge');
        debugLog('History badge search result:', {
            found: !!this.historyBadge,
            element: this.historyBadge,
            badgeId: 'toast-history-badge'
        });

        // Log detailed element properties if found
        if (this.historyButton) {
            debugLog('History button details:', {
                id: this.historyButton.id,
                className: this.historyButton.className,
                ariaLabel: this.historyButton.getAttribute('aria-label'),
                visible: this.historyButton.offsetParent !== null,
                parent: this.historyButton.parentElement?.tagName
            });
        }

        if (this.historyBadge) {
            debugLog('History badge details:', {
                id: this.historyBadge.id,
                className: this.historyBadge.className,
                display: window.getComputedStyle(this.historyBadge).display,
                parent: this.historyBadge.parentElement?.tagName
            });
        }

        // Initialize unread count from body data attribute
        const unreadCount = parseInt(document.body.dataset.unreadToasts || '0', 10);
        debugLog('Reading unread count from body:', {
            rawValue: document.body.dataset.unreadToasts,
            parsedValue: unreadCount,
            bodyAttributes: Object.keys(document.body.dataset)
        });
        
        this.toastCount = unreadCount;
        
        if (this.historyBadge) {
            debugLog('Updating badge with count:', this.toastCount);
            this.updateBadge();
        } else {
            debugLog('Cannot update badge - element not found');
        }

        this.initialized = true;
        debugLog('Initialization complete', {
            historyButtonFound: !!this.historyButton,
            historyBadgeFound: !!this.historyBadge,
            unreadCount: this.toastCount
        });
        return true;
    },

    updateBadge() {
        if (!this.historyBadge) {
            debugLog('No history badge element found to update');
            return;
        }
        
        debugLog('Updating badge with count:', this.toastCount);
        
        // Update badge text and visibility
        this.historyBadge.textContent = this.toastCount || '';
        
        // Only show badge if we have notifications
        if (this.toastCount > 0) {
            this.historyBadge.classList.remove('d-none');
            debugLog('Showing badge with count:', this.toastCount);
        } else {
            this.historyBadge.classList.add('d-none');
            debugLog('Hiding badge - no notifications');
        }
        
        // Update button aria-label
        if (this.historyButton) {
            const label = `Notification History (${this.toastCount} notifications)`;
            this.historyButton.setAttribute('aria-label', label);
            debugLog('Updated history button aria-label:', label);
        }

        debugLog('Badge update complete:', {
            count: this.toastCount,
            visible: !this.historyBadge.classList.contains('d-none'),
            text: this.historyBadge.textContent,
            fromHistory: this.toastCount > 0
        });
    },

    showToast(message, type = 'success', addToHistory = true) {
        if (toastConfig.debug) {
            console.group('[Toast Manager] showToast');
            console.log('Called with:', { message, type, addToHistory });
        }

        // If not initialized and initialization fails, queue the message
        if (!this.initialized) {
            console.log('System not initialized, attempting initialization');
            const initResult = this.initialize();
            console.log('Initialization result:', initResult);
            
            if (!initResult) {
                console.log('Initialization failed, queueing message');
                this.pendingMessages.push([message, type, addToHistory]);
                if (toastConfig.debug) console.groupEnd();
                return;
            }
        }

        const toastData = {
            message: typeof message === 'object' ? message.message : message,
            type: typeof message === 'object' ? message.type : type,
            addToHistory: typeof message === 'object' ? message.addToHistory : addToHistory
        };

        debugLog('Created toastData:', toastData);

        // Only increment badge count for API-triggered toasts that should be added to history
        if (toastData.addToHistory) {
            this.toastCount++;
            debugLog('Incrementing badge count for API toast:', this.toastCount);
            this.updateBadge();
        }

        // Create or get toast container
        console.group('[Toast Manager] Looking for toast container');
        let toastContainer = document.querySelector('.toast-container');
        console.log('querySelector(.toast-container) returned:', toastContainer);

        if (!toastContainer) {
            console.log('No existing container found, creating new one');
            toastContainer = document.createElement('div');
            toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
            toastContainer.style.zIndex = '1050';
            document.body.appendChild(toastContainer);
            
            // Log the newly created container's properties
            const rect = toastContainer.getBoundingClientRect();
            console.log('Created new container:', {
                element: toastContainer,
                position: {
                    top: rect.top,
                    right: rect.right,
                    width: rect.width,
                    height: rect.height
                },
                styles: {
                    position: window.getComputedStyle(toastContainer).position,
                    top: window.getComputedStyle(toastContainer).top,
                    right: window.getComputedStyle(toastContainer).right,
                    zIndex: window.getComputedStyle(toastContainer).zIndex
                }
            });
        }
        console.groupEnd();

        // Create toast element with pointer-events enabled
        console.group('[Toast Manager] Creating toast element');
        const toastEl = document.createElement('div');
        console.log('Created toast element:', toastEl);

        toastEl.className = `toast text-${toastData.type} show`;
        toastEl.style.pointerEvents = 'auto'; // Enable interactions for this element
        toastEl.setAttribute('role', 'alert');
        toastEl.setAttribute('aria-live', 'assertive');
        toastEl.setAttribute('aria-atomic', 'true');
        toastEl.innerHTML = `
            <div class="d-flex align-items-center">
                <div class="toast-body d-flex align-items-center flex-grow-1">
                    <i class="bi bi-${
                        toastData.type === 'success' ? 'check-circle' : 
                        toastData.type === 'danger' ? 'exclamation-circle' :
                        toastData.type === 'warning' ? 'exclamation-triangle' : 
                        'info-circle'
                    } me-2"></i>
                    <span>${toastData.message}</span>
                </div>
                <button type="button" class="btn-close me-2" data-bs-dismiss="toast"></button>
            </div>
        `;
        console.log('Toast element HTML set');

        toastContainer.insertAdjacentElement('afterbegin', toastEl);
        console.log('Toast element added to container');

        // Initialize Bootstrap toast
        if (typeof bootstrap === 'undefined') {
            console.error('[Toast Manager] Bootstrap not loaded!');
            if (toastConfig.debug) console.groupEnd();
            return;
        }

        console.log('[Toast Manager] Creating Bootstrap toast');
        const toast = new bootstrap.Toast(toastEl, {
            delay: 5000,
            autohide: true,
            animation: true
        });
        
        toast.show();
        console.log('[Toast Manager] Bootstrap toast.show() called');
        
        toastEl.addEventListener('shown.bs.toast', () => {
            console.log('[Toast Manager] Toast shown event fired');
        });

        toastEl.addEventListener('hidden.bs.toast', () => {
            console.log('[Toast Manager] Toast hidden event fired');
            toastEl.remove();
            if (!toastContainer.children.length) {
                toastContainer.remove();
                console.log('[Toast Manager] Removed empty toast container');
            }
        });

        if (toastConfig.debug) console.groupEnd();
    },

    // Main show method that handles both object and parameter-based calls
    show(message, type = 'success', addToHistory = true) {
        if (toastConfig.debug) {
            console.group('[Toast Manager] show() called');
            console.log('Received args:', { message, type, addToHistory });
            
            if (typeof message === 'object') {
                console.log('Message is an object, extracting:', message);
            } else {
                console.log('Message is direct string:', message);
            }
            console.groupEnd();
        }

        if (typeof message === 'object') {
            this.showToast(message.message, message.type, message.addToHistory);
        } else {
            this.showToast(message, type, addToHistory);
        }
    }
};

// Export for use in other modules
window.toastSystem = toastSystem;

// Initialize the toast system when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    debugLog('DOM ready, initializing toastSystem');
    
    // Wait for full DOM load
    if (document.readyState !== 'complete') {
        debugLog('DOM not fully loaded, waiting...', {
            currentState: document.readyState
        });
        
        window.addEventListener('load', () => {
            debugLog('Window fully loaded, initializing toast system');
            initializeToastSystem();
        });
        return;
    }

    initializeToastSystem();
});

function initializeToastSystem() {
    // Get initial unread count from body dataset
    const initialUnreadCount = document.body.dataset.unreadToasts;
    debugLog('Initial unread count from DOM:', {
        rawValue: initialUnreadCount,
        exists: 'unreadToasts' in document.body.dataset
    });

    // Initialize the system
    const initResult = toastSystem.initialize();
    debugLog('Toast system initialization result:', {
        success: initResult,
        currentCount: toastSystem.toastCount,
        badgeElement: toastSystem.historyBadge ? 'found' : 'not found'
    });

    // Force an initial badge update
    if (initResult && toastSystem.historyBadge) {
        toastSystem.updateBadge();
        debugLog('Initial badge update complete', {
            count: toastSystem.toastCount,
            badgeVisible: !toastSystem.historyBadge.classList.contains('d-none')
        });
    }
} 