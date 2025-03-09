/**
 * Toast System
 * 
 * Manages toast notifications and history for the application
 * 
 * Configuration:
 * -------------
 * To enable debugging, set debug: true in toastConfig below
 * Debug mode will:
 * - Show toast lifecycle events
 * - Log history operations
 * - Display API interactions
 */

// System Configuration
const toastConfig = {
    debug: false           // Set to true to enable debug mode
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

// Toast System
const toastSystem = {
    history: [],
    MAX_HISTORY: 50,

    async loadHistory() {
        try {
            const response = await utils.fetchWithCSRF('/api/toast-history/');
            const data = await response.json();
            if (data.history) {
                this.history = data.history.map(item => ({
                    ...item,
                    timestamp: new Date(item.timestamp)
                }));
                if (toastConfig.debug) {
                    console.table(this.history);
                }
                this.updateHistoryBadge();
            }
        } catch (error) {
            console.error('Failed to load toast history:', error);
        }
    },

    async saveHistory() {
        try {
            await utils.fetchWithCSRF('/api/toast-history/', {
                method: 'POST',
                body: JSON.stringify({ history: this.history })
            });
        } catch (error) {
            console.error('Failed to save toast history:', error);
        }
    },

    show(message, type = 'success', addToHistory = true) {
        // Create toast data
        const toastData = {
            id: `toast_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
            message: typeof message === 'object' ? message.message : message,
            type: typeof message === 'object' ? message.type : type,
            timestamp: new Date().toISOString(),
            addToHistory: typeof message === 'object' ? message.addToHistory : addToHistory
        };

        if (toastConfig.debug) {
            debugLog('New Toast:', toastData);
        }

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
        
        // Create toast container if needed
        let toastContainer = document.querySelector('.toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
            document.body.appendChild(toastContainer);
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

    updateHistoryBadge() {
        const badge = document.getElementById('toastHistoryBadge');
        if (badge) {
            const count = this.history.length;
            badge.textContent = count || '';
            badge.classList.toggle('d-none', count === 0);
            const btn = document.getElementById('toastHistoryBtn');
            if (btn) {
                btn.setAttribute('aria-label', `Notification History (${count} notifications)`);
            }
        }
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

// Initialize toast system when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    toastSystem.loadHistory();
    
    const toastHistoryBtn = document.getElementById('toastHistoryBtn');
    if (toastHistoryBtn) {
        toastHistoryBtn.addEventListener('click', () => toastSystem.showHistory());
    }

    // Process Django messages
    const toastMessageEl = document.getElementById('toast-message');
    if (toastMessageEl) {
        try {
            const toastMessage = JSON.parse(toastMessageEl.textContent);
            toastSystem.show(toastMessage);
        } catch (e) {
            console.error('Error processing toast message:', e);
        }
    }

    // Convert Django alerts to toasts (excluding static alerts)
    const messages = document.querySelectorAll('.alert:not([data-static="true"]):not(.processed)');
    messages.forEach(message => {
        const type = message.classList.contains('alert-success') ? 'success' :
                    message.classList.contains('alert-warning') ? 'warning' :
                    message.classList.contains('alert-danger') ? 'danger' : 'info';
        
        const messageText = message.childNodes[0]?.textContent.trim() || 
                          message.textContent.trim();
        
        if (messageText) {
            message.style.opacity = '0';  // Fade out
            message.classList.add('processed');
            setTimeout(() => message.remove(), 150);  // Remove after fade
            toastSystem.show(messageText, type);
        }
    });
});

// Export for use in other modules
window.toastSystem = toastSystem;
window.showToast = function(message, type = 'info') {
    toastSystem.show({
        message: message,
        type: type,
        addToHistory: true
    });
}; 