// static/sensors/js/sensor-watch.js

const sensorWatchConfig = {
    debug: true, // Master debug switch
};

class SensorWatcher {
    constructor() {
        this.watchedSensors = new Set(JSON.parse(localStorage.getItem('watchedSensors')) || []);
        this.pollingIntervals = new Map();
        if (sensorWatchConfig.debug) console.log('[SensorWatcher] Initialized. Watched sensors on load:', Array.from(this.watchedSensors));

        document.addEventListener('DOMContentLoaded', () => this.initAll(document.body));
        document.body.addEventListener('htmx:afterSwap', (event) => {
            if (event.detail.elt) {
                this.initAll(event.detail.elt)
            }
        });
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
            if (!sensorId) return;
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
            toggle.classList.toggle('btn-outline-secondary', !isWatched);
            const icon = toggle.querySelector('i');
            if (icon) {
                icon.classList.toggle('bi-eye-fill', isWatched);
                icon.classList.toggle('bi-eye', !isWatched);
            }
        });
    }

    startPolling(sensorId) {
        if (this.pollingIntervals.has(sensorId)) {
            if (sensorWatchConfig.debug) console.log(`[SensorWatcher] Polling already active for sensor ${sensorId}.`);
            return;
        }

        const pollableElements = document.querySelectorAll(`[data-sensor-id="${sensorId}"][data-poll-url]`);
        if (sensorWatchConfig.debug) console.log(`[SensorWatcher] Found ${pollableElements.length} pollable elements for sensor ${sensorId}`);

        const performPoll = () => {
            if (!this.watchedSensors.has(sensorId)) {
                this.stopPolling(sensorId);
                return;
            }

            pollableElements.forEach(element => {
                // Check if the element is still in the DOM
                if (!document.body.contains(element)) {
                    return;
                }

                const pollUrl = new URL(element.dataset.pollUrl, window.location.origin);
                const style = element.dataset.pollStyle;
                const isNarrow = element.dataset.narrowView === 'true';

                if (style) {
                    pollUrl.searchParams.set('style', style);
                }
                if (isNarrow) {
                    pollUrl.searchParams.set('narrow_view', 'true');
                }

                if (sensorWatchConfig.debug) console.log(`[SensorWatcher] Polling for element:`, {
                    id: element.id,
                    url: pollUrl.toString()
                });

                // The target is the element itself, but we are replacing its content
                htmx.ajax('GET', pollUrl.toString(), {
                    target: element,
                    swap: 'innerHTML'
                });
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
