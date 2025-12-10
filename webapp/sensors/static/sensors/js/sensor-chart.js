console.log('--- SENSOR-CHART.JS v.DEBUG.2 LOADED ---');

// Local debug flag - set to true during development, false in production
const SENSOR_CHART_DEBUG = false;

// Helper function to get display strings for boolean values
function getBooleanDisplay(value, sensorTypeName) {
    const isPositive = value > 0;
    switch (sensorTypeName) {
        case 'Switch':
            return isPositive ? 'On' : 'Off';
        case 'Water Detector':
            return isPositive ? 'Water' : 'No Water';
        default:
            return isPositive ? 'True' : 'False';
    }
}

if (SENSOR_CHART_DEBUG) console.log('sensor-chart.js');
class SensorChart {
    constructor(graphCardId) {
        this.graphCard = document.getElementById(graphCardId);
        if (!this.graphCard) {
            console.error('Graph card not found!');
            return;
        }

        // Use local constant for debug configuration
        this.debug = SENSOR_CHART_DEBUG;

        if (this.debug) {
            console.log('SensorChart: Initializing...', { graphCardId });
            console.log('SensorChart: Initial dataset from DOM:', JSON.parse(JSON.stringify(this.graphCard.dataset)));
        }

        this.chart = null;
        this.originalData = [];
        this.currentGraphType = this.graphCard.dataset.graphType;
        this.originalUnit = this.graphCard.dataset.sensorUnit;
        this.unitName = this.graphCard.dataset.sensorUnitName; // Need to add this data attr
        this.sensorType = this.graphCard.dataset.sensorType;
        this.originalMinValue = this.graphCard.dataset.minValue !== '' ? parseFloat(this.graphCard.dataset.minValue) : null;
        this.originalMaxValue = this.graphCard.dataset.maxValue !== '' ? parseFloat(this.graphCard.dataset.maxValue) : null;
        this.dataTable = null;
        this.sensorConfig = {};
        this.queryRange = {}; // Initialize queryRange

        this.initialize();
    }

    initializeDataTable() {
        const sensorId = this.graphCard.dataset.sensorId;
        const dataTableElement = document.querySelector(`#graph-datapoints-${sensorId} table`);

        if (dataTableElement && !this.dataTable) {
            if (this.debug) console.log("SensorChart: Initializing empty DataTable.");
            this.dataTable = new simpleDatatables.DataTable(dataTableElement, {
                searchable: false,
                perPageSelect: false,
                paging: true,
                perPage: 10,
                labels: {
                    noRows: "No data points found",
                    info: "Showing {start} to {end} of {rows} entries",
                }
            });
        }
    }

    // --- Conversion Helpers ---
    celsiusToFahrenheit(celsius) { return celsius * 9 / 5 + 32; }
    fahrenheitToCelsius(fahrenheit) { return (fahrenheit - 32) * 5 / 9; }

    // --- UI Helper ---
    showLoadingState(isLoading) {
        const sensorId = this.graphCard.dataset.sensorId;
        const placeholder = document.getElementById(`graph-placeholder-${sensorId}`);
        const content = document.getElementById(`graph-content-${sensorId}`);
        const loadingSpinner = document.getElementById(`graph-loading-${sensorId}`);

        if (isLoading) {
            if (placeholder) placeholder.classList.add('d-none');
            // Keep content visible but maybe dimmed? Or just show spinner overlay
            if (loadingSpinner) loadingSpinner.classList.remove('d-none');

            const chartCanvas = document.getElementById(`sensor-chart-${sensorId}`);
             // Don't destroy chart immediately to avoid flicker, just maybe show loading
        } else {
             if (loadingSpinner) loadingSpinner.classList.add('d-none');
        }
    }

    showToast(message, type = 'info') {
        // Use a global toast function if available, otherwise fallback to alert/log
        if (window.showToast) {
            window.showToast(message, type);
        } else if (typeof bootstrap !== 'undefined' && document.getElementById('toast-container')) {
            // Create a toast dynamically if container exists
             const toastContainer = document.getElementById('toast-container');
             const toastHtml = `
                <div class="toast align-items-center text-white bg-${type} border-0" role="alert" aria-live="assertive" aria-atomic="true">
                  <div class="d-flex">
                    <div class="toast-body">
                      ${message}
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
                  </div>
                </div>
             `;
             const tempDiv = document.createElement('div');
             tempDiv.innerHTML = toastHtml;
             const toastEl = tempDiv.firstElementChild;
             toastContainer.appendChild(toastEl);
             const toast = new bootstrap.Toast(toastEl);
             toast.show();
             toastEl.addEventListener('hidden.bs.toast', () => {
                 toastEl.remove();
             });
        } else {
            console.log(`[${type.toUpperCase()}] ${message}`);
        }
    }

    // --- Data Fetching and Processing ---
    async fetchData(apiUrl) {
        if (this.debug) console.log('SensorChart: fetchData called with URL:', apiUrl);
        this.showLoadingState(true);

        if (!apiUrl) {
            console.error('API URL is missing.');
            this.renderChart([], this.currentGraphType);
            this.showLoadingState(false);
            return;
        }
        try {
            let url;
            try {
                url = new URL(apiUrl);
            } catch (e) {
                console.error('Invalid API URL provided:', apiUrl, e);
                // As a fallback, try resolving relative to the window origin
                url = new URL(apiUrl, window.location.origin);
            }

            const userTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
            url.searchParams.set('timezone', userTimezone);
            if (this.debug) console.log('Fetching data from URL:', url.toString());

            const responseData = await window.utils.fetchWithCSRF(url.toString());

            if (this.debug) {
                console.log("SensorChart: Raw API responseData:", JSON.parse(JSON.stringify(responseData)));
            }

            if (responseData.status !== 'success') {
                throw new Error(responseData.description || 'The server returned an error.');
            }

            if (responseData && responseData.payload) {
                if (this.debug) console.log('SensorChart: Raw API responseData:', responseData);

                this.sensorConfig = responseData.payload.sensor;
                this.queryTimeMs = responseData.payload.query_time_ms;
                this.queryRange = responseData.payload.query_range; // This was missing

                if (this.debug) console.log('SensorChart: Stored sensorConfig:', this.sensorConfig);

                // --- Log Data ---
                if (this.debug) {
                    console.log("Sensor Chart Data Payload:");
                    if (responseData.payload && responseData.payload.data_points && responseData.payload.data_points.length > 0) {
                         // Show first and last few points
                         console.table(responseData.payload.data_points.slice(0, 5).concat(responseData.payload.data_points.slice(-5)));
                    } else {
                        console.log("No data points returned.");
                    }
                    console.log(`Query Time: ${responseData.payload.query_time_ms}ms`);
                }

                // --- Populate Footer Stats ---
                const queryTimeEl = document.getElementById('graph-query-time');
                if (queryTimeEl && responseData.payload.query_time_ms) {
                    queryTimeEl.textContent = `Data: ${responseData.payload.query_time_ms.toFixed(0)}ms`;
                }

                const datapointCountEl = document.getElementById('datapoint-count');
                if (datapointCountEl && responseData.payload.data_points) {
                    datapointCountEl.textContent = `${responseData.payload.data_points.length} points`;
                }

                const firstReadingEl = document.getElementById('first-reading-time');
                const lastReadingEl = document.getElementById('last-reading-time');
                if (responseData.payload.data_points && responseData.payload.data_points.length > 0) {
                    const firstPoint = responseData.payload.data_points[0][0];
                    const lastPoint = responseData.payload.data_points[responseData.payload.data_points.length - 1][0];

                    const options = { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false };

                    if (firstReadingEl) {
                        firstReadingEl.textContent = `First: ${new Date(firstPoint).toLocaleString(undefined, options)}`;
                    }
                    if (lastReadingEl) {
                        lastReadingEl.textContent = `Last: ${new Date(lastPoint).toLocaleString(undefined, options)}`;
                    }
                } else {
                    if (firstReadingEl) firstReadingEl.textContent = '';
                    if (lastReadingEl) lastReadingEl.textContent = '';
                }

                this.currentGraphType = this.sensorConfig.graph_type;
                this.graphCard.dataset.sensorUnit = this.sensorConfig.unit || 'N/A';
                this.originalUnit = this.graphCard.dataset.sensorUnit;

                this.originalData = responseData.payload.data_points.map(p => [new Date(p[0]), p[1]]);

                // Call the summary and table update function with the correct data
                this.updateDataPointsTable(this.originalData.map(item => ({ x: item[0], y: item[1] })), this.originalUnit, this.graphCard.dataset.decimalPlaces);

                const tempUnitSelect = document.getElementById('temp-unit-select');
                if (tempUnitSelect && tempUnitSelect.value !== this.originalUnit.replace('°','')) {
                    tempUnitSelect.dispatchEvent(new Event('change'));
                } else {
                    this.renderChart(this.originalData, this.currentGraphType);
                }

                // Notify user if data is empty but successful
                const warningEl = document.getElementById(`graph-warning-${this.graphCard.dataset.sensorId}`);
                if (warningEl) warningEl.classList.add('d-none');

                if (this.originalData.length === 0) {
                    this.showToast('No data found for the selected time range.', 'warning');
                } else {
                     // Check if data is outside min/max range
                     // Use the dataset values which are strings, convert to float if they exist
                     const effectiveMin = this.originalMinValue;
                     const effectiveMax = this.originalMaxValue;

                    if (effectiveMin !== null || effectiveMax !== null) {
                        let outOfRangeCount = 0;
                        this.originalData.forEach(p => {
                             const val = p[1];
                             if (val !== null) {
                                 if ((effectiveMin !== null && val < effectiveMin) || (effectiveMax !== null && val > effectiveMax)) {
                                     outOfRangeCount++;
                                 }
                             }
                        });

                        if (outOfRangeCount > 0 && warningEl) {
                             warningEl.textContent = `Warning: ${outOfRangeCount} of ${this.originalData.length} data points are outside the defined range (${effectiveMin !== null ? effectiveMin : '-∞'} to ${effectiveMax !== null ? effectiveMax : '+∞'}).`;
                             warningEl.classList.remove('d-none');
                        }
                    }
                }

                // Dispatch an event to notify other components that new data is available
                if (this.originalData.length > 0) {
                    const event = new CustomEvent('graphDataUpdated', {
                        detail: {
                            sensorId: this.graphCard.dataset.sensorId,
                            latestData: this.originalData[this.originalData.length - 1],
                            unitSymbol: this.sensorConfig.unit,
                            decimalPlaces: this.sensorConfig.decimal_places
                        }
                    });
                    document.dispatchEvent(event);
                }

            } else {
                throw new Error('Invalid API response structure.');
            }

        } catch (error) {
            console.error('Error fetching or rendering chart:', error);
            const sensorId = this.graphCard.dataset.sensorId;
            const placeholder = document.getElementById(`graph-placeholder-${sensorId}`);
            const content = document.getElementById(`graph-content-${sensorId}`);

            this.showToast('Failed to load graph data. See console for details.', 'danger');

            if (placeholder) {
                placeholder.classList.remove('d-none');
                placeholder.innerHTML = `<i class="bi bi-exclamation-triangle-fill fs-1 text-danger"></i><p class="mt-2 text-danger">Failed to load graph data.</p>`;
            }
            if (content) content.classList.add('d-none');
        } finally {
            this.showLoadingState(false);
        }
    }

    _getAdaptiveTimeStep(min, max) {
        if (!min || !max) {
            return { unit: 'hour', stepSize: 12 };
        }
        const durationHours = (max.getTime() - min.getTime()) / (1000 * 60 * 60);

        if (durationHours <= 2) return { unit: 'minute', stepSize: 15 };
        if (durationHours <= 12) return { unit: 'hour', stepSize: 1 };
        if (durationHours <= 24) return { unit: 'hour', stepSize: 3 };
        if (durationHours <= 48) return { unit: 'hour', stepSize: 4 };
        if (durationHours <= 72) return { unit: 'hour', stepSize: 6 };
        if (durationHours <= 144) return { unit: 'hour', stepSize: 8 };
        if (durationHours <= 7 * 24) return { unit: 'hour', stepSize: 12 };
        return { unit: 'day', stepSize: 1 };
    }

    // --- Chart Rendering ---
    renderChart(data, type) {
        if (this.debug) console.log(`SensorChart: renderChart called with ${data.length} data points and type: ${type}`);
        const sensorId = this.graphCard.dataset.sensorId;
        const placeholder = document.getElementById(`graph-placeholder-${sensorId}`);
        const content = document.getElementById(`graph-content-${sensorId}`);
        const chartCanvas = document.getElementById(`sensor-chart-${sensorId}`);
        if (!chartCanvas) return;

        // Handle visibility
        if (data && data.length > 0) {
            if (placeholder) placeholder.classList.add('d-none');
            if (content) content.classList.remove('d-none');
        } else {
            if (placeholder) {
                placeholder.classList.remove('d-none');
                placeholder.innerHTML = `<i class="bi bi-info-circle fs-1 text-secondary"></i><p class="mt-2 text-muted">No data available for this time range.</p>`;
            }
            if (content) content.classList.add('d-none');
            return; // Exit if no data
        }

        const displayUnit = this.graphCard.dataset.sensorUnit || '';
        // const minValue = this.graphCard.dataset.minValue !== '' ? parseFloat(this.graphCard.dataset.minValue) : null;
        // const maxValue = this.graphCard.dataset.maxValue !== '' ? parseFloat(this.graphCard.dataset.maxValue) : null;
        const decimalPlaces = this.graphCard.dataset.decimalPlaces !== '' ? parseInt(this.graphCard.dataset.decimalPlaces) : 2;
        const sensorName = this.graphCard.dataset.sensorName || 'Sensor';
        const deviceName = this.graphCard.dataset.deviceName || 'Device';

        const isBoolean = this.sensorConfig && this.sensorConfig.is_boolean;
        if (this.debug) {
            console.log('SensorChart->renderChart: isBoolean check:', isBoolean);
        }

        // Calculate effective min/max based on unit conversion
        let effectiveMin = this.originalMinValue;
        let effectiveMax = this.originalMaxValue;

        if (effectiveMin !== null || effectiveMax !== null) {
            // Check if conversion is needed
            if (displayUnit.includes('F') && this.originalUnit.includes('C')) {
                if (effectiveMin !== null) effectiveMin = this.celsiusToFahrenheit(effectiveMin);
                if (effectiveMax !== null) effectiveMax = this.celsiusToFahrenheit(effectiveMax);
            } else if (displayUnit.includes('C') && this.originalUnit.includes('F')) {
                if (effectiveMin !== null) effectiveMin = this.fahrenheitToCelsius(effectiveMin);
                if (effectiveMax !== null) effectiveMax = this.fahrenheitToCelsius(effectiveMax);
            }
        }

        if (this.chart) {
            this.chart.destroy();
            this.chart = null;
        } else {
            // Safety check: verify if a chart instance is already attached to this canvas context
            // This handles cases where this.chart ref was lost but Chart.js still tracks it
            const sensorId = this.graphCard.dataset.sensorId;
            const chartCanvas = document.getElementById(`sensor-chart-${sensorId}`);
            const existingChart = Chart.getChart(chartCanvas);
            if (existingChart) {
                existingChart.destroy();
            }
        }

        const chartData = data.map(item => ({ x: item[0], y: item[1] }));

        let typeUpper = 'LINE';
        if (type) {
            typeUpper = type.toUpperCase();
        }

        // Map sensor graph type to Chart.js type and options
        let chartType = 'line'; // default
        let stepped = false;
        let showLine = true;
        let fill = false;
        let pointRadius = 2;

        if (typeUpper === 'SCATTER') {
            chartType = 'scatter';
            showLine = false;
        } else if (typeUpper === 'BAR') {
            chartType = 'bar';
        } else if (typeUpper === 'STEP') {
            chartType = 'line';
            stepped = true;
            fill = true;
        } else if (typeUpper === 'ALARM_BAR') {
             chartType = 'bar';
             // For ALARM_BAR, we might want to transform data to 0/1 or similar if not already done backend-side.
             // But assuming backend returns values, we just plot them.
             // If "Alarm Events" implies binary, ensure data reflects that.
        } else if (typeUpper === 'OVERLAY') {
             // Overlay usually implies mixed types (line + points/bars).
             // Chart.js handles mixed types via dataset controllers.
             // For a simple single-dataset chart, 'line' with points is standard.
             // If we need dual datasets (value vs alarm), we'd need structured data from backend
             // distinguishing the two. Assuming single series for now.
             chartType = 'line';
             pointRadius = 6;
             showLine = true; // or false depending on specific "Overlay" look
        }

        let yAxisTitle = `Value (${displayUnit})`;
        if (this.sensorConfig && this.sensorConfig.is_boolean) {
            yAxisTitle = 'State';
        }

        const yAxisOptions = { title: { display: true, text: yAxisTitle } };
        // Use strict min/max to adhere to the sensor's defined range
        if (effectiveMin !== null) yAxisOptions.min = effectiveMin;
        if (effectiveMax !== null) yAxisOptions.max = effectiveMax;

        if (this.sensorType && this.sensorType.toLowerCase().includes('humidity')) {
            yAxisOptions.min = 0;
            yAxisOptions.max = 100;
        }

        // Special scales for Alarm types if needed
        if (typeUpper === 'STEP' || typeUpper === 'ALARM_BAR') {
             // e.g. beginAtZero: true
             // yAxisOptions.beginAtZero = true;
        }

        if (this.sensorConfig && this.sensorConfig.is_boolean) {
            yAxisOptions.min = 0;
            yAxisOptions.max = 1;
            yAxisOptions.ticks = {
                stepSize: 1,
                callback: (value) => {
                    if (value === 0 || value === 1) {
                        return getBooleanDisplay(value, this.sensorConfig.sensor_type_name);
                    }
                    return null;
                }
            };
        }

        if (this.debug) {
            console.log('SensorChart: Render Configuration', {
                sensorType: this.sensorType,
                effectiveMin,
                effectiveMax,
                yAxisOptions: JSON.parse(JSON.stringify(yAxisOptions)), // Clone to avoid reference issues in log
                dataRange: {
                    min: chartData.length > 0 ? Math.min(...chartData.map(d => d.y)) : 'N/A',
                    max: chartData.length > 0 ? Math.max(...chartData.map(d => d.y)) : 'N/A'
                }
            });
        }

        const start = new Date(this.graphCard.dataset.startDate);
        const end = new Date(this.graphCard.dataset.endDate);
        const timeStep = this._getAdaptiveTimeStep(start, end);

        const timezonePlugin = {
            id: 'timezonePlugin',
            afterDraw: (chart) => {
                const ctx = chart.ctx;
                const chartArea = chart.chartArea;

                const userTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
                const offset = new Date().toLocaleDateString(undefined, { day:'2-digit', timeZoneName: 'short' }).substring(4);

                ctx.save();
                ctx.font = '12px Arial';
                ctx.fillStyle = 'rgba(102, 102, 102, 0.8)';
                ctx.textAlign = 'right';
                ctx.fillText(`${userTimezone} (${offset})`, chartArea.right, chartArea.bottom + 30);
                ctx.restore();
            }
        };

        const datasetConfig = {
            label: `${sensorName} (${deviceName})`,
            data: chartData,
            borderColor: 'rgba(75, 192, 192, 1)',
            backgroundColor: 'rgba(75, 192, 192, 0.2)',
            fill: fill,
            tension: 0.1,
            pointRadius: pointRadius,
            pointHoverRadius: 5,
            stepped: stepped,
            showLine: showLine
        };

        // Adjust colors or styles for specific types
        if (typeUpper === 'ALARM_BAR') {
            datasetConfig.backgroundColor = 'rgba(255, 99, 132, 0.5)';
            datasetConfig.borderColor = 'rgba(255, 99, 132, 1)';
        }

        this.chart = new Chart(chartCanvas.getContext('2d'), {
            type: chartType,
            data: {
                datasets: [datasetConfig]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'nearest',
                    axis: 'x',
                    intersect: false
                },
                scales: {
                    x: {
                        min: start.getTime(),
                        max: end.getTime(),
                        type: 'time',
                        time: {
                            unit: timeStep.unit,
                            stepSize: timeStep.stepSize,
                            tooltipFormat: 'MMM d, yyyy, HH:mm:ss',
                            displayFormats: {
                                hour: 'HH', // Simplified hour format
                                day: 'MMM d'
                            }
                        },
                        title: { display: true, text: 'Time' },
                        ticks: {
                            major: {
                                enabled: true
                            },
                            autoSkip: false, // This is the critical fix
                            maxRotation: 0,
                            callback: function(value, index, ticks) {
                                const date = new Date(value);
                                const unit = timeStep.unit;
                                const stepSize = timeStep.stepSize;

                                // Only draw labels that fall on our exact step interval
                                if (unit === 'hour') {
                                    if (date.getHours() % stepSize !== 0) return '';
                                } else if (unit === 'minute') {
                                    if (date.getMinutes() % stepSize !== 0) return '';
                                }

                                if (date.getHours() === 0 && date.getMinutes() === 0) {
                                    return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(date);
                                }
                                // For multi-day views, only show the hour.
                                const durationHours = (end.getTime() - start.getTime()) / (1000 * 60 * 60);
                                if (durationHours > 48) {
                                    return new Intl.DateTimeFormat(undefined, { hour: '2-digit', hour12: false }).format(date);
                                }
                                // For shorter views, show HH:mm, but skip if not on the hour
                                if (date.getMinutes() !== 0) {
                                    return new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit', hour12: false }).format(date);
                                }
                                return new Intl.DateTimeFormat(undefined, { hour: '2-digit', hour12: false }).format(date);
                            }
                        },
                        grid: {
                            color: function(context) {
                                if (context && context.tick && context.tick.major) {
                                    return 'rgba(218, 165, 32, 0.7)'; // Dark gold for major ticks (midnight)
                                }
                                return 'rgba(0, 0, 0, 0.1)';
                            },
                            lineWidth: function(context) {
                                if (context && context.tick && context.tick.major) {
                                    return 2; // Bolder line for major ticks
                                }
                                return 1;
                            }
                        }
                    },
                    y: yAxisOptions
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    title: {
                        display: true,
                        text: `${sensorName} (${deviceName})`,
                        position: 'top',
                        align: 'center',
                        font: { size: 16 }
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                let label = context.dataset.label || '';
                                if (label) label += ': ';
                                if (context.parsed.y !== null) {
                                    label += `${context.parsed.y.toFixed(decimalPlaces)} ${displayUnit}`;
                                }
                                return label;
                            }
                        }
                    }
                }
            },
            plugins: [timezonePlugin]
        });

        // Chart.js expects data to be sorted ascending, which the API now provides.
        this.chart.data.datasets[0].data = chartData;
        this.chart.update();
        if (this.debug) {
            console.log('SensorChart->renderChart: Chart updated with new data.');
        }

        this.updateDataPointsTable(chartData, displayUnit, decimalPlaces);
    }

    updateDataPointsTable(chartData, displayUnit, decimalPlaces) {
        const sensorId = this.graphCard.dataset.sensorId;
        const dataPointsBody = document.getElementById(`data-points-body-${sensorId}`);
        const dataPointsHeader = document.getElementById(`data-points-value-header-${sensorId}`);
        const dataPointsContainer = document.getElementById(`graph-datapoints-container-${sensorId}`);

        // Stats elements
        const statsCountEl = document.getElementById(`dp-stats-count-${sensorId}`);
        const statsFirstEl = document.getElementById(`dp-stats-first-${sensorId}`);
        const statsLastEl = document.getElementById(`dp-stats-last-${sensorId}`);
        const statsSourceEl = document.getElementById(`dp-stats-source-${sensorId}`);
        const statsQueryTimeEl = document.getElementById(`dp-stats-query-time-${sensorId}`);
        const statsRangeEl = document.getElementById(`dp-stats-range-${sensorId}`);


        if (this.debug) {
            console.log('SensorChart->updateDataPointsTable: Checking queryRange', JSON.parse(JSON.stringify(this.queryRange)));
        }

        let tableHeader = `Value (${displayUnit})`;
        const isBoolean = this.sensorConfig && this.sensorConfig.is_boolean;
        if (this.debug) {
            console.log('SensorChart->updateDataPointsTable: isBoolean check:', isBoolean);
        }

        if (isBoolean) {
            tableHeader = 'State';
        }
        if (dataPointsHeader) dataPointsHeader.textContent = tableHeader;

        if (dataPointsBody && dataPointsContainer) {
            dataPointsBody.innerHTML = ''; // Clear previous data

            if (chartData.length > 0) {
                dataPointsContainer.classList.remove('d-none');

                // Populate stats without icons
                if (statsCountEl) statsCountEl.innerHTML = `Record Count: <strong>${chartData.length}</strong>`;
                if (statsFirstEl) statsFirstEl.innerHTML = `First: <strong>${window.utils.formatTimestamp(chartData[0].x, true)}</strong>`;
                if (statsLastEl) statsLastEl.innerHTML = `Last: <strong>${window.utils.formatTimestamp(chartData[chartData.length - 1].x, true)}</strong>`;
                if (statsSourceEl) statsSourceEl.innerHTML = `Source: <strong>${this.sensorConfig.data_store}</strong>`;
                if (statsQueryTimeEl && this.queryTimeMs !== undefined) {
                    statsQueryTimeEl.innerHTML = `Query: <strong>${this.queryTimeMs}ms</strong>`;
                }
                if (statsRangeEl && this.queryRange && this.queryRange.start_date && this.queryRange.end_date) {
                    const start = window.utils.formatTimestamp(this.queryRange.start_date, true);
                    const end = window.utils.formatTimestamp(this.queryRange.end_date, true);
                    statsRangeEl.innerHTML = `Range: <strong>${start} to ${end}</strong>`;
                }

                // To show newest first in the table, we iterate over a reversed copy of the array.
                chartData.slice().reverse().forEach(dp => {
                    const row = dataPointsBody.insertRow();
                    const cell1 = row.insertCell(0);
                    const cell2 = row.insertCell(1);

                    cell1.textContent = window.utils.formatTimestamp(dp.x);
                    let valueDisplay;
                    if (isBoolean) {
                        valueDisplay = getBooleanDisplay(dp.y, this.sensorConfig.sensor_type_name);
                    } else {
                        valueDisplay = dp.y.toFixed(decimalPlaces);
                    }
                    cell2.textContent = valueDisplay;
                });

            } else {
                dataPointsContainer.classList.add('d-none');
            }
        }
    }

    // --- Event Listeners and Initialization ---
    initialize() {
        if (this.debug) console.log("SensorChart: Initializing for graph card:", this.graphCard.id);
        if (!this.graphCard) {
            console.error("SensorChart: Initialization failed, graph card not found.");
            return;
        }
        if (this.debug) console.log("SensorChart: Initializing flatpickr and event listeners.");
        this.fp_start = flatpickr("#start-date-picker", {
            enableTime: true,
            altInput: true,
            altFormat: "M j, Y H:i",
            dateFormat: "Y-m-d H:i",
            time_24hr: true,
            onChange: (selectedDates, dateStr, instance) => {
                if (this.fp_end) {
                    this.fp_end.set("minDate", selectedDates[0]);
                }
            }
        });
        this.fp_end = flatpickr("#end-date-picker", {
            enableTime: true,
            altInput: true,
            altFormat: "M j, Y H:i",
            dateFormat: "Y-m-d H:i",
            time_24hr: true,
            onChange: (selectedDates, dateStr, instance) => {
                if (this.fp_start) {
                    this.fp_start.set("maxDate", selectedDates[0]);
                }
            }
        });

        // Set initial date range to last 3 days
        const end = new Date();
        const start = new Date();
        start.setDate(start.getDate() - 3);
        this.fp_start.setDate(start, false);
        this.fp_end.setDate(end, false);
        if (this.debug) console.log("SensorChart: Initial date range set:", start, "to", end);

        // Set the initial query range and trigger a fetch
        this.queryRange = { start: start, end: end };
        const applyBtn = document.getElementById('apply-date-range');
        if (applyBtn) {
            // Use the 'active' preset button's logic if available, otherwise click Apply
            const activePreset = document.querySelector('.date-range-preset.active');
            if (activePreset) {
                activePreset.click();
            } else {
                // Default to clicking the first preset button if none are active
                const firstPreset = document.querySelector('.date-range-preset');
                if (firstPreset) {
                    firstPreset.click();
                } else {
                     applyBtn.click();
                }
            }
        }

        this.setupEventListeners();
    }

    setupEventListeners() {
        if (this.debug) console.log("SensorChart: Setting up event listeners.");
        const applyBtn = document.getElementById('apply-date-range');
        if(applyBtn) {
            if (this.debug) console.log("SensorChart: Attaching listener to Apply button.");
            applyBtn.addEventListener('click', () => {
                if (this.debug) console.log("SensorChart: Apply button clicked.");
                document.querySelectorAll('.date-range-preset').forEach(btn => btn.classList.remove('active'));

                const startDt = this.fp_start.selectedDates[0];
                const endDt = this.fp_end.selectedDates[0];
                if (this.debug) console.log("SensorChart: Apply dates:", startDt, endDt);

                if (!startDt || !endDt) {
                    alert("Please select both a start and end date.");
                    return;
                }

                this.queryRange = { start: startDt, end: endDt };
                this.graphCard.dataset.startDate = startDt.toISOString();
                this.graphCard.dataset.endDate = endDt.toISOString();

                const apiUrl = new URL(this.graphCard.dataset.apiUrl, window.location.origin);
                apiUrl.searchParams.delete('delta');
                apiUrl.searchParams.set('start_date', this.graphCard.dataset.startDate);
                apiUrl.searchParams.set('end_date', this.graphCard.dataset.endDate);

                this.fetchData(apiUrl.toString());
            });
        }

        const showNaToggle = document.getElementById(`show-na-toggle-${this.graphCard.dataset.sensorId}`);
        if (showNaToggle) {
            showNaToggle.addEventListener('change', () => {
                const tempUnitSelect = document.getElementById('temp-unit-select');
                if (tempUnitSelect && tempUnitSelect.value !== this.originalUnit.replace('°','')) {
                    tempUnitSelect.dispatchEvent(new Event('change'));
                } else {
                    this.renderChart(this.originalData, this.currentGraphType);
                }
            });
        }

        this.graphCard.addEventListener('graphTypeChange', (e) => {
            if (this.debug) console.log('sensor-chart.js: Received graphTypeChange event with detail:', e.detail);
            this.currentGraphType = e.detail.newType;
            const tempUnitSelect = document.getElementById('temp-unit-select');
            if (tempUnitSelect && tempUnitSelect.value !== this.originalUnit.replace('°','')) {
                 tempUnitSelect.dispatchEvent(new Event('change'));
            } else {
                this.renderChart(this.originalData, this.currentGraphType);
            }
        });
        if (this.debug) console.log('sensor-chart.js: Event listener for graphTypeChange added to graphCard.');

        if (this.debug) console.log("SensorChart: Attaching listeners to date range preset buttons.");
        document.querySelectorAll('.date-range-preset').forEach(button => {
            button.addEventListener('click', () => {
                if (this.debug) console.log("SensorChart: Date range preset button clicked:", button.dataset.range);
                document.querySelectorAll('.date-range-preset').forEach(btn => btn.classList.remove('active'));
                button.classList.add('active');

                const range = button.dataset.range;

                const end = new Date();
                const start = new Date();
                if (range.includes('h')) {
                    start.setHours(start.getHours() - parseInt(range));
                } else if (range.includes('d')) {
                    start.setDate(start.getDate() - parseInt(range));
                }

                this.queryRange = { start: start, end: end };
                this.graphCard.dataset.startDate = start.toISOString();
                this.graphCard.dataset.endDate = end.toISOString();

                // Update flatpickr instances
                this.fp_start.setDate(start, false);
                this.fp_end.setDate(end, false);

                const apiUrl = new URL(this.graphCard.dataset.apiUrl, window.location.origin);
                apiUrl.searchParams.delete('start_date');
                apiUrl.searchParams.delete('end_date');
                apiUrl.searchParams.set('delta', range);
                this.fetchData(apiUrl.toString());
            });
        });

        const tempUnitSelect = document.getElementById('temp-unit-select');
        if (tempUnitSelect) {
            if (this.debug) console.log("SensorChart: Attaching listener to temperature unit selector.");
            tempUnitSelect.addEventListener('change', () => {
                const selectedUnit = tempUnitSelect.value;
                if (this.debug) console.log("SensorChart: Temperature unit changed to:", selectedUnit);

                let dataToRender = [];

                if ((selectedUnit === 'C' && this.originalUnit.includes('C')) || (selectedUnit === 'F' && this.originalUnit.includes('F'))) {
                    dataToRender = this.originalData;
                    this.graphCard.dataset.sensorUnit = this.originalUnit;
                } else {
                    if (selectedUnit === 'F' && this.originalUnit.includes('C')) {
                        dataToRender = this.originalData.map(p => [p[0], this.celsiusToFahrenheit(p[1])]);
                        this.graphCard.dataset.sensorUnit = '°F';
                    } else if (selectedUnit === 'C' && this.originalUnit.includes('F')) {
                        dataToRender = this.originalData.map(p => [p[0], this.fahrenheitToCelsius(p[1])]);
                        this.graphCard.dataset.sensorUnit = '°C';
                    } else {
                        dataToRender = this.originalData;
                        this.graphCard.dataset.sensorUnit = this.originalUnit;
                    }
                }
                this.renderChart(dataToRender, this.currentGraphType);
            });
        }
    }
}
