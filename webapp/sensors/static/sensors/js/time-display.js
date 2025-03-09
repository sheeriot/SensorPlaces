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
        if (!timeSpan) return;

        const now = new Date();
        const hour = now.getHours();
        
        // Set color based on time of day
        timeSpan.style.color = 
            hour >= 5 && hour < 11 ? this.themes.morning.color :
            hour >= 11 && hour < 17 ? this.themes.afternoon.color :
            hour >= 17 && hour < 21 ? this.themes.evening.color :
            this.themes.night.color;

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
        
        // Update display with compact format
        timeSpan.innerHTML = `<small>${dateStr} ${timeStr} ${offsetString} (${shortTZ})</small>`;
        
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
        
        timeSpan.setAttribute('data-bs-title', 
            `${fullTimeString}\nISO: ${isoTime}\nUNIX: ${unixTime}\nClick to copy current timestamp`);
    },

    initializeTimestampCopy() {
        const timeSpan = document.getElementById('localTime');
        if (!timeSpan) return;

        timeSpan.addEventListener('click', function() {
            const now = new Date();
            navigator.clipboard.writeText(now.toISOString()).then(() => {
                const tooltip = bootstrap.Tooltip.getInstance(this);
                const originalTitle = this.getAttribute('data-bs-title');
                
                tooltip.setContent({ '.tooltip-inner': 'Copied!' });
                setTimeout(() => {
                    tooltip.setContent({ '.tooltip-inner': originalTitle });
                }, 1000);
            });
        });
    }
};

// Initialize time display when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    // Initialize the tooltip
    const timeSpan = document.getElementById('localTime');
    if (timeSpan) {
        new bootstrap.Tooltip(timeSpan);
    }
    
    // Start the time display system
    timeDisplay.update();
    setInterval(() => timeDisplay.update(), 1000);
    timeDisplay.initializeTimestampCopy();
}); 