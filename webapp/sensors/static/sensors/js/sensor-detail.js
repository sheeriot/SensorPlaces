let liveValueFetcher = null;
let isChartInitialized = false;

const SCRIPT_DEBUG = false;

function initializeLiveValueFetcher() {
    if (!liveValueFetcher) {
        const placeSlug = document.body.dataset.placeSlug;
        if (placeSlug && window.LiveValueFetcher) {
            if(SCRIPT_DEBUG) console.log('sensor-detail.js: Initializing global LiveValueFetcher.');
            liveValueFetcher = new LiveValueFetcher(placeSlug, 90000);
            liveValueFetcher.start();
        }
    }
}

document.addEventListener('DOMContentLoaded', function () {
    if(SCRIPT_DEBUG) console.log('sensor-detail.js: DOMContentLoaded. Initializing live value fetcher.');
    initializeLiveValueFetcher();

    document.body.addEventListener('htmx:afterSwap', function(evt) {
        if(SCRIPT_DEBUG) console.log('sensor-detail.js: htmx:afterSwap event triggered.');
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
