// static/sensors/js/time-updater.js

function updateTimeAgo() {
    const elements = document.querySelectorAll('.time-ago');
    const now = new Date();

    elements.forEach(el => {
        const timestampStr = el.dataset.timestamp;
        if (!timestampStr) return;

        const timestamp = new Date(timestampStr);
        const diffSeconds = Math.round((now - timestamp) / 1000);

        let timeAgo;

        if (diffSeconds < 60) {
            timeAgo = '< minute';
        } else if (diffSeconds < 3600) {
            const minutes = Math.round(diffSeconds / 60);
            timeAgo = `${minutes} minute${minutes > 1 ? 's' : ''}`;
        } else if (diffSeconds < 86400) {
            const hours = Math.round(diffSeconds / 3600);
            timeAgo = `${hours} hour${hours > 1 ? 's' : ''}`;
        } else {
            const days = Math.round(diffSeconds / 86400);
            timeAgo = `${days} day${days > 1 ? 's' : ''}`;
        }

        el.textContent = timeAgo;
    });
}

// Run on initial load
document.addEventListener('DOMContentLoaded', () => {
    updateTimeAgo();
    // Run every minute
    setInterval(updateTimeAgo, 60000);
});

// Also run after HTMX swaps to catch new elements
document.body.addEventListener('htmx:afterSwap', function (event) {
    updateTimeAgo();
});
