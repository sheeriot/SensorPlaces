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
    debug: false,  // Set to true to enable debug mode
    apiEndpoint: (placeSlug) => `/api/${placeSlug}/toasts/`,
};

// if (toastConfig.debug) 
console.log('toastConfig.apiEndpoint:', toastConfig.apiEndpoint);

// Create and initialize the system
const createToastSystem = () => {
    if (toastConfig.debug) console.log('[Toast Manager] Creating toast system');
    
    const system = {
        initialized: false,
        historyButton: null,
        historyBadge: null,
        toastUnreadCount: 0,
        pendingMessages: [],

        initialize() {
            if (this.initialized) {
                if (toastConfig.debug) console.log('[Toast Manager] System already initialized');
                return true;
            }
            
            if (toastConfig.debug) console.group('[Toast Manager] System Initialization');
            
            // Get DOM elements
            this.historyButton = document.getElementById('toast-history-button');
            this.historyBadge = document.getElementById('toast-history-badge');
            
            if (!this.historyButton || !this.historyBadge) {
                if (toastConfig.debug) console.log('[Toast Manager] Required elements not found');
                if (toastConfig.debug) console.groupEnd();
                return false;
            }

            // Get initial count from global state
            this.toastUnreadCount = window.sensorPlaces.toastUnreadCount;
            
            if (toastConfig.debug) {
                console.log('[Toast Manager] Initial state:', {
                    unreadCount: this.toastUnreadCount,
                    placeSlug: window.sensorPlaces.currentPlaceSlug,
                    badgeVisible: !this.historyBadge.classList.contains('d-none')
                });
            }

            // Set up click handler for history button
            this.historyButton.addEventListener('click', async (event) => {
                if (toastConfig.debug) console.log('[Toast Manager] History button clicked');
                event.preventDefault();

                // Find history modal
                let historyModal = document.getElementById('toast-history-modal');
                if (!historyModal) {
                    if (toastConfig.debug) console.log('[Toast Manager] Error: History modal not found');
                    return;
                }

                // Get place slug from global state
                const placeSlug = window.sensorPlaces?.currentPlaceSlug;
                if (!placeSlug) {
                    if (toastConfig.debug) console.log('[Toast Manager] Error: No current place slug found in global state');
                    return;
                }

                // Define modal hidden handler first
                const handleModalHidden = () => {
                    // Return focus to history button
                    this.historyButton.focus();
                    
                    // Reset modal content
                    const historyList = historyModal.querySelector('#toastHistoryList');
                    if (historyList) {
                        historyList.innerHTML = `
                            <div class="text-center text-muted py-5">
                                <i class="bi bi-hourglass-split fs-1 d-block mb-3"></i>
                                Loading notifications...
                            </div>`;
                    }
                    
                    // Reset show all checkbox
                    const showAllCheckbox = historyModal.querySelector('#showAllToasts');
                    if (showAllCheckbox) {
                        showAllCheckbox.checked = false;
                        const newCheckbox = showAllCheckbox.cloneNode(true);
                        showAllCheckbox.parentNode.replaceChild(newCheckbox, showAllCheckbox);
                    }
                    
                    // Remove modal backdrop if it exists
                    const backdrop = document.querySelector('.modal-backdrop');
                    if (backdrop) {
                        backdrop.remove();
                    }
                    
                    // Reset modal state
                    historyModal.style.display = '';
                    historyModal.classList.remove('show');
                    historyModal.removeAttribute('aria-modal');
                    historyModal.removeAttribute('aria-hidden');
                    document.body.classList.remove('modal-open');
                    document.body.style.removeProperty('padding-right');
                };

                // Remove previous event listener if it exists
                historyModal.removeEventListener('hidden.bs.modal', handleModalHidden);
                
                // Add new event listener
                historyModal.addEventListener('hidden.bs.modal', handleModalHidden);

                // Show modal with loading state
                const modal = new bootstrap.Modal(historyModal, {
                    backdrop: true,
                    keyboard: true,
                    focus: true
                });
                
                modal.show();

                try {
                    // Initial load of unread notifications only
                    await this.loadToastHistory(placeSlug, false);

                    // Set up show all toggle handler
                    const showAllCheckbox = historyModal.querySelector('#showAllToasts');
                    showAllCheckbox.addEventListener('change', async (event) => {
                        await this.loadToastHistory(placeSlug, event.target.checked);
                    });

                    // Set up mark all as read handler
                    const markAllReadBtn = historyModal.querySelector('#markAllRead');
                    const confirmMarkAllReadBtn = document.querySelector('#confirmMarkAllRead');
                    
                    markAllReadBtn.addEventListener('click', () => {
                        const confirmModal = new bootstrap.Modal(document.getElementById('mark-all-read-modal'));
                        confirmModal.show();
                    });

                    confirmMarkAllReadBtn.addEventListener('click', async () => {
                        try {
                            const response = await window.utils.fetchWithCSRF(
                                toastConfig.apiEndpoint(placeSlug),
                                { method: 'POST' }
                            );

                            if (response.success) {
                                // Hide all unread notifications
                                const unreadItems = historyModal.querySelectorAll('.toast-history-item:not(.read)');
                                unreadItems.forEach(item => {
                                    item.classList.add('read', 'd-none');
                                    const checkbox = item.querySelector('.form-check-input');
                                    if (checkbox) checkbox.checked = true;
                                });

                                // Update badge count
                                this.updateBadge(0);

                                // Close the confirmation modal
                                bootstrap.Modal.getInstance(document.getElementById('mark-all-read-modal')).hide();
                            }
                        } catch (error) {
                            console.error('Error marking all as read:', error);
                        }
                    });

                } catch (error) {
                    console.error('Error loading toast history:', error);
                    const historyList = historyModal.querySelector('#toastHistoryList');
                    if (historyList) {
                            historyList.innerHTML = `
                            <div class="text-center text-danger py-5">
                                <i class="bi bi-exclamation-circle fs-1 d-block mb-3"></i>
                                Error loading notifications
                            </div>`;
                    }
                }
            });

            this.initialized = true;
            if (toastConfig.debug) console.groupEnd();
            return true;
        },

        updateBadge(count) {
            if (!this.historyBadge) {
                if (toastConfig.debug) console.log('[Toast Manager] Cannot update badge: element not found');
                return;
            }
            
            // Ensure count is a number
            this.toastUnreadCount = parseInt(count, 10) || 0;
            
            if (toastConfig.debug) {
                console.log('[Toast Manager] Updating badge:', {
                    count: this.toastUnreadCount,
                    willBeVisible: this.toastUnreadCount > 0
                });
            }
            
            // Update badge text
            this.historyBadge.textContent = this.toastUnreadCount || '';
            
            // Explicitly handle visibility
            if (this.toastUnreadCount > 0) {
                this.historyBadge.classList.remove('d-none');
            } else {
                this.historyBadge.classList.add('d-none');
            }
            
            // Update aria-label
            if (this.historyButton) {
                this.historyButton.setAttribute('aria-label', 
                    `Notification History (${this.toastUnreadCount} unread)`);
            }
        },

        showToast(message, type = 'success', addToHistory = true) {
            if (toastConfig.debug) console.log('[Toast Manager] Showing toast:', { message, type, addToHistory });

            if (!this.initialized) {
                const initResult = this.initialize();
                if (!initResult) {
                    this.pendingMessages.push([message, type, addToHistory]);
                    return;
                }
            }

            const toastData = {
                message: typeof message === 'object' ? message.message : message,
                type: typeof message === 'object' ? message.type : type,
                addToHistory: typeof message === 'object' ? message.addToHistory : addToHistory,
                unread_count: typeof message === 'object' ? message.unread_count : undefined
            };

            // Update badge count if provided in response
            if (toastData.unread_count !== undefined) {
                this.updateBadge(toastData.unread_count);
            } else if (addToHistory) {
                // If adding to history, increment the current count
                this.updateBadge(this.toastUnreadCount + 1);
            }

            // Create or get toast container
            let toastContainer = document.querySelector('.toast-container');
            if (!toastContainer) {
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
        },

        // Add new method for loading toast history
        async loadToastHistory(placeSlug, showAll = false) {
            const historyList = document.querySelector('#toastHistoryList');
            if (!historyList) return;

            try {
                const data = await window.utils.fetchWithCSRF(
                    `${toastConfig.apiEndpoint(placeSlug)}?show_all=${showAll}`
                );

                if (data.success) {
                    // Update badge count from API response
                    if (data.unread_count !== undefined) {
                        this.updateBadge(data.unread_count);
                    }

                    // Get template once
                    const template = document.getElementById('toast-history-item-template');
                    if (!template) {
                        console.error('[Toast Manager] Template not found');
                        return;
                    }

                    if (data.history.length === 0) {
                        historyList.innerHTML = `
                            <div class="text-center text-muted py-5">
                                <i class="bi bi-inbox fs-1 d-block mb-3"></i>
                                No notifications
                            </div>`;
                        return;
                    }

                    // Render history items
                    const historyHtml = data.history.map(toast => {
                        const element = template.content.cloneNode(true);
                        const container = element.querySelector('.toast-history-item');
                        
                        // Set container attributes
                        container.dataset.toastId = toast.id;
                        container.classList.toggle('read', toast.read);
                        container.classList.toggle('d-none', toast.read && !showAll);

                        // Set timestamp
                        const timestamp = new Date(toast.created_at).toLocaleString();
                        element.querySelector('.toast-timestamp').textContent = timestamp;

                        // Set message and type
                        const messageDiv = element.querySelector('.ms-4');
                        messageDiv.innerHTML = toast.message;
                        messageDiv.classList.add(`text-${toast.type}`);

                        // Set read checkbox
                        const checkbox = element.querySelector('.form-check-input');
                        checkbox.id = `toast-${toast.id}-read`;
                        checkbox.checked = toast.read;
                        checkbox.dataset.toastId = toast.id;

                        // Update label
                        const label = element.querySelector('.form-check-label');
                        label.setAttribute('for', `toast-${toast.id}-read`);

                        return container.outerHTML;
                    }).join('');

                    historyList.innerHTML = historyHtml;

                    // Add event listeners to checkboxes
                    historyList.querySelectorAll('.form-check-input').forEach(checkbox => {
                        checkbox.addEventListener('change', async (event) => {
                            if (!event.target.checked) return; // Only handle marking as read

                            const toastId = parseInt(event.target.dataset.toastId, 10);
                            const toastItem = event.target.closest('.toast-history-item');

                            try {
                                const response = await window.utils.fetchWithCSRF(
                                    toastConfig.apiEndpoint(placeSlug),
                                    {
                                        method: 'POST',
                                        body: JSON.stringify({
                                            action: 'mark_read',
                                            toast_ids: [toastId]
                                        })
                                    }
                                );

                                if (response.success) {
                                    toastItem.classList.add('read');
                                    if (!showAll) {
                                        toastItem.classList.add('d-none');
                                    }
                                    // Update badge from response
                                    if (response.unread_count !== undefined) {
                                        this.updateBadge(response.unread_count);
                                    }
                                }
                            } catch (error) {
                                console.error('Error marking toast as read:', error);
                                event.target.checked = false;
                            }
                        });
                    });

                    // Handle "Mark all as read" button
                    const markAllReadBtn = document.getElementById('confirmMarkAllRead');
                    if (markAllReadBtn) {
                        markAllReadBtn.onclick = async () => {
                            try {
                                const response = await window.utils.fetchWithCSRF(
                                    toastConfig.apiEndpoint(placeSlug),
                                    {
                                        method: 'POST',
                                        body: JSON.stringify({
                                            action: 'mark_read',
                                            toast_ids: data.history
                                                .filter(t => !t.read)
                                                .map(t => t.id)
                                        })
                                    }
                                );

                                if (response.success) {
                                    // Update UI
                                    const unreadItems = historyList.querySelectorAll('.toast-history-item:not(.read)');
                                    unreadItems.forEach(item => {
                                        item.classList.add('read');
                                        if (!showAll) {
                                            item.classList.add('d-none');
                                        }
                                        const checkbox = item.querySelector('.form-check-input');
                                        if (checkbox) checkbox.checked = true;
                                    });

                                    // Update badge from response
                                    if (response.unread_count !== undefined) {
                                        this.updateBadge(response.unread_count);
                                    }

                                    // Close confirmation modal
                                    const confirmModal = bootstrap.Modal.getInstance(document.getElementById('mark-all-read-modal'));
                                    if (confirmModal) {
                                        confirmModal.hide();
                                    }
                                }
                            } catch (error) {
                                console.error('Error marking all as read:', error);
                            }
                        };
                    }
                }
            } catch (error) {
                console.error('Error loading toast history:', error);
                historyList.innerHTML = `
                    <div class="text-center text-danger py-5">
                        <i class="bi bi-exclamation-circle fs-1 d-block mb-3"></i>
                        Error loading notifications
                    </div>`;
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
    if (toastConfig.debug) console.log('[Toast Manager] System initialized:', initResult);

    if (document.readyState === 'complete') {
        processServerToast();
    } else {
        window.addEventListener('load', processServerToast);
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
    const toastContainer = document.getElementById('toast-messages');
    if (!toastContainer) return;

    const serverToastElements = toastContainer.querySelectorAll('.server-toast-message');
    if (toastConfig.debug) console.log('[Toast Manager] Found server toasts:', serverToastElements.length);

    Array.from(serverToastElements).forEach(toastMessage => {
        if (toastMessage.getAttribute('data-processed') === 'true') return;

        const toastScript = toastMessage.querySelector('script[type="application/json"]');
        if (toastScript && window.toastSystem) {
            try {
                const toastData = JSON.parse(toastScript.textContent);
                toastData.addToHistory = false;  // Badge count is already in template
                window.toastSystem.show(toastData);
                toastMessage.setAttribute('data-processed', 'true');
            } catch (e) {
                console.error('[Toast Manager] Error processing toast:', e);
            }
        }
    });
};

if (toastConfig.debug) console.log('Toast UI Manager script loaded', {
    readyState: document.readyState,
    toastSystemAvailable: !!window.toastSystem,
    eventsExported: !!window.ToastEvents
}); 