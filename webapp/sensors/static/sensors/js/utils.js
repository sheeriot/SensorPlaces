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
        const csrfToken = this.getCookie('csrftoken') || document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        
        const defaultHeaders = {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
            'X-Requested-With': 'XMLHttpRequest'
        };

        options.headers = { ...defaultHeaders, ...options.headers };

        try {
            // Return the raw response object for the caller to handle
            const response = await fetch(url, options);
            return response;
        } catch (error) {
            console.error('Fetch error:', error);
            // Re-throw the error so the calling function can handle it
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
    }
};
