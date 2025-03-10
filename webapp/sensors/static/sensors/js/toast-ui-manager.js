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
    if (data) {
        console.debug(`[Toast Manager] ${message}`, data);
    } else {
        console.debug(`[Toast Manager] ${message}`);
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
        
        debugLog('Initializing toast system');

        // Find UI elements once
        this.historyButton = document.getElementById('toast-history-button');
        this.historyBadge = document.getElementById('toastHistoryBadge');

        if (!this.historyButton || !this.historyBadge) {
            debugLog('UI elements not found, will retry when DOM is ready');
            
            // Set up one-time DOM ready check if not already loaded
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', () => {
                    debugLog('DOM now ready, retrying initialization');
                    if (this.initialize()) {
                        // Show any pending messages
                        while (this.pendingMessages.length > 0) {
                            const [msg, type, addToHistory] = this.pendingMessages.shift();
                            this.showToast(msg, type, addToHistory);
                        }
                    }
                }, { once: true });
            }
            return false;
        }

        debugLog('Found UI elements:', { 
            button: this.historyButton, 
            badge: this.historyBadge 
        });

        this.initialized = true;
        debugLog('Toast system initialized');
        return true;
    },

    updateBadge() {
        if (!this.historyBadge) return;
        
        this.historyBadge.textContent = this.toastCount || '';
        this.historyBadge.classList.toggle('d-none', this.toastCount === 0);
        
        if (this.historyButton) {
            this.historyButton.setAttribute('aria-label', `Notification History (${this.toastCount} notifications)`);
        }
    },

    showToast(message, type = 'success', addToHistory = true) {
        if (toastConfig.debug) {
            console.group('[Toast Manager] showToast');
            console.log('Called with:', { message, type, addToHistory });
        }

        // If not initialized and initialization fails, queue the message
        if (!this.initialized && !this.initialize()) {
            debugLog('Queueing message for when DOM is ready:', { message, type, addToHistory });
            this.pendingMessages.push([message, type, addToHistory]);
            if (toastConfig.debug) console.groupEnd();
            return;
        }

        console.log('[Toast Manager] Past initialization check');
        console.trace('Execution trace');

        const toastData = {
            message: typeof message === 'object' ? message.message : message,
            type: typeof message === 'object' ? message.type : type,
            addToHistory: typeof message === 'object' ? message.addToHistory : addToHistory
        };

        console.log('[Toast Manager] Created toastData:', toastData);

        if (toastData.addToHistory) {
            this.toastCount++;
            this.updateBadge();
            console.log('[Toast Manager] Updated badge count:', this.toastCount);
        }

        // Create or get toast container
        console.group('[Toast Manager] Looking for toast container');
        let toastContainer = document.querySelector('.toast-container');
        console.log('querySelector(.toast-container) returned:', toastContainer);

        if (toastContainer) {
            const rect = toastContainer.getBoundingClientRect();
            console.log('Found existing container:', {
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
        } else {
            console.log('No existing container found, creating new one');
            toastContainer = document.createElement('div');
            toastContainer.className = 'toast-container';
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
    debugLog('DOM ready, initializing system');
    toastSystem.initialize();
}); 