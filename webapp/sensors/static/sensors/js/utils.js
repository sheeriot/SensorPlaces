(function() {
    function getCookie(name) {
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
    }

    async function fetchWithCSRF(url, options = {}) {
        const csrfToken = getCookie('csrftoken');

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
                console.error(`HTTP error! status: ${response.status}`, {response});
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const contentType = response.headers.get("content-type");
            if (contentType && contentType.indexOf("application/json") !== -1) {
                return response.json();
            }
            return response;
        } catch (error) {
            console.error('Fetch error:', error);
            throw error;
        }
    }

    function formatTimestamp(date) {
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

    function setCookie(name, value, days) {
        let expires = "";
        if (days) {
            const date = new Date();
            date.setTime(date.getTime() + (days*24*60*60*1000));
            expires = "; expires=" + date.toUTCString();
        }
        document.cookie = name + "=" + (value || "")  + expires + "; path=/";
    }

    function deleteCookie(name) {
        document.cookie = name + '=; Max-Age=-99999999;';
    }

    function getNaturalTime(isoString) {
        if (!isoString) {
            return "Never";
        }
        const now = new Date();
        const past = new Date(isoString);
        const seconds = Math.floor((now - past) / 1000);

        if (seconds < 5) return "just now";
        if (seconds < 60) return `${seconds} seconds ago`;

        const minutes = Math.floor(seconds / 60);
        if (minutes < 60) return `${minutes} minute${minutes > 1 ? 's' : ''} ago`;

        const hours = Math.floor(minutes / 60);
        if (hours < 24) return `${hours} hour${hours > 1 ? 's' : ''} ago`;

        const days = Math.floor(hours / 24);
        return `${days} day${days > 1 ? 's' : ''} ago`;
    }

    function showToast(message, type = 'info', delay = 5000) {
        document.dispatchEvent(new CustomEvent('show-toast', {
            detail: {
                message: message,
                type: type,
                delay: delay
            }
        }));
    }

    // Public API
    window.utils = {
        getCookie: getCookie,
        setCookie: setCookie,
        deleteCookie: deleteCookie,
        fetchWithCSRF: fetchWithCSRF,
        formatTimestamp: formatTimestamp,
        getNaturalTime: getNaturalTime,
        showToast: showToast
    };
})();
