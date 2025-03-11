// System Configuration
const utilsConfig = {
    debug: true,  // Set to true to enable debug mode
    logCSRF: true,
    logFetch: true,
    logToasts: true
};

// Utility Functions
const utils = {
    getCookie(name) {
        if (utilsConfig.debug && utilsConfig.logCSRF) {
            console.group('getCookie');
            console.log('Looking for cookie:', name);
        }

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

        if (utilsConfig.debug && utilsConfig.logCSRF) {
            console.log('Cookie value found:', cookieValue);
            console.groupEnd();
        }
        return cookieValue;
    },

    getCSRFToken() {
        if (utilsConfig.debug && utilsConfig.logCSRF) {
            console.group('getCSRFToken');
        }
        
        // First try to get from cookie
        let token = this.getCookie('csrftoken');
        
        // If not in cookie, try to get from meta tag
        if (!token) {
            if (utilsConfig.debug && utilsConfig.logCSRF) {
                console.log('Token not found in cookie, checking meta tag');
            }
            const csrfInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
            if (csrfInput) {
                token = csrfInput.value;
            }
        }
        
        if (utilsConfig.debug && utilsConfig.logCSRF) {
            console.log('Final CSRF token:', token ? 'Found' : 'Not found');
            console.groupEnd();
        }
        return token;
    },

    async fetchWithCSRF(url, options = {}) {
        if (utilsConfig.debug && utilsConfig.logFetch) {
            console.group('fetchWithCSRF');
            console.log('Request:', {
                url,
                options
            });
        }

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
                const error = new Error('CSRF token not found in cookies or meta tag');
                if (utilsConfig.debug && utilsConfig.logFetch) {
                    console.error('CSRF Error:', error);
                    console.groupEnd();
                }
                throw error;
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

        if (utilsConfig.debug && utilsConfig.logFetch) {
            console.log('Merged request options:', mergedOptions);
        }
        
        // Ensure URL doesn't start with double slashes
        url = url.replace(/^\/+/, '/');
        
        try {
            if (utilsConfig.debug && utilsConfig.logFetch) {
                console.log('Sending fetch request to:', url);
            }

            const response = await fetch(url, mergedOptions);
            
            if (utilsConfig.debug && utilsConfig.logFetch) {
                console.log('Response received:', {
                    status: response.status,
                    statusText: response.statusText,
                    headers: Object.fromEntries(response.headers.entries())
                });
            }

            // Check content type
            const contentType = response.headers.get('content-type');
            if (utilsConfig.debug && utilsConfig.logFetch) {
                console.log('Response content type:', contentType);
            }

            if (!contentType || !contentType.includes('application/json')) {
                const error = new Error('Invalid response format - expected JSON');
                if (utilsConfig.debug && utilsConfig.logFetch) {
                    console.error('Content Type Error:', error);
                    console.groupEnd();
                }
                throw error;
            }

            // Parse JSON response
            const data = await response.json();
            
            if (utilsConfig.debug && utilsConfig.logFetch) {
                console.log('Parsed response data:', data);
            }

            // Handle toast messages from API response
            if (data.toast || (data.success && data.message)) {
                if (utilsConfig.debug && utilsConfig.logToasts) {
                    console.log('Processing API response for toast:', {
                        hasToast: !!data.toast,
                        message: data.message,
                        type: data.type
                    });
                }

                // Use server's toast config or create minimal one from message
                const toastData = data.toast || {
                    message: data.message,
                    type: data.type || (data.message.toLowerCase().includes('deactivated') ? 'warning' : 'success')
                };

                // Always set addToHistory true for API calls
                toastData.addToHistory = toastData.addToHistory ?? true;

                if (utilsConfig.debug && utilsConfig.logToasts) {
                    console.log('Showing toast message:', toastData);
                }

                if (window.toastSystem) {
                    window.toastSystem.show(toastData);
                } else if (utilsConfig.debug && utilsConfig.logToasts) {
                    console.warn('Toast system not available');
                }
            }

            // Handle CSRF errors
            if (response.status === 403) {
                if (data.detail && data.detail.includes('CSRF')) {
                    const error = new Error('CSRF validation failed. Please refresh the page and try again.');
                    if (utilsConfig.debug && utilsConfig.logFetch) {
                        console.error('CSRF Validation Error:', error);
                        console.groupEnd();
                    }
                    throw error;
                }
            }

            // Handle other error responses
            if (!response.ok) {
                // Show error toast if there isn't already a toast message
                if (!data.toast && window.toastSystem) {
                    if (utilsConfig.debug && utilsConfig.logToasts) {
                        console.log('Showing error toast for non-OK response');
                    }
                    window.toastSystem.show({
                        message: data.detail || 'An error occurred while processing your request.',
                        type: 'danger',
                        addToHistory: true
                    });
                }
                const error = new Error(data.detail || 'Request failed');
                if (utilsConfig.debug && utilsConfig.logFetch) {
                    console.error('Response Error:', error);
                    console.groupEnd();
                }
                throw error;
            }

            if (utilsConfig.debug && utilsConfig.logFetch) {
                console.log('Request completed successfully');
                console.groupEnd();
            }
            return data;

        } catch (error) {
            if (utilsConfig.debug && utilsConfig.logFetch) {
                console.error('Fetch Error:', {
                    message: error.message,
                    stack: error.stack
                });
                console.groupEnd();
            }
            
            // Show error toast for network/parsing errors
            if (window.toastSystem) {
                if (utilsConfig.debug && utilsConfig.logToasts) {
                    console.log('Showing error toast for fetch error');
                }
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

if (utilsConfig.debug) {
    console.log('Utils module loaded', {
        version: '1.0',
        debug: utilsConfig.debug,
        features: {
            csrf: utilsConfig.logCSRF,
            fetch: utilsConfig.logFetch,
            toasts: utilsConfig.logToasts
        }
    });
}