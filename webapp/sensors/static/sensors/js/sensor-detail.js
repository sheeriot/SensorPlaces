let liveValueFetcher = null;
let isChartInitialized = false;
const watchedSensors = new Set();

const SCRIPT_DEBUG = false;

function updateWatchToggleUI(toggleButton) {
    if (!toggleButton) return;
    const sensorId = toggleButton.dataset.sensorId;
    const icon = toggleButton.querySelector('i');
    if (watchedSensors.has(sensorId)) {
        toggleButton.classList.add('active');
        toggleButton.classList.replace('btn-outline-secondary', 'btn-secondary');
        if (icon) icon.classList.replace('bi-eye', 'bi-eye-slash-fill');
        toggleButton.title = 'Stop watching this sensor';
    } else {
        toggleButton.classList.remove('active');
        toggleButton.classList.replace('btn-secondary', 'btn-outline-secondary');
        if (icon) icon.classList.replace('bi-eye-slash-fill', 'bi-eye');
        toggleButton.title = 'Watch this sensor';
    }
}

function toggleWatchState(sensorId) {
    if (watchedSensors.has(sensorId)) {
        watchedSensors.delete(sensorId);
    } else {
        watchedSensors.add(sensorId);
    }
    const toggleButton = document.querySelector(`.watch-toggle[data-sensor-id="${sensorId}"]`);
    updateWatchToggleUI(toggleButton);
}

function reapplyWatchState(container) {
    container.querySelectorAll('.watch-toggle').forEach(toggleButton => {
        updateWatchToggleUI(toggleButton);
    });
}

function initializeLiveValueFetcher() {
    if (!liveValueFetcher) {
        const placeSlug = document.body.dataset.placeSlug;
        if (placeSlug && window.LiveValueFetcher) {
            if(SCRIPT_DEBUG) console.log('sensor-detail.js: Initializing global LiveValueFetcher.');
            liveValueFetcher = new LiveValueFetcher(placeSlug, 90000);
            // Don't start the timer here, but force an initial fetch.
            // The timer will be started after the first forced fetch.
            liveValueFetcher.forceRefresh().then(() => {
                if(SCRIPT_DEBUG) console.log('sensor-detail.js: Initial forced refresh complete. Starting timer.');
            liveValueFetcher.start();
            });
        }
    } else {
        // If it already exists, just force a refresh
        if(SCRIPT_DEBUG) console.log('sensor-detail.js: LiveValueFetcher already exists. Forcing refresh.');
        liveValueFetcher.forceRefresh();
    }
}

document.addEventListener('DOMContentLoaded', function () {
    if(SCRIPT_DEBUG) console.log('sensor-detail.js: DOMContentLoaded. Initializing live value fetcher.');
    initializeLiveValueFetcher();

    document.body.addEventListener('click', function(evt) {
        const toggleButton = evt.target.closest('.watch-toggle');
        if (toggleButton) {
            const sensorId = toggleButton.dataset.sensorId;
            if (sensorId) {
                toggleWatchState(sensorId);
            }
        }
    });

    document.body.addEventListener('htmx:afterSwap', function(evt) {
        if(SCRIPT_DEBUG) console.log('sensor-detail.js: htmx:afterSwap event triggered.');
        // Re-apply watch state to any toggles in the swapped content
        reapplyWatchState(evt.detail.target);

        // Check if the swapped-in content contains the graph card.
        const graphCard = document.querySelector('#sensor-graph-card');

        if (graphCard && !isChartInitialized) {
            if(SCRIPT_DEBUG) console.log('sensor-detail.js: Graph card found and chart not initialized. Initializing SensorChart.', graphCard);
            new SensorChart('sensor-graph-card');
            isChartInitialized = true;
        } else if (graphCard && isChartInitialized) {
            if(SCRIPT_DEBUG) console.log('sensor-detail.js: Graph card found, but chart is already initialized. Skipping.');
        } else {
            if(SCRIPT_DEBUG) console.log('sensor-detail.js: Graph card not found. Resetting initialization flag.');
            isChartInitialized = false;
        }
    });

    // This event listener fires after HTMX has settled a request.
    document.addEventListener('htmx:afterSettle', function(evt) {
        const target = evt.detail.target;
        if (target && target.id === 'graph-card-container') {
            if(commonConfig.debug) console.log('sensor-detail.js: HTMX settle event triggered on target:', target.id);

            const sensorPk = target.dataset.sensorId;
            if (sensorPk) {
                const source = document.getElementById(`live-value-source-${sensorPk}`);
                const destination = document.getElementById(`live-value-destination-${sensorPk}`);

                if (source && destination) {
                    if(commonConfig.debug) console.log(`sensor-detail.js: Copying live value from source to destination for sensor ${sensorPk}.`);
                    destination.innerHTML = source.innerHTML;
                } else {
                    if(commonConfig.debug) console.warn(`sensor-detail.js: Could not find source or destination for sensor ${sensorPk}.`);
                }
            }
        }
    });

    document.querySelectorAll('.live-value-refresh').forEach(button => {
        button.addEventListener('click', () => {
            if (liveValueFetcher) {
                if(commonConfig.debug) console.log('sensor-detail.js: Manual refresh triggered.');
                liveValueFetcher.forceRefresh();
    }
        });
    });

    // Listen for the custom event from sensor-chart.js
    document.addEventListener('graphDataUpdated', function(e) {
        if (SCRIPT_DEBUG) console.log('sensor-detail.js: Received graphDataUpdated event:', e.detail);

        const { sensorId, latestData, unitSymbol, decimalPlaces } = e.detail;
        if (liveValueFetcher && sensorId && latestData) {
            liveValueFetcher.updateSensorValueFromGraph(sensorId, latestData, unitSymbol, decimalPlaces);
        }
    });
});
