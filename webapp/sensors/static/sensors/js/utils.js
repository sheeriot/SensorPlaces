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

    function formatTimestamp(timestamp, short = false) {
        if (!timestamp) return 'N/A';

        const date = new Date(timestamp);
        const userTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
        const tzShort = date.toLocaleDateString(undefined, { day:'2-digit', timeZoneName: 'short' }).substring(4);

        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        const hours = String(date.getHours()).padStart(2, '0');
        const minutes = String(date.getMinutes()).padStart(2, '0');
        const seconds = String(date.getSeconds()).padStart(2, '0');

        // Get timezone offset in +/-HHMM format
        const offset = -date.getTimezoneOffset();
        const offsetSign = offset >= 0 ? '+' : '-';
        const offsetHours = String(Math.floor(Math.abs(offset) / 60)).padStart(2, '0');
        const offsetMinutes = String(Math.abs(offset) % 60).padStart(2, '0');
        const tzOffset = `${offsetSign}${offsetHours}${offsetMinutes}`;

        if (short) {
            return `${year}/${month}/${day} ${hours}:${minutes}`;
        }

        return `${year}/${month}/${day} ${hours}:${minutes}:${seconds} ${tzOffset} (${tzShort})`;
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
