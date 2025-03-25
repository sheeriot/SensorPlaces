/**
 * Toast UI Manager - Shows notifications, updates badge count, handles history display
 */

const toastConfig = {
    debug: false,
    apiEndpoint: (placeSlug) => `/api/${placeSlug}/toasts/`,
};

const createToastSystem = () => {
    const system = {
        initialized: false,
        historyButton: null,
        historyBadge: null,
        toastUnreadCount: 0,
        pendingMessages: [],

        initialize() {
            if (this.initialized) return true;
            
            this.historyButton = document.getElementById('toast-history-button');
            this.historyBadge = document.getElementById('toast-history-badge');
            
            if (!this.historyButton || !this.historyBadge) return false;

            this.toastUnreadCount = window.sensorPlaces?.toastUnreadCount || 0;
            this.historyButton.addEventListener('click', this._handleHistoryButtonClick.bind(this));
            
            this.initialized = true;
            return true;
        },
        
        // Private method for handling history button click
        async _handleHistoryButtonClick(event) {
            event.preventDefault();
            const historyModal = document.getElementById('toast-history-modal');
            if (!historyModal) return;

            const placeSlug = window.sensorPlaces?.currentPlaceSlug;
            if (!placeSlug) return;

            // Setup modal reset handler
            this._setupModalResetHandler(historyModal);
            
            // Show modal
            const modal = new bootstrap.Modal(historyModal, {
                backdrop: true, keyboard: true, focus: true
            });
            modal.show();

            try {
                // Load initial history and set up event handlers
                await this.loadToastHistory(placeSlug, false);
                this._setupHistoryEventHandlers(historyModal, placeSlug);
            } catch (error) {
                console.error('Error loading toast history:', error);
                this._showHistoryError(historyModal);
            }
        },
        
        // Set up modal reset handler
        _setupModalResetHandler(historyModal) {
            const handleModalHidden = () => {
                this.historyButton.focus();
                
                // Reset content
                const historyList = historyModal.querySelector('#toastHistoryList');
                if (historyList) {
                    historyList.innerHTML = `
                        <div class="text-center text-muted py-5">
                            <i class="bi bi-hourglass-split fs-1 d-block mb-3"></i>
                            Loading notifications...
                        </div>`;
                }
                
                // Reset checkbox
                const showAllCheckbox = historyModal.querySelector('#showAllToasts');
                if (showAllCheckbox) {
                    showAllCheckbox.checked = false;
                    showAllCheckbox.parentNode.replaceChild(showAllCheckbox.cloneNode(true), showAllCheckbox);
                }
                
                // Clean up Bootstrap modal
                const backdrop = document.querySelector('.modal-backdrop');
                if (backdrop) backdrop.remove();
                
                historyModal.style.display = '';
                historyModal.classList.remove('show');
                historyModal.removeAttribute('aria-modal');
                historyModal.removeAttribute('aria-hidden');
                document.body.classList.remove('modal-open');
                document.body.style.removeProperty('padding-right');
            };

            historyModal.removeEventListener('hidden.bs.modal', handleModalHidden);
            historyModal.addEventListener('hidden.bs.modal', handleModalHidden);
        },
        
        // Set up history modal event handlers
        _setupHistoryEventHandlers(historyModal, placeSlug) {
            // Set up show all toggle
            const showAllCheckbox = historyModal.querySelector('#showAllToasts');
            if (showAllCheckbox) {
                showAllCheckbox.addEventListener('change', async (event) => {
                    await this.loadToastHistory(placeSlug, event.target.checked);
                });
            }

            // Set up mark all as read handlers
            const markAllReadBtn = historyModal.querySelector('#markAllRead');
            const confirmMarkAllReadBtn = document.querySelector('#confirmMarkAllRead');
            
            if (markAllReadBtn) {
                markAllReadBtn.addEventListener('click', () => {
                    const confirmModal = new bootstrap.Modal(document.getElementById('mark-all-read-modal'));
                    confirmModal.show();
                });
            }

            if (confirmMarkAllReadBtn) {
                confirmMarkAllReadBtn.addEventListener('click', async () => {
                    await this._markAllAsRead(placeSlug, historyModal);
                });
            }
        },
        
        // Handle marking all as read
        async _markAllAsRead(placeSlug, historyModal) {
            try {
                const response = await window.utils.fetchWithCSRF(
                    toastConfig.apiEndpoint(placeSlug),
                    { method: 'POST' }
                );

                if (response.success) {
                    // Update UI
                    const unreadItems = historyModal.querySelectorAll('[data-toast-id]:not(.read)');
                    unreadItems.forEach(item => {
                        item.classList.add('read', 'd-none');
                        const checkbox = item.querySelector('.form-check-input');
                        if (checkbox) checkbox.checked = true;
                    });

                    // Update badge count
                    this.updateBadge(0);

                    // Close modal
                    bootstrap.Modal.getInstance(document.getElementById('mark-all-read-modal')).hide();
                }
            } catch (error) {
                console.error('Error marking all as read:', error);
            }
        },
        
        // Show error in history modal
        _showHistoryError(historyModal) {
            const historyList = historyModal.querySelector('#toastHistoryList');
            if (historyList) {
                historyList.innerHTML = `
                    <div class="text-center text-danger py-5">
                        <i class="bi bi-exclamation-circle fs-1 d-block mb-3"></i>
                        Error loading notifications
                    </div>`;
            }
        },

        updateBadge(count) {
            if (!this.historyBadge) return;
            
            this.toastUnreadCount = parseInt(count, 10) || 0;
            this.historyBadge.textContent = this.toastUnreadCount || '';
            
            // Toggle visibility
            this.historyBadge.classList.toggle('d-none', this.toastUnreadCount <= 0);
            
            if (this.historyButton) {
                this.historyButton.setAttribute('aria-label', 
                    `Notification History (${this.toastUnreadCount} unread)`);
            }
        },

        show(message, type = 'success', addToHistory = true) {
            if (!this.initialized && !this.initialize()) {
                this.pendingMessages.push([message, type, addToHistory]);
                return;
            }

            const toastData = {
                message: typeof message === 'object' ? message.message : message,
                type: typeof message === 'object' ? message.type : type,
                addToHistory: typeof message === 'object' ? message.addToHistory : addToHistory,
                unread_count: typeof message === 'object' ? message.unread_count : undefined
            };

            // Update badge
            if (toastData.unread_count !== undefined) {
                this.updateBadge(toastData.unread_count);
            } else if (addToHistory) {
                this.updateBadge(this.toastUnreadCount + 1);
            }

            this._createAndShowToast(toastData);
        },
        
        // Create and display a toast notification
        _createAndShowToast(toastData) {
            // Get or create container
            let toastContainer = document.querySelector('.toast-container');
            if (!toastContainer) {
                toastContainer = document.createElement('div');
                toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
                toastContainer.style.zIndex = '1050';
                document.body.appendChild(toastContainer);
            }

            // Create toast element
            const toastEl = document.createElement('div');
            toastEl.className = `toast text-${toastData.type}`;
            toastEl.style.pointerEvents = 'auto';
            toastEl.setAttribute('role', 'alert');
            toastEl.setAttribute('aria-live', 'assertive');
            toastEl.setAttribute('aria-atomic', 'true');
            
            // Set toast content
            const iconType = this._getIconForToastType(toastData.type);
            toastEl.innerHTML = `
                <div class="d-flex align-items-center">
                    <div class="toast-body d-flex align-items-center flex-grow-1">
                        <i class="bi bi-${iconType} me-2"></i>
                        <span>${toastData.message}</span>
                    </div>
                    <button type="button" class="btn-close me-2" data-bs-dismiss="toast"></button>
                </div>
            `;

            toastContainer.insertAdjacentElement('afterbegin', toastEl);
            this._showBootstrapToast(toastEl, toastContainer);
        },
        
        // Get the appropriate icon for a toast type
        _getIconForToastType(type) {
            switch (type) {
                case 'success': return 'check-circle';
                case 'danger': return 'exclamation-circle';
                case 'warning': return 'exclamation-triangle';
                default: return 'info-circle';
            }
        },
        
        // Display a Bootstrap toast with animation
        _showBootstrapToast(toastEl, toastContainer) {
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
                
                // Add fade transition and cleanup
                toastEl.style.transition = 'opacity 0.15s linear';
                toast.show();
                
                toastEl.addEventListener('hidden.bs.toast', () => {
                    toastEl.addEventListener('transitionend', () => {
                        toastEl.remove();
                        if (!toastContainer.children.length) toastContainer.remove();
                    }, { once: true });
                    toastEl.style.opacity = '0';
                });
            });
        },

        // Load toast history
        async loadToastHistory(placeSlug, showAll = false) {
            const historyList = document.querySelector('#toastHistoryList');
            if (!historyList) return;

            try {
                const data = await window.utils.fetchWithCSRF(
                    `${toastConfig.apiEndpoint(placeSlug)}?show_all=${showAll}`
                );

                if (data.success) {
                    // Update badge
                    if (data.unread_count !== undefined) {
                        this.updateBadge(data.unread_count);
                    }

                    if (data.history.length === 0) {
                        this._showEmptyHistoryMessage(historyList);
                        return;
                    }

                    // Render history
                    this._renderHistoryItems(historyList, data.history, showAll, placeSlug);
                }
            } catch (error) {
                console.error('Error loading toast history:', error);
                this._showHistoryErrorMessage(historyList);
            }
        },
        
        // Show empty history message
        _showEmptyHistoryMessage(historyList) {
            historyList.innerHTML = `
                <div class="text-center text-muted py-5">
                    <i class="bi bi-inbox fs-1 d-block mb-3"></i>
                    No notifications
                </div>`;
        },
        
        // Show history error message
        _showHistoryErrorMessage(historyList) {
            historyList.innerHTML = `
                <div class="text-center text-danger py-5">
                    <i class="bi bi-exclamation-circle fs-1 d-block mb-3"></i>
                    Error loading notifications
                </div>`;
        },
        
        // Render history items and set up event handlers
        _renderHistoryItems(historyList, historyData, showAll, placeSlug) {
            const template = document.getElementById('toast-history-item-template');
            if (!template) {
                console.error('Toast history item template not found');
                return;
            }

            // Render history items
            const historyHtml = historyData.map(toast => {
                return this._renderSingleHistoryItem(template, toast, showAll);
            }).join('');

            historyList.innerHTML = historyHtml;
            
            // Set up event handlers
            this._setupHistoryItemHandlers(historyList, placeSlug, showAll, historyData);
        },
        
        // Render a single history item from template
        _renderSingleHistoryItem(template, toast, showAll) {
            const element = template.content.cloneNode(true);
            const container = element.querySelector('[data-toast-id]');
            
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
        },
        
        // Set up event handlers for history items
        _setupHistoryItemHandlers(historyList, placeSlug, showAll, historyData) {
            // Add event listeners to checkboxes
            historyList.querySelectorAll('.form-check-input').forEach(checkbox => {
                checkbox.addEventListener('change', async (event) => {
                    if (!event.target.checked) return; // Only handle marking as read
                    await this._markSingleToastAsRead(event.target, placeSlug, showAll);
                });
            });

            // Handle "Mark all as read" button
            const markAllReadBtn = document.getElementById('confirmMarkAllRead');
            if (markAllReadBtn) {
                markAllReadBtn.onclick = () => this._markAllHistoryAsRead(
                    historyList, placeSlug, showAll, historyData);
            }
        },
        
        // Mark a single toast as read
        async _markSingleToastAsRead(checkbox, placeSlug, showAll) {
            const toastId = parseInt(checkbox.dataset.toastId, 10);
            const toastItem = checkbox.closest('[data-toast-id]');

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
                    if (!showAll) toastItem.classList.add('d-none');
                    
                    // Update badge
                    if (response.unread_count !== undefined) {
                        this.updateBadge(response.unread_count);
                    }
                }
            } catch (error) {
                console.error('Error marking toast as read:', error);
                checkbox.checked = false;
            }
        },
        
        // Mark all history items as read
        async _markAllHistoryAsRead(historyList, placeSlug, showAll, historyData) {
            try {
                const response = await window.utils.fetchWithCSRF(
                    toastConfig.apiEndpoint(placeSlug),
                    {
                        method: 'POST',
                        body: JSON.stringify({
                            action: 'mark_read',
                            toast_ids: historyData
                                .filter(t => !t.read)
                                .map(t => t.id)
                        })
                    }
                );

                if (response.success) {
                    // Update UI
                    const unreadItems = historyList.querySelectorAll('[data-toast-id]:not(.read)');
                    unreadItems.forEach(item => {
                        item.classList.add('read');
                        if (!showAll) item.classList.add('d-none');
                        
                        const checkbox = item.querySelector('.form-check-input');
                        if (checkbox) checkbox.checked = true;
                    });

                    // Update badge
                    if (response.unread_count !== undefined) {
                        this.updateBadge(response.unread_count);
                    }

                    // Close confirmation modal
                    const confirmModal = bootstrap.Modal.getInstance(
                        document.getElementById('mark-all-read-modal'));
                    if (confirmModal) confirmModal.hide();
                }
            } catch (error) {
                console.error('Error marking all as read:', error);
            }
        }
    };

    window.toastSystem = system;
    return system;
};

// Initialize the toast system
const initializeToastSystem = () => {
    if (!window.toastSystem) createToastSystem();
    window.toastSystem.initialize();
    
    if (document.readyState === 'complete') {
        processServerToast();
    } else {
        window.addEventListener('load', processServerToast);
    }
};

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', initializeToastSystem);

// Export toast events
window.ToastEvents = {
    SHOW: 'sensors:toast:show',
    HISTORY: 'sensors:toast:history',
    CLEAR: 'sensors:toast:clear'
};

// Process server-side toast messages
const processServerToast = () => {
    const toastContainer = document.getElementById('toast-messages');
    if (!toastContainer) return;

    // Process toast messages
    const serverToastElements = toastContainer.querySelectorAll('.server-toast-message');
    
    if (serverToastElements.length === 0) {
        _processDirectToastFallback();
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
                console.error('Error processing toast:', e);
            }
        }
    });
};

// Process direct toast fallback
const _processDirectToastFallback = () => {
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
}; 