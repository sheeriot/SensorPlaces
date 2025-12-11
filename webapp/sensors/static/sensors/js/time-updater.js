// static/sensors/js/time-updater.js

function updateTimeAgo(container = document) {
    const elements = container.querySelectorAll('.time-ago');
    const now = new Date();

    elements.forEach(el => {
        const timestampStr = el.dataset.timestamp;
        if (!timestampStr) return;

        const timestamp = new Date(timestampStr);
        const diffSeconds = Math.round((now - timestamp) / 1000);

        let timeAgo;

        if (diffSeconds < 2) {
            timeAgo = 'just now';
        } else if (diffSeconds < 60) {
            timeAgo = `${diffSeconds} secs`;
        } else if (diffSeconds < 3600) {
            const minutes = Math.round(diffSeconds / 60);
            timeAgo = `${minutes} min${minutes > 1 ? 's' : ''}`;
        } else if (diffSeconds < 86400) {
            const hours = Math.round(diffSeconds / 3600);
            timeAgo = `${hours} hr${hours > 1 ? 's' : ''}`;
        } else {
            const days = Math.round(diffSeconds / 86400);
            timeAgo = `${days} day${days > 1 ? 's' : ''}`;
        }

        el.textContent = timeAgo;
    });
}

function initializeTimeUpdaters() {
    updateTimeAgo();
    setInterval(updateTimeAgo, 5000); // Update more frequently
}

// Run on initial load
document.addEventListener('DOMContentLoaded', initializeTimeUpdaters);

// Also run after HTMX swaps to catch new elements
document.body.addEventListener('htmx:afterSwap', function (event) {
    if (event.detail.elt) {
        // Update time for the newly swapped content only
        updateTimeAgo(event.detail.elt);
    }
});
