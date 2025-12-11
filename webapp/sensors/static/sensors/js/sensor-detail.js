// static/sensors/js/sensor-detail.js

document.addEventListener('click', function(event) {
    const hammerButton = event.target.closest('[id^="hammer-btn-"]');
    if (hammerButton) {
        hammerButton.classList.add('hammer-animation');
        setTimeout(() => {
            hammerButton.classList.remove('hammer-animation');
        }, 300);
    }
});

document.addEventListener('DOMContentLoaded', function () {
    const SCRIPT_DEBUG = true;
    if(SCRIPT_DEBUG) console.log('--- SENSOR-DETAIL.JS v.DEBUG.2 LOADED ---');

    let liveValueFetcher;
    let sensorChart;

    function initializeChart(graphCard) {
        const sensorId = graphCard.dataset.sensorId;
        if (SCRIPT_DEBUG) console.log(`sensor-detail.js: Initializing chart for sensor ${sensorId}.`);
        if (sensorId) {
            sensorChart = new SensorChart(`sensor-graph-card`);
        }
    }

    function initializeLiveValueFetcher() {
        const placeSlug = document.body.dataset.placeSlug;
        if (placeSlug && window.LiveValueFetcher) {
            if(SCRIPT_DEBUG) console.log('sensor-detail.js: Initializing global LiveValueFetcher.');
            liveValueFetcher = new LiveValueFetcher(placeSlug, 90000);
            liveValueFetcher.forceRefresh().then(() => {
                if(SCRIPT_DEBUG) console.log('sensor-detail.js: Initial forced refresh complete. Starting timer.');
                liveValueFetcher.start();
            });
        } else {
            if(SCRIPT_DEBUG) console.log('sensor-detail.js: LiveValueFetcher not available or no placeSlug.');
        }
    }

    function reapplyWatchState(container) {
        // This function is now handled by sensor-watch.js
    }

    function reinitializeTooltips(container) {
        const tooltipTriggerList = [].slice.call(container.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }

    reinitializeTooltips(document);

    document.body.addEventListener('htmx:afterSwap', function (event) {
        if(SCRIPT_DEBUG) console.log('sensor-detail.js: htmx:afterSwap triggered for target:', event.detail.target.id);

        if (event.detail.target.id === 'graph-card-container') {
             if(SCRIPT_DEBUG) console.log('sensor-detail.js: Graph card loaded, initializing chart.');
             const graphCard = document.getElementById('sensor-graph-card');
             if(graphCard) {
                initializeChart(graphCard);
             } else {
                if(SCRIPT_DEBUG) console.log('sensor-detail.js: sensor-graph-card not found inside container.');
             }
        }
        reapplyWatchState(event.detail.elt);
        reinitializeTooltips(event.detail.elt);
    });

    const graphCard = document.getElementById('sensor-graph-card');
    if (graphCard) {
        initializeChart(graphCard);
    }

    const graphTypeSelect = document.getElementById('sensor-graph-type-select');
    if (graphTypeSelect) {
        graphTypeSelect.addEventListener('change', function () {
            const saveBtn = document.getElementById('save-graph-type-btn');
            const currentType = this.dataset.currentType;
            if (this.value !== currentType) {
                saveBtn.classList.remove('d-none');
            } else {
                saveBtn.classList.add('d-none');
            }
        });
    }

    document.body.addEventListener('htmx:afterRequest', function(event) {
        if (event.detail.pathInfo && event.detail.pathInfo.path && event.detail.pathInfo.path.includes('update-graph-type')) {
            if (event.detail.successful) {
                const graphTypeSelect = document.getElementById('sensor-graph-type-select');
                if (graphTypeSelect) {
                    const newType = graphTypeSelect.value;
                    graphTypeSelect.dataset.currentType = newType;
                    const saveBtn = document.getElementById('save-graph-type-btn');
                    saveBtn.classList.add('d-none');

                    // Find the chart and update its type
                    const chartId = document.querySelector('[id^="sensor-chart-"]').id;
                    const chartInstance = Chart.getChart(chartId);
                    if (chartInstance && window.sensorChartManager) {
                        const sensorPk = chartInstance.canvas.dataset.sensorPk;
                         window.sensorChartManager.updateChartType(sensorPk, newType);
                    }
                }
            }
        }
    });

    initializeLiveValueFetcher();
});
