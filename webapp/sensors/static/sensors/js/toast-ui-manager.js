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
    debug: false,  // Set to false in production
    apiEndpoint: (placeSlug) => `/api/${placeSlug}/toasts/`,
};

// Create and initialize the system
const createToastSystem = () => {
    const system = {
        initialized: false,
        historyButton: null,
        historyBadge: null,
        toastUnreadCount: 0,
        pendingMessages: [],

        initialize() {
            if (this.initialized) {
                return true;
            }
            
            // Get DOM elements
            this.historyButton = document.getElementById('toast-history-button');
            this.historyBadge = document.getElementById('toast-history-badge');
            
            if (!this.historyButton || !this.historyBadge) {
                return false;
            }

            // Get initial count from global state
            this.toastUnreadCount = window.sensorPlaces?.toastUnreadCount || 0;
            
            // Set up click handler for history button
            this.historyButton.addEventListener('click', async (event) => {
                event.preventDefault();

                // Find history modal
                let historyModal = document.getElementById('toast-history-modal');
                if (!historyModal) {
                    return;
                }

                // Get place slug from global state
                const placeSlug = window.sensorPlaces?.currentPlaceSlug;
                if (!placeSlug) {
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
            return true;
        },

        updateBadge(count) {
            if (!this.historyBadge) {
                return;
            }
            
            // Ensure count is a number
            this.toastUnreadCount = parseInt(count, 10) || 0;
            
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

        show(message, type = 'success', addToHistory = true) {
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
            toastEl.className = `toast text-${toastData.type}`;
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
                    console.error('Bootstrap not loaded!');
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
                        console.error('Toast history item template not found');
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
    return system;
};

// Initialize the toast system
const initializeToastSystem = () => {
    if (!window.toastSystem) {
        createToastSystem();
    }

    const initResult = window.toastSystem.initialize();
    
    if (document.readyState === 'complete') {
        processServerToast();
    } else {
        window.addEventListener('load', processServerToast);
    }
};

// Ensure proper initialization sequence
document.addEventListener('DOMContentLoaded', () => {
    initializeToastSystem();
});

// Export toast events for other modules
window.ToastEvents = {
    SHOW: 'sensors:toast:show',
    HISTORY: 'sensors:toast:history',
    CLEAR: 'sensors:toast:clear'
};

// Process server-side toast messages
const processServerToast = () => {
    const toastContainer = document.getElementById('toast-messages');
    if (!toastContainer) {
        return;
    }

    // Process all server toast messages
    const serverToastElements = toastContainer.querySelectorAll('.server-toast-message');
    
    if (serverToastElements.length === 0) {
        // Check for direct toast data - as an emergency fallback
        const directToast = document.getElementById('direct-toast-fallback');
        if (directToast && directToast.querySelector('script')) {
            try {
                const directScript = directToast.querySelector('script');
                const directData = JSON.parse(directScript.textContent);
                if (window.toastSystem && typeof window.toastSystem.show === 'function') {
                    window.toastSystem.show(directData);
                } else if (window.showToast) {
                    window.showToast(directData.message, directData.type);
                }
            } catch (e) {
                console.error('Error processing direct toast:', e);
            }
        }
        return;
    }

    // Process all server toast messages
    Array.from(serverToastElements).forEach((toastMessage, index) => {
        if (toastMessage.getAttribute('data-processed') === 'true') return;

        const toastScript = toastMessage.querySelector('script');
        if (toastScript && window.toastSystem) {
            try {
                const toastData = JSON.parse(toastScript.textContent);
                toastData.addToHistory = false;  // Badge count is already in template
                
                // Add a slight delay between toasts
                setTimeout(() => {
                    if (window.toastSystem && typeof window.toastSystem.show === 'function') {
                        window.toastSystem.show(toastData);
                    } else if (window.showToast) {
                        window.showToast(toastData.message, toastData.type);
                    }
                }, index * 300);
                
                toastMessage.setAttribute('data-processed', 'true');
            } catch (e) {
                console.error('Error processing toast:', e, toastScript.textContent);
            }
        }
    });
}; 