let liveValueFetcher = null;

function initializeLiveValueFetcher() {
    if (!liveValueFetcher) {
        const placeSlug = document.body.dataset.placeSlug;
        if (placeSlug && window.LiveValueFetcher) {
            console.log('sensor-detail.js: Initializing global LiveValueFetcher.');
            liveValueFetcher = new LiveValueFetcher(placeSlug, 30000);
            liveValueFetcher.start();
        }
    }
}

document.addEventListener('DOMContentLoaded', function () {
    console.log('sensor-detail.js: DOMContentLoaded. Initializing live value fetcher.');
    initializeLiveValueFetcher();

    document.body.addEventListener('htmx:afterSettle', function(evt) {
        console.log('sensor-detail.js: HTMX settle event triggered on target:', evt.detail.target.id);

        // If a new live value container might have been added, ensure fetcher is running and trigger a fetch.
        initializeLiveValueFetcher();
        if (liveValueFetcher) {
            console.log('sensor-detail.js: Triggering live value fetch after HTMX swap.');
            liveValueFetcher.fetch();
        }

        const graphCardId = 'sensor-graph-card';
        if (evt.detail.target.id === graphCardId) {
            console.log('sensor-detail.js: Graph card content loaded. Initializing SensorChart.');
            const graphCardElement = document.getElementById(graphCardId);

            if (graphCardElement && !graphCardElement.sensorChart) {
                // Store the chart instance on the element itself to prevent re-initialization
                graphCardElement.sensorChart = new SensorChart(graphCardId);

            } else {
                console.log('sensor-detail.js: Chart already initialized or graph card not found. Skipping.');
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
});
