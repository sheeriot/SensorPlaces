// static/sensors/js/sensor-watch.js

const sensorWatchConfig = {
    debug: false, // Master debug switch
};

class SensorWatcher {
    constructor() {
        this.watchedSensors = new Set(JSON.parse(localStorage.getItem('watchedSensors')) || []);
        this.pollingIntervals = new Map();
        if (sensorWatchConfig.debug) console.log('[SensorWatcher] Initialized. Watched sensors on load:', Array.from(this.watchedSensors));

        document.addEventListener('DOMContentLoaded', () => this.initAll(document.body));
        document.body.addEventListener('htmx:afterSwap', (event) => this.initAll(event.detail.elt));
    }

    initAll(container) {
        if (sensorWatchConfig.debug) console.log('[SensorWatcher] Running initAll on container:', container);

        const toggles = container.querySelectorAll('.watch-toggle');
        toggles.forEach(toggle => {
            const sensorId = toggle.dataset.sensorId;
            if (!toggle.dataset.watcherInitialized) {
                if (sensorWatchConfig.debug) console.log(`[SensorWatcher] Initializing new toggle for sensor ${sensorId}`);
                toggle.addEventListener('click', () => this.toggleSensor(sensorId));
                toggle.dataset.watcherInitialized = 'true';
            }
        });

        // Update UI for all sensors and start polling for watched ones
        const allSensorIds = new Set(Array.from(document.querySelectorAll('[data-sensor-id]')).map(el => el.dataset.sensorId));
        allSensorIds.forEach(sensorId => {
            const isWatched = this.watchedSensors.has(sensorId);
            this.updateUI(sensorId, isWatched);
            if (isWatched && !this.pollingIntervals.has(sensorId)) {
                this.startPolling(sensorId);
            }
        });
    }

    toggleSensor(sensorId) {
        const isCurrentlyWatched = this.watchedSensors.has(sensorId);
        if (isCurrentlyWatched) {
            this.watchedSensors.delete(sensorId);
            this.stopPolling(sensorId);
        } else {
            this.watchedSensors.add(sensorId);
            this.startPolling(sensorId);
        }
        localStorage.setItem('watchedSensors', JSON.stringify(Array.from(this.watchedSensors)));
        if (sensorWatchConfig.debug) console.log(`[SensorWatcher] Toggled sensor ${sensorId}. New state: ${!isCurrentlyWatched}. Watched set:`, Array.from(this.watchedSensors));
        this.updateUI(sensorId, !isCurrentlyWatched);
    }

    updateUI(sensorId, isWatched) {
        if (sensorWatchConfig.debug) console.log(`[SensorWatcher] Updating UI for all elements of sensor ${sensorId} to state: ${isWatched}`);
        const toggles = document.querySelectorAll(`.watch-toggle[data-sensor-id="${sensorId}"]`);
        toggles.forEach(toggle => {
toggle.classList.toggle('btn-primary', isWatched);
        toggle.classList.toggle('btn-link', !isWatched); // Use btn-link for no border
        const icon = toggle.querySelector('i');
            if (icon) {
                icon.classList.toggle('bi-eye-fill', isWatched);
                icon.classList.toggle('bi-eye', !isWatched);
                icon.classList.toggle('text-white', isWatched);
            }
        });
    }

    startPolling(sensorId) {
        if (this.pollingIntervals.has(sensorId)) {
            if (sensorWatchConfig.debug) console.log(`[SensorWatcher] Polling already active for sensor ${sensorId}.`);
            return;
        }

        const placeSlug = document.body.dataset.placeSlug;
        if (!placeSlug || placeSlug === 'none') {
            console.error('[SensorWatcher] Error: place_slug not found on body data attribute.');
            return;
        }

        const mainSensorContainer = document.querySelector('.container-fluid[data-sensor-pk]');
        const isNarrowView = !!mainSensorContainer;

        let pollUrl = `/${placeSlug}/sensor/${sensorId}/live-value/?style=row_content`;
        if (isNarrowView) {
            pollUrl += '&narrow_view=true';
        }

        const targetSelector = `#sensor-row-${sensorId}`;

        if (sensorWatchConfig.debug) console.log(`[SensorWatcher] Starting to poll for sensor ${sensorId}: URL=${pollUrl}, Target=${targetSelector}`);

        const performPoll = () => {
             if (!this.watchedSensors.has(sensorId)) {
                this.stopPolling(sensorId);
                return;
            }
            if (sensorWatchConfig.debug) console.log(`[SensorWatcher] Polling ${pollUrl} for sensor ${sensorId}`);
            htmx.ajax('GET', pollUrl, {
                target: htmx.find(targetSelector),
                swap: 'innerHTML'
            });
        };

        // Initial fetch
        performPoll();

        const interval = setInterval(performPoll, 30000);
        this.pollingIntervals.set(sensorId, interval);
    }

    stopPolling(sensorId) {
        if (this.pollingIntervals.has(sensorId)) {
            if (sensorWatchConfig.debug) console.log(`[SensorWatcher] Stopping polling for sensor ${sensorId}`);
            clearInterval(this.pollingIntervals.get(sensorId));
            this.pollingIntervals.delete(sensorId);
        }
    }
}

// Instantiate the watcher to start the process
new SensorWatcher();
