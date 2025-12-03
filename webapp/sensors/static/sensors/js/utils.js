window.utils = {
    getCookie: function(name) {
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

    fetchWithCSRF: async function(url, options = {}) {
        const csrfToken = this.getCookie('csrftoken');

        const defaultHeaders = {
            'X-CSRFToken': csrfToken,
            'X-Requested-With': 'XMLHttpRequest'
        };

        if (!(options.body instanceof FormData)) {
            defaultHeaders['Content-Type'] = 'application/json';
        }

        options.headers = { ...defaultHeaders, ...options.headers };

        try {
            const response = await fetch(url, options);
            if (!response.ok) {
                // For HTTP errors, log them and throw to be caught by the caller
                console.error(`HTTP error! status: ${response.status}`, {response});
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            // Check if the response is JSON before trying to parse it.
            const contentType = response.headers.get("content-type");
            if (contentType && contentType.indexOf("application/json") !== -1) {
                return response.json();
            }
            return response;
        } catch (error) {
            console.error('Fetch error:', error);
            throw error;
        }
    },

    formatTimestamp: function(date) {
        const d = (date instanceof Date) ? date : new Date(date);
        if (isNaN(d)) {
            return 'Invalid Date';
        }

        const year = d.getFullYear();
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        const dateStr = `${year}/${month}/${day}`;

        const timeStr = d.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
        });

        const shortTZ = new Intl.DateTimeFormat('en', { timeZoneName: 'short' })
            .formatToParts(d)
            .find(part => part.type === 'timeZoneName')?.value || '';

        const offset = -d.getTimezoneOffset();
        const offsetHours = Math.floor(Math.abs(offset) / 60);
        const offsetMinutes = Math.abs(offset) % 60;
        const offsetString = `${offset >= 0 ? '+' : '-'}${String(offsetHours).padStart(2, '0')}${String(offsetMinutes).padStart(2, '0')}`;

        return `${dateStr} ${timeStr} ${offsetString} (${shortTZ})`;
    },

    getNaturalTime: function(date) {
        if (!date) return '';

        const now = new Date();
        const seconds = Math.round((now - date) / 1000);

        if (seconds < 5) {
            return "just now";
        } else if (seconds < 60) {
            return `${seconds} seconds ago`;
        }

        const minutes = Math.round(seconds / 60);
        if (minutes < 60) {
            return minutes === 1 ? "a minute ago" : `${minutes} minutes ago`;
        }

        const hours = Math.round(minutes / 60);
        if (hours < 24) {
            return hours === 1 ? "an hour ago" : `${hours} hours ago`;
        }

        const days = Math.round(hours / 24);
        return days === 1 ? "yesterday" : `${days} days ago`;
    }
};
