/**
 * Toast UI Manager
 * 
 * Manages the UI components of the toast notification system:
 * - Displays toast notifications
 * - Updates notification badge count
 * - Shows history modal and loads history from backend
 * 
 * Note: Actual history storage is managed by the backend ToastHistoryView
 */

// System Configuration
const toastConfig = {
    debug: true,          // Set to true to enable debug mode
    maxHistory: 50,       // Maximum items to show in history view
    maxAge: 24 * 60 * 60 * 1000  // Maximum age of history items to show
};

// Debug logging helper
function debugLog(message, data = null) {
    if (!toastConfig.debug) return;
    if (data) {
        console.debug(message, data);
    } else {
        console.debug(message);
    }
}

// Toast UI Manager
const toastSystem = {
    history: [],          // Local cache of history for badge/modal
    MAX_HISTORY: toastConfig.maxHistory,
    initialized: false,
    historyLoading: null,
    historyButton: null,
    historyBadge: null,

    async initialize() {
        if (this.initialized) return;
        
        debugLog('Initializing toast system');

        // Initialize history button and badge references once
        this.historyButton = document.getElementById('toastHistoryBtn');
        this.historyBadge = document.getElementById('toastHistoryBadge');
        
        if (this.historyButton && !this.historyButton.hasAttribute('data-toast-initialized')) {
            this.historyButton.setAttribute('data-toast-initialized', 'true');
            this.historyButton.addEventListener('click', () => this.showHistory(), { once: false });
            debugLog('History button initialized');
        }

        await this.loadHistory();
        this.initialized = true;
        debugLog('Toast system initialized');
    },

    async loadHistory() {
        // If history is already loading, wait for it
        if (this.historyLoading) {
            debugLog('History already loading, waiting...');
            return this.historyLoading;
        }

        // If history is already loaded, just return
        if (this.history.length > 0) {
            debugLog('History already loaded');
            return Promise.resolve();
        }

        debugLog('Loading toast history');
        try {
            this.historyLoading = utils.fetchWithCSRF('/api/toast-history/');
            const response = await this.historyLoading;
            const data = await response.json();
            
            if (data.history) {
                // Filter out old messages and convert timestamps
                const now = new Date();
                this.history = data.history
                    .map(item => ({
                        ...item,
                        timestamp: new Date(item.timestamp)
                    }))
                    .filter(item => {
                        const age = now - item.timestamp;
                        return age < toastConfig.maxAge;
                    });

                if (toastConfig.debug) {
                    debugLog('History loaded', this.history);
                }
                this.updateHistoryBadge();
                
                // If we filtered out old messages, save the cleaned history
                if (this.history.length < data.history.length) {
                    this.saveHistory();
                }
            }
        } catch (error) {
            console.error('Failed to load toast history:', error);
        } finally {
            this.historyLoading = null;
        }
    },

    async saveHistory() {
        try {
            // Clean history before saving
            this.cleanHistory();
            await utils.fetchWithCSRF('/api/toast-history/', {
                method: 'POST',
                body: JSON.stringify({ history: this.history })
            });
        } catch (error) {
            console.error('Failed to save toast history:', error);
        }
    },

    cleanHistory() {
        const now = new Date();
        this.history = this.history
            .filter(item => {
                const age = now - item.timestamp;
                return age < toastConfig.maxAge;
            })
            .slice(0, this.MAX_HISTORY);
        this.updateHistoryBadge();
    },

    updateHistoryBadge() {
        if (!this.historyBadge) {
            this.historyBadge = document.getElementById('toastHistoryBadge');
        }
        
        if (this.historyBadge) {
            const count = this.history.length;
            this.historyBadge.textContent = count || '';
            this.historyBadge.classList.toggle('d-none', count === 0);
            
            if (this.historyButton) {
                this.historyButton.setAttribute('aria-label', `Notification History (${count} notifications)`);
            }
            
            debugLog('History badge updated', { count });
        }
    },

    show(message, type = 'success', addToHistory = true) {
        // Clean old toasts first
        this.cleanHistory();

        // Create toast data
        const toastData = {
            id: `toast_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
            message: typeof message === 'object' ? message.message : message,
            type: typeof message === 'object' ? message.type : type,
            timestamp: new Date().toISOString(),
            addToHistory: typeof message === 'object' ? message.addToHistory : addToHistory
        };

        debugLog('New Toast:', toastData);

        if (toastData.addToHistory) {
            this.history.unshift({
                ...toastData,
                timestamp: new Date(toastData.timestamp)
            });
            
            if (this.history.length > this.MAX_HISTORY) {
                this.history.splice(this.MAX_HISTORY);
            }
            
            this.saveHistory();
            this.updateHistoryBadge();
        }
        
        // Create or get toast container
        let toastContainer = document.querySelector('.toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.className = 'toast-container';  // Let CSS handle positioning
            document.body.appendChild(toastContainer);
        }

        // Remove old toasts if there are too many visible
        const visibleToasts = toastContainer.children;
        if (visibleToasts.length > 5) {
            Array.from(visibleToasts)
                .slice(3) // Keep the newest 3
                .forEach(toast => {
                    const bsToast = bootstrap.Toast.getInstance(toast);
                    if (bsToast) bsToast.dispose();
                    toast.remove();
                });
        }

        // Create and show toast
        const toastHtml = `
            <div class="toast showing text-${toastData.type}" id="${toastData.id}">
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
            </div>
        `;

        toastContainer.insertAdjacentHTML('afterbegin', toastHtml);
        const toastEl = document.getElementById(toastData.id);
        
        // Allow DOM to process the new element
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                toastEl.classList.remove('showing');
            });
        });

        const toast = new bootstrap.Toast(toastEl, {
            delay: 5000,
            autohide: true
        });
        
        toast.show();
        
        toastEl.addEventListener('hide.bs.toast', () => {
            toastEl.classList.add('hiding');
        });

        toastEl.addEventListener('hidden.bs.toast', () => {
            debugLog('Lifecycle', `Toast removed: ${toastData.id}`);
            toastEl.remove();
            // Remove toast container if it's empty
            if (!toastContainer.children.length) {
                toastContainer.remove();
            }
        });
    },

    showHistory() {
        debugLog('History', 'Showing history modal', {
            itemCount: this.history.length
        });

        const modalHtml = `
            <div class="modal fade" id="toastHistoryModal" tabindex="-1">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">
                                <i class="bi bi-clock-history me-2"></i>Notification History
                            </h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body px-4 py-3">
                            <div class="toast-history-list">
                                ${this.history.map(toast => {
                                    const timestamp = new Date(toast.timestamp);
                                    const dateStr = timestamp.toLocaleString('en-US', {
                                        year: 'numeric',
                                        month: '2-digit',
                                        day: '2-digit'
                                    });
                                    const timeStr = timestamp.toLocaleString('en-US', {
                                        hour: '2-digit',
                                        minute: '2-digit',
                                        second: '2-digit',
                                        hour12: false
                                    });
                                    const shortTZ = new Intl.DateTimeFormat('en', { timeZoneName: 'short' })
                                        .formatToParts(timestamp)
                                        .find(part => part.type === 'timeZoneName')?.value || '';
                                    const offset = -timestamp.getTimezoneOffset();
                                    const offsetHours = Math.floor(Math.abs(offset) / 60);
                                    const offsetMinutes = Math.abs(offset) % 60;
                                    const offsetString = `${offset >= 0 ? '+' : '-'}${String(offsetHours).padStart(2, '0')}${String(offsetMinutes).padStart(2, '0')}`;
                                    
                                    return `
                                        <div class="toast-history-item mb-3">
                                            <div class="toast-history-time font-monospace text-muted mb-1" style="font-size: 0.75em;">
                                                ${dateStr} ${timeStr} ${shortTZ} UTC${offsetString}
                                            </div>
                                            <div class="text-${toast.type} p-2 rounded shadow-sm">
                                                <div class="d-flex align-items-center">
                                                    <i class="bi bi-${
                                                        toast.type === 'success' ? 'check-circle' : 
                                                        toast.type === 'danger' ? 'exclamation-circle' :
                                                        toast.type === 'warning' ? 'exclamation-triangle' : 
                                                        'info-circle'
                                                    } me-2"></i>
                                                    <span>${toast.message}</span>
                                                </div>
                                            </div>
                                        </div>
                                    `;
                                }).join('')}
                            </div>
                            ${!this.history.length ? `
                                <div class="text-center text-muted py-5">
                                    <i class="bi bi-inbox fs-1 d-block mb-3"></i>
                                    No notifications yet
                                </div>
                            ` : ''}
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Close</button>
                            ${this.history.length ? `
                                <button type="button" class="btn btn-outline-danger" onclick="toastSystem.clearHistory()">
                                    <i class="bi bi-trash me-2"></i>Clear History
                                </button>
                            ` : ''}
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.getElementById('toastHistoryModal')?.remove();
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        new bootstrap.Modal(document.getElementById('toastHistoryModal')).show();
    },

    async clearHistory() {
        debugLog('History', 'Clearing toast history');
        try {
            await utils.fetchWithCSRF('/api/toast-history/', { method: 'DELETE' });
            this.history = [];
            this.updateHistoryBadge();
            bootstrap.Modal.getInstance(document.getElementById('toastHistoryModal'))?.hide();
            debugLog('History', 'History cleared successfully');
        } catch (error) {
            console.error('Error clearing toast history:', error);
        }
    }
};

// Initialize toast system when DOM is loaded - ensure single initialization
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => toastSystem.initialize(), { once: true });
} else {
    toastSystem.initialize();
}

// Export for use in other modules
window.toastSystem = toastSystem;
window.showToast = function(message, type = 'info') {
    toastSystem.show({
        message: message,
        type: type,
        addToHistory: true
    });
}; 