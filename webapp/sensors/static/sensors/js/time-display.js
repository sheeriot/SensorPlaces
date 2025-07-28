// Time Display System Configuration
const timeDisplayConfig = {
    debug: false
};

// // Initialize debug mode from URL parameter
// const urlParams = new URLSearchParams(window.location.search);
// if (urlParams.get('debug') === 'true') {
//     timeDisplayConfig.debug = true;
// }

// Time Display System
const timeDisplay = {
    themes: {
        morning: { color: '#FF8C00' },     // 5-11
        afternoon: { color: '#000000' },   // 11-17
        evening: { color: '#4B0082' },     // 17-21
        night: { color: '#1E4B9C' }       // 21-5
    },

    update() {
        const timeSpan = document.getElementById('localTime');
        if (!timeSpan) {
            if (timeDisplayConfig.debug) console.log('Time display element not found');
            return;
        }

        if (timeDisplayConfig.debug) console.log('Updating time display...');
        
        const now = new Date();
        const hour = now.getHours();
        
        // Set color based on time of day
        const newColor = hour >= 5 && hour < 11 ? this.themes.morning.color :
                        hour >= 11 && hour < 17 ? this.themes.afternoon.color :
                        hour >= 17 && hour < 21 ? this.themes.evening.color :
                        this.themes.night.color;
        
        if (timeDisplayConfig.debug) {
            console.log(`Updating time display color for hour ${hour} to ${newColor}`);
        }
        
        timeSpan.style.color = newColor;

        // Format date in YYYY/MM/DD format
        const year = now.getFullYear();
        const month = String(now.getMonth() + 1).padStart(2, '0');
        const day = String(now.getDate()).padStart(2, '0');
        const dateStr = `${year}/${month}/${day}`;
        
        const timeStr = now.toLocaleString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
        });

        // Get timezone info
        const shortTZ = new Intl.DateTimeFormat('en', { timeZoneName: 'short' })
            .formatToParts(now)
            .find(part => part.type === 'timeZoneName')?.value || '';

        // Get offset in compact format
        const offset = -now.getTimezoneOffset();
        const offsetHours = Math.floor(Math.abs(offset) / 60);
        const offsetMinutes = Math.abs(offset) % 60;
        const offsetString = `${offset >= 0 ? '+' : '-'}${String(offsetHours).padStart(2, '0')}${String(offsetMinutes).padStart(2, '0')}`;
        
        const displayString = `<small>${dateStr} ${timeStr} ${offsetString} (${shortTZ})</small>`;
        if (timeDisplayConfig.debug) {
            console.log('Updating time display with:', displayString);
        }
        
        // Update display with compact format
        timeSpan.innerHTML = displayString;
        
        // Update tooltip with full details
        const isoTime = now.toISOString();
        const unixTime = Math.floor(now.getTime() / 1000);
        const fullTimeString = now.toLocaleString('en-US', {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false,
            timeZoneName: 'long'
        });
        
        const tooltipContent = `${fullTimeString}\nISO: ${isoTime}\nUNIX: ${unixTime}\nClick to copy current timestamp`;
        if (timeDisplayConfig.debug) {
            console.log('Updating tooltip content:', tooltipContent);
        }
        
        timeSpan.setAttribute('data-bs-title', tooltipContent);
    },

    initializeTimestampCopy() {
        const timeSpan = document.getElementById('localTime');
        if (!timeSpan) {
            if (timeDisplayConfig.debug) {
                console.log('Cannot initialize timestamp copy - element not found');
            }
            return;
        }

        if (timeDisplayConfig.debug) {
            console.log('Initializing timestamp copy functionality');
        }

        timeSpan.addEventListener('click', function() {
            const now = new Date();
            const isoString = now.toISOString();
            
            if (timeDisplayConfig.debug) {
                console.log('Copying timestamp to clipboard:', isoString);
            }

            navigator.clipboard.writeText(isoString).then(() => {
                const tooltip = bootstrap.Tooltip.getInstance(this);
                const originalTitle = this.getAttribute('data-bs-title');
                
                if (timeDisplayConfig.debug) {
                    console.log('Timestamp copied, showing confirmation');
                }

                tooltip.setContent({ '.tooltip-inner': 'Copied!' });
                setTimeout(() => {
                    tooltip.setContent({ '.tooltip-inner': originalTitle });
                    if (timeDisplayConfig.debug) {
                        console.log('Resetting tooltip content');
                    }
                }, 1000);
            });
        });
    }
};

// Function to send timezone to backend
function sendTimezoneToServer() {
    if (sessionStorage.getItem('timezoneSet')) {
        if (timeDisplayConfig.debug) console.log('Timezone already set in this session.');
        return;
    }

    const userTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (timeDisplayConfig.debug) console.log('Detected timezone:', userTimezone);

    fetch('/api/set-timezone/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({ timezone: userTimezone })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'ok') {
            sessionStorage.setItem('timezoneSet', 'true');
            if (timeDisplayConfig.debug) console.log('Timezone successfully set on server.');
        } else {
            if (timeDisplayConfig.debug) console.error('Failed to set timezone on server:', data.message);
        }
    })
    .catch(error => {
        if (timeDisplayConfig.debug) console.error('Error sending timezone to server:', error);
    });
}

// Helper function to get CSRF token
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


// Initialize time display when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    if (timeDisplayConfig.debug) console.log('Initializing time display system');
    
    // Send timezone to server
    sendTimezoneToServer();

    // Initialize the tooltip
    const timeSpan = document.getElementById('localTime');
    if (timeSpan) {
        new bootstrap.Tooltip(timeSpan);
        if (timeDisplayConfig.debug) {
            console.log('Time display tooltip initialized');
        }
    }
    
    // Start the time display system
    timeDisplay.update();
    setInterval(() => timeDisplay.update(), 1000);
    timeDisplay.initializeTimestampCopy();
}); 