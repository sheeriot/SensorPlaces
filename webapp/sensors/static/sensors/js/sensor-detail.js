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

                // --- Link Detail Card Selector to Chart ---
                const graphTypeSelect = document.getElementById('sensor-graph-type-select');
                const saveBtn = document.getElementById('save-graph-type-btn');

                if (graphTypeSelect && saveBtn) {
                    graphTypeSelect.addEventListener('change', function() {
                        const newType = this.value;
                        const defaultType = this.dataset.defaultType;
                        console.log('sensor-detail.js: Graph type selected:', newType, 'Default:', defaultType);

                        // Update Chart immediately (preview)
                        if (graphCardElement.sensorChart) {
                            // sensor-chart.js listens for 'graphTypeChange' on the card element.
                            const event = new CustomEvent('graphTypeChange', { detail: { newType: newType } });
                            graphCardElement.dispatchEvent(event);
                        }

                        // Show Save Button only if the selected type differs from the sensor type default
                        // OR if we are reverting to the default but the sensor currently has an override saved.
                        // Actually, simplified logic: if the user changes the select, we let them save it.
                        // The requirement is: "Only when the sensor.graph_type selected is different than the sensor.sensor_type.default_graph_type should we show the Save button"
                        // But wait, if they change it back to the default, we should probably allow saving to "clear" the override or explicitly set it to default?
                        // If we strictly follow: show save ONLY if newType !== defaultType.
                        // However, if the sensor ALREADY has an override (e.g. sensor.graph_type is 'BAR' and default is 'LINE'),
                        // and they change it back to 'LINE', we want to save that too (effectively resetting it).
                        // So checking against defaultType alone might be tricky if we don't know the *saved* state vs *current* state.

                        // Let's look at the requirement: "no need to save it on the sensor if it gets it from sensor.sensor_type."
                        // This implies we want to save if we are *deviating* from the default.

                        if (newType !== defaultType) {
                             saveBtn.classList.remove('d-none');
                        } else {
                             // If they selected the default, maybe we still want to save (to clear the override)?
                             // If the current backend value (data-current-type) is DIFFERENT from default, and they select default,
                             // they are "fixing" it, so we should save.
                             // If current backend value IS default, and they select default, no change.

                             const currentSavedType = this.dataset.currentType;
                             if (currentSavedType !== defaultType) {
                                 saveBtn.classList.remove('d-none');
                             } else {
                                 saveBtn.classList.add('d-none');
                             }
                        }
                    });

                    // Hide Save button after successful save
                    saveBtn.addEventListener('htmx:afterRequest', function(evt) {
                        if (evt.detail.successful) {
                            saveBtn.classList.add('d-none');
                        }
                    });
                }

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
