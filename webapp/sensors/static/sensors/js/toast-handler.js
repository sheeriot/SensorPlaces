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
                this.updateHistoryBadge();
            }
        } catch (error) {
            console.error('Error loading toast history:', error);
        }
    },

    async saveHistory() {
        try {
            await utils.fetchWithCSRF('/api/toast-history/', {
                method: 'POST',
                body: JSON.stringify({ history: this.history })
            });
        } catch (error) {
            console.error('Error saving toast history:', error);
        }
    },

    show(message, type = 'success', addToHistory = true) {
        // Create toast data with consistent structure
        const toastData = {
            id: `toast_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
            message: typeof message === 'object' ? message.message : message,
            type: typeof message === 'object' ? message.type : type,
            timestamp: new Date().toISOString(),
            addToHistory: typeof message === 'object' ? message.addToHistory : addToHistory
        };

        // Only add to history if addToHistory is true
        if (toastData.addToHistory) {
            // Add to history
            this.history.unshift({
                ...toastData,
                timestamp: new Date(toastData.timestamp)
            });
            
            // Keep history within limit
            if (this.history.length > this.MAX_HISTORY) {
                this.history = this.history.slice(0, this.MAX_HISTORY);
            }
            
            // Save to server and update badge
            this.saveHistory();
            this.updateHistoryBadge();
        }
        
        // Create toast container if it doesn't exist
        let toastContainer = document.querySelector('.toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
            document.body.appendChild(toastContainer);
        }

        // Create and show toast
        const toastHtml = `
            <div class="toast fade show text-${toastData.type}" id="${toastData.id}">
                <div class="d-flex align-items-center">
                    <div class="toast-body d-flex align-items-center flex-grow-1" style="font-family: 'monospace';">
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
        
        const toast = new bootstrap.Toast(toastEl, {
            delay: 5000,
            autohide: true
        });
        
        toast.show();
        
        toastEl.addEventListener('hidden.bs.toast', () => {
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
            // Also update the aria-label for accessibility
            const btn = document.getElementById('toastHistoryBtn');
            if (btn) {
                btn.setAttribute('aria-label', `Notification History (${count} notifications)`);
            }
        }
    },

    showHistory() {
        const modalHtml = `
            <div class="modal fade" id="toastHistoryModal" tabindex="-1">
                <div class="modal-dialog modal-xl">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Notification History</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
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
                                            <div class="toast-history-time font-monospace text-muted" style="font-size: 0.75em;">
                                                ${dateStr} ${timeStr} ${shortTZ} UTC${offsetString}
                                            </div>
                                            <div class="text-${toast.type} font-monospace">
                                                ${toast.message}
                                            </div>
                                        </div>
                                    `;
                                }).join('')}
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                            <button type="button" class="btn btn-danger" onclick="toastSystem.clearHistory()">Clear History</button>
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
        try {
            await utils.fetchWithCSRF('/api/toast-history/', { method: 'DELETE' });
            this.history = [];
            this.updateHistoryBadge();
            bootstrap.Modal.getInstance(document.getElementById('toastHistoryModal'))?.hide();
        } catch (error) {
            console.error('Error clearing toast history:', error);
        }
    }
};

// Initialize toast system when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize toast system
    toastSystem.loadHistory();
    
    // Set up toast history button click handler
    const toastHistoryBtn = document.getElementById('toastHistoryBtn');
    if (toastHistoryBtn) {
        toastHistoryBtn.addEventListener('click', () => toastSystem.showHistory());
    }

    // Process any toast message from Django context
    const toastMessageEl = document.getElementById('toast-message');
    if (toastMessageEl) {
        try {
            const toastMessage = JSON.parse(toastMessageEl.textContent);
            toastSystem.show(toastMessage);
        } catch (e) {
            console.error('Error processing toast message:', e);
        }
    }

    // Convert any Django messages to toasts
    document.querySelectorAll('.alert:not(.processed)').forEach(message => {
        const type = message.classList.contains('alert-success') ? 'success' :
                    message.classList.contains('alert-warning') ? 'warning' :
                    message.classList.contains('alert-danger') ? 'danger' : 'info';
        
        const messageText = message.childNodes[0]?.textContent.trim() || 
                          message.textContent.trim();
        
        if (messageText) {
            message.classList.add('processed');
            message.remove();
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