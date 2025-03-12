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
    debug: true,  // Set to true to enable debug mode
    apiEndpoints: {
        markAsRead: '/api/toasts/mark-read/',
        clearHistory: '/api/toasts/clear-history/'
    }
};

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

            // Remove local count initialization - rely on HTML data attribute
            this.toastUnreadCount = 0;
            
            if (this.historyBadge) {
                // Only update visibility based on current badge state
                const currentCount = parseInt(this.historyBadge.textContent || '0', 10);
                this.historyBadge.classList.toggle('d-none', currentCount === 0);
            }

            // Add history button click handler
            if (this.historyButton) {
                if (toastConfig.debug) console.log('[Toast Manager] Setting up history button click handler');
                this.historyButton.addEventListener('click', async (event) => {
                    if (toastConfig.debug) console.log('[Toast Manager] History button clicked');
                    event.preventDefault();

                    // Find history modal
                    let historyModal = document.getElementById('toast-history-modal');
                    if (!historyModal) {
                        if (toastConfig.debug) console.log('[Toast Manager] Error: History modal not found');
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
                        // Fetch history using utils.fetchWithCSRF
                        const data = await window.utils.fetchWithCSRF('/api/toast-history/');
                        
                        // Update the modal content with the history data
                        const historyList = historyModal.querySelector('#toastHistoryList');
                        if (historyList && data.history) {
                            let historyHtml = '';
                            
                            if (data.history.length === 0) {
                                if (toastConfig.debug) console.log('[Toast Manager] No history items to display');
                                historyHtml = `
                                    <div class="text-center text-muted py-5">
                                        <i class="bi bi-inbox fs-1 d-block mb-3"></i>
                                        No notifications yet
                                    </div>`;
                            } else {
                                if (toastConfig.debug) {
                                    console.group('[Toast Manager] Rendering history items');
                                    console.log('History items count:', data.history.length);
                                }
                                
                                // Get the template
                                const template = document.getElementById('toast-history-item-template');
                                if (!template) {
                                    console.error('[Toast Manager] Template not found: toast-history-item-template');
                                    return;
                                }
                                if (toastConfig.debug) console.log('[Toast Manager] Template found:', template.innerHTML);

                                historyHtml = data.history.map(toast => {
                                    if (toastConfig.debug) {
                                        console.group(`[Toast Manager] Processing toast ${toast.id}`);
                                        console.log('Toast data:', toast);
                                    }
                                    
                                    const date = new Date(toast.created_at);
                                    const timestamp = date.toLocaleString('en-US', {
                                        year: 'numeric',
                                        month: '2-digit',
                                        day: '2-digit',
                                        hour: '2-digit',
                                        minute: '2-digit',
                                        second: '2-digit',
                                        hour12: false,
                                        timeZoneName: 'shortOffset'
                                    }).replace(',', '');
                                    
                                    if (toastConfig.debug) console.log('Formatted timestamp:', timestamp);
                                    
                                    // Clone the template content
                                    const element = template.content.cloneNode(true);
                                    if (toastConfig.debug) console.log('Cloned template:', element);
                                    
                                    const container = element.querySelector('.toast-history-item');
                                    if (!container) {
                                        console.error('[Toast Manager] Could not find .toast-history-item in template');
                                        if (toastConfig.debug) console.groupEnd();
                                        return '';
                                    }
                                    
                                    // Set data and classes
                                    container.dataset.toastId = toast.id;
                                    container.classList.toggle('d-none', toast.read);
                                    container.classList.add(toast.read ? 'read' : 'unread');
                                    
                                    // Set timestamp
                                    const timestampEl = element.querySelector('.toast-timestamp');
                                    if (timestampEl) {
                                        timestampEl.textContent = timestamp;
                                    } else {
                                        console.error('[Toast Manager] Could not find .toast-timestamp');
                                    }
                                    
                                    // Set type badge
                                    const typeBadgeClass = 
                                        toast.type === 'success' ? 'bg-success' :
                                        toast.type === 'danger' ? 'bg-danger' :
                                        toast.type === 'warning' ? 'bg-warning text-dark' :
                                        'bg-info text-dark';
                                    
                                    const typeIcon = 
                                        toast.type === 'success' ? 'check-circle' :
                                        toast.type === 'danger' ? 'exclamation-circle' :
                                        toast.type === 'warning' ? 'exclamation-triangle' :
                                        'info-circle';
                                    
                                    const typeBadgeEl = element.querySelector('.toast-type-badge');
                                    if (typeBadgeEl) {
                                        typeBadgeEl.innerHTML = `
                                            <span class="badge ${typeBadgeClass}">
                                                <i class="bi bi-${typeIcon} me-1"></i>${toast.type}
                                            </span>`;
                                    } else {
                                        console.error('[Toast Manager] Could not find .toast-type-badge');
                                    }
                                    
                                    // Set checkbox
                                    const checkbox = element.querySelector('.form-check-input');
                                    if (checkbox) {
                                        checkbox.id = `toast-${toast.id}-read`;
                                        checkbox.checked = toast.read;
                                        checkbox.dataset.toastId = toast.id;
                                    } else {
                                        console.error('[Toast Manager] Could not find .form-check-input');
                                    }
                                    
                                    const label = element.querySelector('.form-check-label');
                                    if (label) {
                                        label.setAttribute('for', `toast-${toast.id}-read`);
                                    } else {
                                        console.error('[Toast Manager] Could not find .form-check-label');
                                    }
                                    
                                    // Set message
                                    const messageDiv = element.querySelector('.ms-4');
                                    if (messageDiv) {
                                        messageDiv.classList.add(`text-${toast.type}`);
                                        messageDiv.innerHTML = toast.message;
                                    } else {
                                        console.error('[Toast Manager] Could not find message div with .ms-4');
                                    }
                                    
                                    if (toastConfig.debug) {
                                        console.log('Generated HTML:', container.outerHTML);
                                        console.groupEnd();
                                    }
                                    
                                    return container.outerHTML;
                                }).join('');
                                
                                if (toastConfig.debug) {
                                    console.log('Final HTML:', historyHtml);
                                    console.groupEnd();
                                }
                            }
                            
                            historyList.innerHTML = historyHtml;
                            
                            // Show/hide clear history button based on content
                            const clearButton = historyModal.querySelector('#clearToastHistory');
                            if (clearButton) {
                                clearButton.classList.toggle('d-none', data.history.length === 0);
                            }

                            // Add event listeners for the show all toggle and read checkboxes
                            const showAllCheckbox = historyModal.querySelector('#showAllToasts');
                            const readCheckboxes = historyModal.querySelectorAll('.toast-read-checkbox');

                            // Handle show all toggle
                            showAllCheckbox.addEventListener('change', (event) => {
                                const readToasts = historyModal.querySelectorAll('.toast-history-item.read');
                                readToasts.forEach(toast => {
                                    toast.classList.toggle('d-none', !event.target.checked);
                                });
                            });

                            // Handle read checkbox changes
                            readCheckboxes.forEach(checkbox => {
                                checkbox.addEventListener('change', async (event) => {
                                    const toastId = event.target.dataset.toastId;
                                    const toastItem = event.target.closest('.toast-history-item');
                                    
                                    try {
                                        const response = await window.utils.fetchWithCSRF('/api/toasts/mark-read/', {
                                            method: 'POST',
                                            body: JSON.stringify({
                                                toast_id: toastId,
                                                read: event.target.checked
                                            })
                                        });
                                        
                                        // Update UI
                                        if (event.target.checked) {
                                            toastItem.classList.add('read');
                                            if (!showAllCheckbox.checked) {
                                                toastItem.classList.add('d-none');
                                            }
                                            // Decrement unread count
                                            this.toastUnreadCount = Math.max(0, this.toastUnreadCount - 1);
                                        } else {
                                            toastItem.classList.remove('read', 'd-none');
                                            // Increment unread count
                                            this.toastUnreadCount++;
                                        }
                                        
                                        // Update badge with new count from response
                                        if (response.toast_unread_count !== undefined) {
                                            this.toastUnreadCount = response.toast_unread_count;
                                        }
                                        this.updateBadge();
                                    } catch (error) {
                                        console.error('Error updating toast read status:', error);
                                        // Revert checkbox state on error
                                        event.target.checked = !event.target.checked;
                                    }
                                });
                            });
                        }
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
                if (toastConfig.debug) console.log('[Toast Manager] History button click handler initialized');
            }

            this.initialized = true;
            if (toastConfig.debug) console.log('[Toast Manager] Initialization complete', {
                historyButtonFound: !!this.historyButton,
                historyBadgeFound: !!this.historyBadge,
                unreadCount: this.toastUnreadCount
            });
            if (toastConfig.debug) console.groupEnd();
            return true;
        },

        updateBadge(count) {
            if (!this.historyBadge) return;
            
            // Update internal count if provided
            if (typeof count === 'number') {
                this.toastUnreadCount = count;
            }
            
            if (toastConfig.debug) console.log('[Toast Manager] Updating badge with count:', this.toastUnreadCount);
            
            // Update badge text and visibility
            this.historyBadge.textContent = this.toastUnreadCount || '';
            this.historyBadge.classList.toggle('d-none', this.toastUnreadCount === 0);
            
            // Update button aria-label
            if (this.historyButton) {
                const label = `Notification History (${this.toastUnreadCount} notifications)`;
                this.historyButton.setAttribute('aria-label', label);
            }
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

            // Only increment badge count if server confirms via response
            if (toastData.toast_unread_count !== undefined) {
                this.updateBadge(toastData.toast_unread_count);
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