// Utility Functions
const utils = {
    getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    },

    getCSRFToken() {
        // First try to get from cookie
        let token = this.getCookie('csrftoken');
        
        // If not in cookie, try to get from meta tag
        if (!token) {
            const csrfInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
            if (csrfInput) {
                token = csrfInput.value;
            }
        }
        
        return token;
    },

    async fetchWithCSRF(url, options = {}) {
        const defaultOptions = {
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json'
            },
            cache: 'no-store'
        };

        // Only require CSRF token for state-modifying methods
        const method = (options.method || 'GET').toUpperCase();
        const requiresCSRF = !['GET', 'HEAD', 'OPTIONS', 'TRACE'].includes(method);

        if (requiresCSRF) {
            const csrfToken = this.getCSRFToken();
            if (!csrfToken) {
                console.error('CSRF token not found in cookies or meta tag');
                throw new Error('CSRF token not found. Please refresh the page.');
            }
            defaultOptions.headers['X-CSRFToken'] = csrfToken;
        }

        // Properly merge headers
        const mergedOptions = {
            ...defaultOptions,
            ...options,
            headers: {
                ...defaultOptions.headers,
                ...(options.headers || {})
            }
        };
        
        // Ensure URL doesn't start with double slashes
        url = url.replace(/^\/+/, '/');
        
        try {
            const response = await fetch(url, mergedOptions);
            
            // Parse JSON response
            const data = await response.json();
            
            // Handle toast messages from API response
            if (data.toast) {
                if (window.toastSystem) {
                    window.toastSystem.show({
                        message: data.toast.message || data.toast,
                        type: data.toast.type || 'info',
                        addToHistory: true
                    });
                }
            }

            // Handle CSRF errors
            if (response.status === 403) {
                if (data.detail && data.detail.includes('CSRF')) {
                    throw new Error('CSRF validation failed. Please refresh the page and try again.');
                }
            }

            // Handle other error responses
            if (!response.ok) {
                // Show error toast if there isn't already a toast message
                if (!data.toast && window.toastSystem) {
                    window.toastSystem.show({
                        message: data.detail || 'An error occurred while processing your request.',
                        type: 'danger',
                        addToHistory: true
                    });
                }
                throw new Error(data.detail || 'Request failed');
            }

            return data;
        } catch (error) {
            console.error('Error in fetchWithCSRF:', error);
            
            // Show error toast for network/parsing errors
            if (window.toastSystem) {
                window.toastSystem.show({
                    message: error.message || 'A network error occurred. Please try again.',
                    type: 'danger',
                    addToHistory: true
                });
            }
            throw error;
        }
    }
};

// Export for use in other modules
window.utils = utils; 