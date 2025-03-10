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

// Create and initialize the system
const createToastSystem = () => {
    if (toastConfig.debug) console.log('[Toast Manager] Creating toast system');
    
    const system = {
        initialized: false,
        historyButton: null,
        historyBadge: null,
        toastCount: 0,
        pendingMessages: [],

        initialize() {
            if (this.initialized) {
                if (toastConfig.debug) console.log('[Toast Manager] System already initialized');
                return true;
            }
            
            if (toastConfig.debug) console.group('[Toast Manager] System Initialization');
            
            this.historyButton = document.getElementById('toast-history-button');
            if (toastConfig.debug) console.log('[Toast Manager] History button search result:', {
                found: !!this.historyButton,
                buttonId: 'toast-history-button'
            });

            this.historyBadge = document.getElementById('toast-history-badge');
            if (toastConfig.debug) console.log('[Toast Manager] History badge search result:', {
                found: !!this.historyBadge,
                badgeId: 'toast-history-badge'
            });

            // Log detailed element properties if found
            if (this.historyButton) {
                if (toastConfig.debug) console.log('[Toast Manager] History button details:', {
                    id: this.historyButton.id,
                    className: this.historyButton.className,
                    ariaLabel: this.historyButton.getAttribute('aria-label'),
                    visible: this.historyButton.offsetParent !== null,
                    parent: this.historyButton.parentElement?.tagName
                });
            }

            if (this.historyBadge) {
                if (toastConfig.debug) console.log('[Toast Manager] History badge details:', {
                    id: this.historyBadge.id,
                    className: this.historyBadge.className,
                    display: window.getComputedStyle(this.historyBadge).display,
                    parent: this.historyBadge.parentElement?.tagName
                });
            }

            // Initialize unread count from body data attribute
            const unreadCount = parseInt(document.body.dataset.unreadToasts || '0', 10);
            if (toastConfig.debug) console.log('[Toast Manager] Reading unread count from body:', {
                rawValue: document.body.dataset.unreadToasts,
                parsedValue: unreadCount,
                bodyAttributes: Object.keys(document.body.dataset)
            });
            
            this.toastCount = unreadCount;
            
            if (this.historyBadge) {
                if (toastConfig.debug) console.log('[Toast Manager] Updating badge with count:', this.toastCount);
                this.updateBadge();
            } else {
                if (toastConfig.debug) console.log('[Toast Manager] Cannot update badge - element not found');
            }

            // Add history button click handler
            if (this.historyButton) {
                if (toastConfig.debug) console.log('[Toast Manager] Setting up history button click handler');
                this.historyButton.addEventListener('click', (event) => {
                    if (toastConfig.debug) console.log('[Toast Manager] History button clicked');
                    event.preventDefault();
                    
                    // Check if Bootstrap is available
                    if (typeof bootstrap === 'undefined') {
                        if (toastConfig.debug) console.log('[Toast Manager] Error: Bootstrap not loaded');
                        return;
                    }

                    // Find or create history modal
                    let historyModal = document.getElementById('toast-history-modal');
                    if (!historyModal) {
                        if (toastConfig.debug) console.log('[Toast Manager] Creating history modal');
                        historyModal = document.createElement('div');
                        historyModal.id = 'toast-history-modal';
                        historyModal.className = 'modal fade';
                        historyModal.setAttribute('tabindex', '-1');
                        historyModal.setAttribute('aria-hidden', 'true');
                        historyModal.innerHTML = `
                            <div class="modal-dialog">
                                <div class="modal-content">
                                    <div class="modal-header">
                                        <h5 class="modal-title">Notification History</h5>
                                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                                    </div>
                                    <div class="modal-body">
                                        <div id="toast-history-list" class="list-group list-group-flush">
                                            <!-- History items will be inserted here -->
                                        </div>
                                    </div>
                                </div>
                            </div>
                        `;
                        document.body.appendChild(historyModal);
                        if (toastConfig.debug) console.log('[Toast Manager] History modal created and added to DOM');
                    }

                    // Initialize and show modal
                    try {
                        const modal = new bootstrap.Modal(historyModal);
                        modal.show();
                        if (toastConfig.debug) console.log('[Toast Manager] History modal shown');
                    } catch (e) {
                        if (toastConfig.debug) console.log('[Toast Manager] Error showing history modal:', e);
                    }
                });
                if (toastConfig.debug) console.log('[Toast Manager] History button click handler initialized');
            }

            this.initialized = true;
            if (toastConfig.debug) console.log('[Toast Manager] Initialization complete', {
                historyButtonFound: !!this.historyButton,
                historyBadgeFound: !!this.historyBadge,
                unreadCount: this.toastCount
            });
            if (toastConfig.debug) console.groupEnd();
            return true;
        },

        updateBadge() {
            if (!this.historyBadge) {
                if (toastConfig.debug) console.log('[Toast Manager] No history badge element found to update');
                return;
            }
            
            if (toastConfig.debug) console.log('[Toast Manager] Updating badge with count:', this.toastCount);
            
            // Update badge text and visibility
            this.historyBadge.textContent = this.toastCount || '';
            
            // Only show badge if we have notifications
            if (this.toastCount > 0) {
                this.historyBadge.classList.remove('d-none');
                if (toastConfig.debug) console.log('[Toast Manager] Showing badge with count:', this.toastCount);
            } else {
                this.historyBadge.classList.add('d-none');
                if (toastConfig.debug) console.log('[Toast Manager] Hiding badge - no notifications');
            }
            
            // Update button aria-label
            if (this.historyButton) {
                const label = `Notification History (${this.toastCount} notifications)`;
                this.historyButton.setAttribute('aria-label', label);
                if (toastConfig.debug) console.log('[Toast Manager] Updated history button aria-label:', label);
            }

            if (toastConfig.debug) console.log('[Toast Manager] Badge update complete:', {
                count: this.toastCount,
                visible: !this.historyBadge.classList.contains('d-none'),
                text: this.historyBadge.textContent,
                fromHistory: this.toastCount > 0
            });
        },

        showToast(message, type = 'success', addToHistory = true) {
            if (toastConfig.debug) console.group('[Toast Manager] showToast');
            if (toastConfig.debug) console.log('Called with:', { message, type, addToHistory });

            if (!this.initialized) {
                if (toastConfig.debug) console.log('System not initialized, attempting initialization');
                const initResult = this.initialize();
                if (toastConfig.debug) console.log('Initialization result:', initResult);
                
                if (!initResult) {
                    if (toastConfig.debug) console.log('Initialization failed, queueing message');
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

            if (toastConfig.debug) console.log('Created toastData:', toastData);

            // Only increment badge count for API-triggered toasts that should be added to history
            if (toastData.addToHistory) {
                this.toastCount++;
                if (toastConfig.debug) console.log('[Toast Manager] Incrementing badge count for API toast:', this.toastCount);
                this.updateBadge();
            }

            // Use requestAnimationFrame for smooth animation
            requestAnimationFrame(() => {
                // Create or get toast container
                let toastContainer = document.querySelector('.toast-container');
                if (toastConfig.debug) console.log('[Toast Manager] Looking for toast container:', { found: !!toastContainer });

                if (!toastContainer) {
                    if (toastConfig.debug) console.log('[Toast Manager] Creating new toast container');
                    toastContainer = document.createElement('div');
                    toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
                    toastContainer.style.zIndex = '1050';
                    document.body.appendChild(toastContainer);
                }

                // Create toast element with pointer-events enabled
                const toastEl = document.createElement('div');
                toastEl.className = `toast text-${toastData.type}`;  // Remove 'show' class
                toastEl.style.pointerEvents = 'auto';
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

                toastContainer.insertAdjacentElement('afterbegin', toastEl);

                // Initialize Bootstrap toast with a slight delay
                requestAnimationFrame(() => {
                    if (typeof bootstrap === 'undefined') {
                        if (toastConfig.debug) console.log('[Toast Manager] Error: Bootstrap not loaded!');
                        if (toastConfig.debug) console.groupEnd();
                        return;
                    }

                    const toast = new bootstrap.Toast(toastEl, {
                        delay: 5000,
                        autohide: true,
                        animation: true
                    });
                    
                    // Add fade transition
                    toastEl.style.transition = 'opacity 0.15s linear';
                    toast.show();
                    
                    toastEl.addEventListener('hidden.bs.toast', () => {
                        toastEl.addEventListener('transitionend', () => {
                            toastEl.remove();
                            if (!toastContainer.children.length) {
                                toastContainer.remove();
                            }
                        }, { once: true });
                        toastEl.style.opacity = '0';
                    });
                });
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
    window.toastSystem = system;
    if (toastConfig.debug) console.log('[Toast Manager] System exported to window');
    return system;
};

// Initialize the toast system
const initializeToastSystem = () => {
    if (toastConfig.debug) console.log('[Toast Manager] Initializing system:', {
        readyState: document.readyState,
        time: new Date().toISOString()
    });

    if (!window.toastSystem) {
        if (toastConfig.debug) console.log('[Toast Manager] Creating new system instance');
        createToastSystem();
    }

    const initResult = window.toastSystem.initialize();
    if (toastConfig.debug) console.log('[Toast Manager] System initialized:', {
        success: initResult,
        initialized: window.toastSystem.initialized
    });

    // Only process server toasts when document is fully loaded
    if (document.readyState === 'complete') {
        if (toastConfig.debug) console.log('[Toast Manager] Document ready, processing server toasts');
        processServerToast();
    } else {
        if (toastConfig.debug) console.log('[Toast Manager] Document not ready, waiting for load');
        window.addEventListener('load', () => {
            if (toastConfig.debug) console.log('[Toast Manager] Window loaded, now processing server toasts');
            processServerToast();
        });
    }
};

// Ensure proper initialization sequence
const initWhenReady = () => {
    if (toastConfig.debug) console.log('Checking document ready state', {
        readyState: document.readyState,
        bodyAvailable: !!document.body
    });

    if (document.readyState === 'loading') {
        if (toastConfig.debug) console.log('Document still loading, adding DOMContentLoaded listener');
        document.addEventListener('DOMContentLoaded', () => {
            if (toastConfig.debug) console.log('DOMContentLoaded fired');
            if (document.readyState !== 'complete') {
                if (toastConfig.debug) console.log('Waiting for full load');
                window.addEventListener('load', initializeToastSystem);
            } else {
                initializeToastSystem();
            }
        });
    } else {
        if (toastConfig.debug) console.log('Document already interactive/complete, initializing now');
        initializeToastSystem();
    }
};

// Start initialization process immediately
if (toastConfig.debug) console.log('Starting toast system initialization process');
initWhenReady();

// Export toast events for other modules
window.ToastEvents = {
    SHOW: 'sensors:toast:show',
    HISTORY: 'sensors:toast:history',
    CLEAR: 'sensors:toast:clear'
};

// Process server-side toast messages
const processServerToast = () => {
    if (toastConfig.debug) console.log('[Toast Manager] Looking for server toasts');

    const toastContainer = document.getElementById('toast-messages');
    if (toastConfig.debug) console.log('[Toast Manager] Toast container:', {
        found: !!toastContainer,
        html: toastContainer?.outerHTML
    });

    if (toastContainer) {
        const serverToastElements = toastContainer.querySelectorAll('.server-toast-message');
        if (toastConfig.debug) console.log('[Toast Manager] Server toast elements:', {
            count: serverToastElements.length,
            elements: Array.from(serverToastElements).map(el => el.outerHTML)
        });

        Array.from(serverToastElements).forEach(toastMessage => {
            if (toastConfig.debug) console.log('[Toast Manager] Processing toast message:', toastMessage.outerHTML);
            
            // If data-processed is true, skip this toast
            if (toastMessage.getAttribute('data-processed') === 'true') {
                if (toastConfig.debug) console.log('[Toast Manager] Toast message already processed');
                return;
            }

            // Look for the script tag within this specific toast message
            const toastScript = toastMessage.querySelector('script[type="application/json"]');
            if (toastConfig.debug) console.log('[Toast Manager] Toast data script:', {
                found: !!toastScript,
                content: toastScript?.textContent,
                type: toastScript?.type
            });

            if (toastScript && window.toastSystem) {
                try {
                    const toastData = JSON.parse(toastScript.textContent);
                    if (toastConfig.debug) console.log('[Toast Manager] Parsed toast data:', toastData);
                    
                    // Server-side page load toasts should NOT update badge
                    toastData.addToHistory = false;  // Badge count is already in body data-unread-toasts
                    
                    requestAnimationFrame(() => {
                        if (toastConfig.debug) console.log('[Toast Manager] Showing page load toast:', {
                            ...toastData,
                            addToHistory: false
                        });
                        window.toastSystem.show(toastData);
                        toastMessage.setAttribute('data-processed', 'true');
                        if (toastConfig.debug) console.log('[Toast Manager] Page load toast processed');
                    });
                } catch (e) {
                    if (toastConfig.debug) console.log('[Toast Manager] Error processing toast:', e);
                }
            }
        });
    }
};

if (toastConfig.debug) console.log('Toast UI Manager script loaded', {
    readyState: document.readyState,
    toastSystemAvailable: !!window.toastSystem,
    eventsExported: !!window.ToastEvents
}); 