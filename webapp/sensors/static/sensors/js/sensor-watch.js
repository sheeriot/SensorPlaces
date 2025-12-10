// static/sensors/js/sensor-watch.js

class SensorWatcher {
    constructor() {
        this.pollingInterval = null;
        this.pollUrl = null;
        this.pollTarget = null;
        this.toggleButton = null;
        this.isActive = false;
    }

    init(toggleButton) {
        this.toggleButton = toggleButton;
        const sensorId = this.toggleButton.dataset.sensorId;
        // Assuming the place slug is available on the body element
        const placeSlug = document.body.getAttribute('data-place-slug');

        if (!placeSlug) {
            console.error('Place slug not found on body element.');
            return;
        }

        this.pollUrl = `/${placeSlug}/sensor/${sensorId}/live-value/`;
        this.pollTarget = `#sensor-row-${sensorId}`;

        this.toggleButton.addEventListener('click', () => {
            this.isActive = !this.isActive;
            this.toggleButton.classList.toggle('btn-primary', this.isActive);
            this.toggleButton.classList.toggle('btn-outline-secondary', !this.isActive);
            this.toggleButton.querySelector('i').classList.toggle('bi-eye-slash', !this.isActive);
            this.toggleButton.querySelector('i').classList.toggle('bi-eye', this.isActive);


            if (this.isActive) {
                this.startPolling();
            } else {
                this.stopPolling();
            }
        });
    }

    startPolling() {
        if (this.pollingInterval) {
            this.stopPolling();
        }
        console.log(`[SensorWatcher] Starting to poll ${this.pollUrl}`);
        htmx.ajax('GET', this.pollUrl, { target: this.pollTarget, swap: 'none' });

        this.pollingInterval = setInterval(() => {
            console.log(`[SensorWatcher] Polling ${this.pollUrl}`);
            htmx.ajax('GET', this.pollUrl, { target: this.pollTarget, swap: 'none' });
        }, 30000);
    }

    stopPolling() {
        if (this.pollingInterval) {
            console.log(`[SensorWatcher] Stopping polling for ${this.pollUrl}`);
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.watch-toggle').forEach(toggle => {
        const watcher = new SensorWatcher();
        watcher.init(toggle);
    });
});

// If using HTMX, you might need to re-initialize on content swap
document.body.addEventListener('htmx:afterSwap', function(event) {
    event.detail.elt.querySelectorAll('.watch-toggle').forEach(toggle => {
        // Avoid re-initializing if it's already handled
        if (!toggle.hasOwnProperty('watcher')) {
            const watcher = new SensorWatcher();
            watcher.init(toggle);
            toggle.watcher = watcher; // Mark as initialized
        }
    });
});
