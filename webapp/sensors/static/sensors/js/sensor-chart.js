console.log('--- SENSOR-CHART.JS v.DEBUG.3 LOADED ---');

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
        this.unitName = this.graphCard.dataset.sensorUnitName;
        this.sensorType = this.graphCard.dataset.sensorType;
        this.originalMinValue = this.graphCard.dataset.minValue !== undefined && this.graphCard.dataset.minValue !== '' ? parseFloat(this.graphCard.dataset.minValue) : null;
        this.originalMaxValue = this.graphCard.dataset.maxValue !== undefined && this.graphCard.dataset.maxValue !== '' ? parseFloat(this.graphCard.dataset.maxValue) : null;
        this.dataTable = null;
        this.sensorConfig = {};
        this.queryRange = {};
        this.selectedDataPoint = null; // For data point navigation
        this.td_start = null; // Tempus Dominus start picker
        this.td_end = null;   // Tempus Dominus end picker

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
        const loadingSpinner = document.getElementById(`graph-loading-${sensorId}`);
        const graphBody = document.getElementById(`graph-body-${sensorId}`);
        const graphFooter = document.getElementById(`graph-footer-${sensorId}`);

        if (isLoading) {
            if (placeholder) placeholder.classList.add('d-none');
            if (loadingSpinner) loadingSpinner.classList.remove('d-none');
            // Show the body when loading starts
            if (graphBody) graphBody.classList.remove('d-none');
            if (graphFooter) graphFooter.classList.remove('d-none');
        } else {
            if (loadingSpinner) loadingSpinner.classList.add('d-none');
        }
    }

    showToast(message, type = 'info') {
        if (window.showToast) {
            window.showToast(message, type);
        } else if (typeof bootstrap !== 'undefined' && document.getElementById('toast-container')) {
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
                this.queryRange = responseData.payload.query_range;

                if (this.debug) console.log('SensorChart: Stored sensorConfig:', this.sensorConfig);

                if (this.debug) {
                    console.log("Sensor Chart Data Payload:");
                    if (responseData.payload && responseData.payload.data_points && responseData.payload.data_points.length > 0) {
                        console.table(responseData.payload.data_points.slice(0, 5).concat(responseData.payload.data_points.slice(-5)));
                    } else {
                        console.log("No data points returned.");
                    }
                    console.log(`Query Time: ${responseData.payload.query_time_ms}ms`);
                }

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

                this.updateDataPointsTable(this.originalData.map(item => ({ x: item[0], y: item[1] })), this.originalUnit, this.graphCard.dataset.decimalPlaces);

                const tempUnitSelect = document.getElementById('temp-unit-select');
                if (tempUnitSelect && tempUnitSelect.value !== this.originalUnit.replace('°','')) {
                    tempUnitSelect.dispatchEvent(new Event('change'));
                } else {
                    this.renderChart(this.originalData, this.currentGraphType);
                }

                const warningEl = document.getElementById(`graph-warning-${this.graphCard.dataset.sensorId}`);
                if (warningEl) warningEl.classList.add('d-none');

                if (this.originalData.length === 0) {
                    this.showToast('No data found for the selected time range.', 'warning');
                } else {
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
        const graphBody = document.getElementById(`graph-body-${sensorId}`);
        const graphFooter = document.getElementById(`graph-footer-${sensorId}`);
        if (!chartCanvas) return;

        // Show body and footer
        if (graphBody) graphBody.classList.remove('d-none');
        if (graphFooter) graphFooter.classList.remove('d-none');

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
            return;
        }

        const displayUnit = this.graphCard.dataset.sensorUnit || '';
        const decimalPlaces = this.graphCard.dataset.decimalPlaces !== '' ? parseInt(this.graphCard.dataset.decimalPlaces) : 2;
        const sensorName = this.graphCard.dataset.sensorName || 'Sensor';
        const deviceName = this.graphCard.dataset.deviceName || 'Device';

        const isBoolean = this.sensorConfig && this.sensorConfig.is_boolean;
        if (this.debug) {
            console.log('SensorChart->renderChart: isBoolean check:', isBoolean);
        }

        let effectiveMin = this.originalMinValue;
        let effectiveMax = this.originalMaxValue;

        if (effectiveMin !== null || effectiveMax !== null) {
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

        let chartType = 'line';
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
        } else if (typeUpper === 'OVERLAY') {
            chartType = 'line';
            pointRadius = 6;
            showLine = true;
        }

        let yAxisTitle = `Value (${displayUnit})`;
        if (this.sensorConfig && this.sensorConfig.is_boolean) {
            yAxisTitle = 'State';
        }

        const yAxisOptions = { title: { display: true, text: yAxisTitle } };
        if (effectiveMin !== null) {
            yAxisOptions.min = effectiveMin;
        }
        if (effectiveMax !== null) {
            yAxisOptions.max = effectiveMax;
        }

        if (this.sensorType && this.sensorType.toLowerCase().includes('humidity')) {
            yAxisOptions.min = 0;
            yAxisOptions.max = 100;
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
                yAxisOptions: JSON.parse(JSON.stringify(yAxisOptions)),
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

        if (typeUpper === 'ALARM_BAR') {
            datasetConfig.backgroundColor = 'rgba(255, 99, 132, 0.5)';
            datasetConfig.borderColor = 'rgba(255, 99, 132, 1)';
        }

        // Store reference to this for zoom callbacks
        const self = this;

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
                                hour: 'HH',
                                day: 'MMM d'
                            }
                        },
                        title: { display: true, text: 'Time' },
                        ticks: {
                            major: {
                                enabled: true
                            },
                            autoSkip: false,
                            maxRotation: 0,
                            callback: function(value, index, ticks) {
                                const date = new Date(value);
                                const unit = timeStep.unit;
                                const stepSize = timeStep.stepSize;

                                if (unit === 'hour') {
                                    if (date.getHours() % stepSize !== 0) return '';
                                } else if (unit === 'minute') {
                                    if (date.getMinutes() % stepSize !== 0) return '';
                                }

                                if (date.getHours() === 0 && date.getMinutes() === 0) {
                                    return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(date);
                                }
                                const durationHours = (end.getTime() - start.getTime()) / (1000 * 60 * 60);
                                if (durationHours > 48) {
                                    return new Intl.DateTimeFormat(undefined, { hour: '2-digit', hour12: false }).format(date);
                                }
                                if (date.getMinutes() !== 0) {
                                    return new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit', hour12: false }).format(date);
                                }
                                return new Intl.DateTimeFormat(undefined, { hour: '2-digit', hour12: false }).format(date);
                            }
                        },
                        grid: {
                            color: function(context) {
                                if (context && context.tick && context.tick.major) {
                                    return 'rgba(218, 165, 32, 0.7)';
                                }
                                return 'rgba(0, 0, 0, 0.1)';
                            },
                            lineWidth: function(context) {
                                if (context && context.tick && context.tick.major) {
                                    return 2;
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
                    },
                    // Zoom plugin configuration
                    zoom: {
                        zoom: {
                            drag: {
                                enabled: true,
                                backgroundColor: 'rgba(75, 192, 192, 0.3)',
                                borderColor: 'rgba(75, 192, 192, 1)',
                                borderWidth: 1
                            },
                            mode: 'x',
                            onZoomComplete: function({ chart }) {
                                // Show reset zoom button
                                const resetBtn = document.getElementById('reset-zoom');
                                if (resetBtn) resetBtn.classList.remove('d-none');

                                // Update date pickers with new range
                                const xScale = chart.scales.x;
                                const newStart = new Date(xScale.min);
                                const newEnd = new Date(xScale.max);

                                if (self.td_start && self.td_end) {
                                    self.td_start.dates.setValue(tempusDominus.DateTime.convert(newStart));
                                    self.td_end.dates.setValue(tempusDominus.DateTime.convert(newEnd));
                                }

                                // Update dataset attributes
                                self.graphCard.dataset.startDate = newStart.toISOString();
                                self.graphCard.dataset.endDate = newEnd.toISOString();

                                // Clear preset button active state
                                document.querySelectorAll('.date-range-preset').forEach(btn => btn.classList.remove('active'));
                            }
                        },
                        pan: {
                            enabled: false
                        }
                    }
                }
            },
            plugins: [timezonePlugin]
        });

        this.chart.data.datasets[0].data = chartData;
        this.chart.update();
        if (this.debug) {
            console.log('SensorChart->renderChart: Chart updated with new data.');
        }

        this.updateDataPointsTable(chartData, displayUnit, decimalPlaces);
    }

    // Reset zoom to original range
    resetZoom() {
        if (this.chart) {
            this.chart.resetZoom();
            const resetBtn = document.getElementById('reset-zoom');
            if (resetBtn) resetBtn.classList.add('d-none');

            // Restore original date range from query
            if (this.queryRange && this.queryRange.start && this.queryRange.end) {
                if (this.td_start && this.td_end) {
                    this.td_start.dates.setValue(tempusDominus.DateTime.convert(this.queryRange.start));
                    this.td_end.dates.setValue(tempusDominus.DateTime.convert(this.queryRange.end));
                }
                this.graphCard.dataset.startDate = this.queryRange.start.toISOString();
                this.graphCard.dataset.endDate = this.queryRange.end.toISOString();
            }
        }
    }

    // Zoom to a specific data point with adjustable window
    zoomToDataPoint(timestamp, windowMinutes = 30) {
        if (!this.chart || !timestamp) return;

        const targetTime = new Date(timestamp).getTime();
        const windowMs = windowMinutes * 60 * 1000;
        const newStart = new Date(targetTime - windowMs);
        const newEnd = new Date(targetTime + windowMs);

        this.selectedDataPoint = timestamp;

        // Update chart zoom
        this.chart.options.scales.x.min = newStart.getTime();
        this.chart.options.scales.x.max = newEnd.getTime();
        this.chart.update();

        // Update date pickers
        if (this.td_start && this.td_end) {
            this.td_start.dates.setValue(tempusDominus.DateTime.convert(newStart));
            this.td_end.dates.setValue(tempusDominus.DateTime.convert(newEnd));
        }

        // Update dataset attributes
        this.graphCard.dataset.startDate = newStart.toISOString();
        this.graphCard.dataset.endDate = newEnd.toISOString();

        // Show reset zoom button
        const resetBtn = document.getElementById('reset-zoom');
        if (resetBtn) resetBtn.classList.remove('d-none');

        // Clear preset button active state
        document.querySelectorAll('.date-range-preset').forEach(btn => btn.classList.remove('active'));

        // Show the navigation controls
        this.showDataPointNavigation(timestamp);
    }

    // Adjust the current view by a time offset
    adjustTimeWindow(offsetMs) {
        if (!this.chart) return;

        const currentStart = new Date(this.graphCard.dataset.startDate);
        const currentEnd = new Date(this.graphCard.dataset.endDate);

        const newStart = new Date(currentStart.getTime() + offsetMs);
        const newEnd = new Date(currentEnd.getTime() + offsetMs);

        // Update chart
        this.chart.options.scales.x.min = newStart.getTime();
        this.chart.options.scales.x.max = newEnd.getTime();
        this.chart.update();

        // Update date pickers
        if (this.td_start && this.td_end) {
            this.td_start.dates.setValue(tempusDominus.DateTime.convert(newStart));
            this.td_end.dates.setValue(tempusDominus.DateTime.convert(newEnd));
        }

        // Update dataset attributes
        this.graphCard.dataset.startDate = newStart.toISOString();
        this.graphCard.dataset.endDate = newEnd.toISOString();
    }

    // Show data point navigation controls
    showDataPointNavigation(timestamp) {
        const sensorId = this.graphCard.dataset.sensorId;
        let navContainer = document.getElementById(`datapoint-nav-${sensorId}`);

        if (!navContainer) {
            // Create navigation container if it doesn't exist
            const dataPointsCard = document.getElementById(`graph-datapoints-${sensorId}`);
            if (dataPointsCard) {
                const cardHeader = dataPointsCard.querySelector('.card-header');
                if (cardHeader) {
                    navContainer = document.createElement('div');
                    navContainer.id = `datapoint-nav-${sensorId}`;
                    navContainer.className = 'alert alert-info py-2 px-3 mb-0 mt-2';
                    cardHeader.appendChild(navContainer);
                }
            }
        }

        if (navContainer) {
            const formattedTime = window.utils ? window.utils.formatTimestamp(timestamp, true) : new Date(timestamp).toLocaleString();
            navContainer.innerHTML = `
                <div class="d-flex flex-wrap align-items-center justify-content-between gap-2">
                    <div class="d-flex align-items-center">
                        <i class="bi bi-crosshair me-2"></i>
                        <span class="small fw-bold">Viewing: ${formattedTime}</span>
                    </div>
                    <div class="btn-group btn-group-sm" role="group" aria-label="Time adjustment">
                        <button type="button" class="btn btn-outline-secondary time-adjust" data-offset="-86400000" title="-1 day">
                            <i class="bi bi-dash-circle"></i> 1d
                        </button>
                        <button type="button" class="btn btn-outline-secondary time-adjust" data-offset="-21600000" title="-6 hours">
                            <i class="bi bi-dash-circle"></i> 6h
                        </button>
                        <button type="button" class="btn btn-outline-secondary time-adjust" data-offset="-3600000" title="-1 hour">
                            <i class="bi bi-dash-circle"></i> 1h
                        </button>
                        <button type="button" class="btn btn-outline-secondary time-adjust" data-offset="-1800000" title="-30 min">
                            <i class="bi bi-dash-circle"></i> 30m
                        </button>
                        <button type="button" class="btn btn-outline-secondary time-adjust" data-offset="-900000" title="-15 min">
                            <i class="bi bi-dash-circle"></i> 15m
                        </button>
                        <button type="button" class="btn btn-outline-secondary time-adjust" data-offset="-300000" title="-5 min">
                            <i class="bi bi-dash-circle"></i> 5m
                        </button>
                        <span class="btn btn-light disabled"><i class="bi bi-grip-vertical"></i></span>
                        <button type="button" class="btn btn-outline-secondary time-adjust" data-offset="300000" title="+5 min">
                            <i class="bi bi-plus-circle"></i> 5m
                        </button>
                        <button type="button" class="btn btn-outline-secondary time-adjust" data-offset="900000" title="+15 min">
                            <i class="bi bi-plus-circle"></i> 15m
                        </button>
                        <button type="button" class="btn btn-outline-secondary time-adjust" data-offset="1800000" title="+30 min">
                            <i class="bi bi-plus-circle"></i> 30m
                        </button>
                        <button type="button" class="btn btn-outline-secondary time-adjust" data-offset="3600000" title="+1 hour">
                            <i class="bi bi-plus-circle"></i> 1h
                        </button>
                        <button type="button" class="btn btn-outline-secondary time-adjust" data-offset="21600000" title="+6 hours">
                            <i class="bi bi-plus-circle"></i> 6h
                        </button>
                        <button type="button" class="btn btn-outline-secondary time-adjust" data-offset="86400000" title="+1 day">
                            <i class="bi bi-plus-circle"></i> 1d
                        </button>
                    </div>
                    <button type="button" class="btn btn-sm btn-outline-danger" id="close-datapoint-nav-${sensorId}">
                        <i class="bi bi-x-lg"></i>
                    </button>
                </div>
            `;

            // Add event listeners for time adjustment buttons
            navContainer.querySelectorAll('.time-adjust').forEach(btn => {
                btn.addEventListener('click', () => {
                    const offset = parseInt(btn.dataset.offset);
                    this.adjustTimeWindow(offset);
                });
            });

            // Close button
            const closeBtn = document.getElementById(`close-datapoint-nav-${sensorId}`);
            if (closeBtn) {
                closeBtn.addEventListener('click', () => {
                    navContainer.remove();
                    this.selectedDataPoint = null;
                });
            }
        }
    }

    updateDataPointsTable(chartData, displayUnit, decimalPlaces) {
        const sensorId = this.graphCard.dataset.sensorId;
        const dataPointsBody = document.getElementById(`data-points-body-${sensorId}`);
        const dataPointsHeader = document.getElementById(`data-points-value-header-${sensorId}`);
        const dataPointsContainer = document.getElementById(`graph-datapoints-container-${sensorId}`);

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
            dataPointsBody.innerHTML = '';

            if (chartData.length > 0) {
                dataPointsContainer.classList.remove('d-none');

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

                // Store reference for click handler
                const self = this;

                chartData.slice().reverse().forEach(dp => {
                    const row = dataPointsBody.insertRow();
                    row.style.cursor = 'pointer';
                    row.classList.add('datapoint-row');
                    row.dataset.timestamp = dp.x.toISOString ? dp.x.toISOString() : new Date(dp.x).toISOString();

                    const cell1 = row.insertCell(0);
                    const cell2 = row.insertCell(1);

                    cell1.innerHTML = `<i class="bi bi-crosshair text-muted me-1" title="Click to zoom to this point"></i>${window.utils.formatTimestamp(dp.x)}`;
                    let valueDisplay;
                    if (isBoolean) {
                        valueDisplay = getBooleanDisplay(dp.y, this.sensorConfig.sensor_type_name);
                    } else {
                        valueDisplay = dp.y.toFixed(decimalPlaces);
                    }
                    cell2.textContent = valueDisplay;

                    // Add click handler for row
                    row.addEventListener('click', () => {
                        // Remove highlight from other rows
                        dataPointsBody.querySelectorAll('.table-primary').forEach(r => r.classList.remove('table-primary'));
                        row.classList.add('table-primary');
                        self.zoomToDataPoint(row.dataset.timestamp);
                    });
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
        if (this.debug) console.log("SensorChart: Initializing Tempus Dominus and event listeners.");

        // Initialize Tempus Dominus date pickers
        const startPickerEl = document.getElementById('start-date-picker');
        const endPickerEl = document.getElementById('end-date-picker');

        // Tempus Dominus configuration
        const tdConfig = {
            display: {
                viewMode: 'calendar',
                components: {
                    calendar: true,
                    date: true,
                    month: true,
                    year: true,
                    decades: true,
                    clock: true,
                    hours: true,
                    minutes: true,
                    seconds: false
                },
                icons: {
                    type: 'icons',
                    time: 'bi bi-clock',
                    date: 'bi bi-calendar',
                    up: 'bi bi-chevron-up',
                    down: 'bi bi-chevron-down',
                    previous: 'bi bi-chevron-left',
                    next: 'bi bi-chevron-right',
                    today: 'bi bi-calendar-check',
                    clear: 'bi bi-trash',
                    close: 'bi bi-x-lg'
                },
                sideBySide: true,
                theme: 'auto',
                buttons: {
                    today: true,
                    clear: false,
                    close: true
                }
            },
            localization: {
                hourCycle: 'h23',
                format: 'yyyy-MM-dd HH:mm'
            },
            allowInputToggle: true
        };

        if (startPickerEl && typeof tempusDominus !== 'undefined') {
            this.td_start = new tempusDominus.TempusDominus(startPickerEl, tdConfig);

            // Click on input to open picker
            startPickerEl.addEventListener('click', () => {
                if (this.td_start) this.td_start.show();
            });

            // Make input directly editable on blur
            startPickerEl.addEventListener('blur', () => {
                const val = startPickerEl.value;
                if (val) {
                    const parsed = new Date(val);
                    if (!isNaN(parsed.getTime())) {
                        this.td_start.dates.setValue(tempusDominus.DateTime.convert(parsed));
                    }
                }
            });
        }

        if (endPickerEl && typeof tempusDominus !== 'undefined') {
            this.td_end = new tempusDominus.TempusDominus(endPickerEl, tdConfig);

            // Click on input to open picker
            endPickerEl.addEventListener('click', () => {
                if (this.td_end) this.td_end.show();
            });

            // Make input directly editable on blur
            endPickerEl.addEventListener('blur', () => {
                const val = endPickerEl.value;
                if (val) {
                    const parsed = new Date(val);
                    if (!isNaN(parsed.getTime())) {
                        this.td_end.dates.setValue(tempusDominus.DateTime.convert(parsed));
                    }
                }
            });
        }

        // Set initial date range to last 3 days
        const end = new Date();
        const start = new Date();
        start.setDate(start.getDate() - 3);

        if (this.td_start && this.td_end) {
            this.td_start.dates.setValue(tempusDominus.DateTime.convert(start));
            this.td_end.dates.setValue(tempusDominus.DateTime.convert(end));
        }
        if (this.debug) console.log("SensorChart: Initial date range set:", start, "to", end);

        this.queryRange = { start: start, end: end };

        this.setupEventListeners();

        // Trigger initial data load - click first preset to set dates, then Graph to fetch
        const firstPreset = document.querySelector('.date-range-preset');
        const applyBtn = document.getElementById('apply-date-range');
        if (firstPreset) {
            firstPreset.click(); // Sets dates only
        }
        if (applyBtn) {
            applyBtn.click(); // Fetches data
        }
    }

    // Helper to get date from Tempus Dominus picker
    getPickerDate(picker) {
        if (!picker || !picker.dates || !picker.dates.lastPicked) {
            return null;
        }
        return picker.dates.lastPicked;
    }

    setupEventListeners() {
        if (this.debug) console.log("SensorChart: Setting up event listeners.");

        // Apply/Graph button
        const applyBtn = document.getElementById('apply-date-range');
        if (applyBtn) {
            if (this.debug) console.log("SensorChart: Attaching listener to Apply button.");
            applyBtn.addEventListener('click', () => {
                if (this.debug) console.log("SensorChart: Apply button clicked.");
                document.querySelectorAll('.date-range-preset').forEach(btn => btn.classList.remove('active'));

                let startDt, endDt;

                if (this.td_start && this.td_end) {
                    const startPicked = this.getPickerDate(this.td_start);
                    const endPicked = this.getPickerDate(this.td_end);
                    startDt = startPicked ? startPicked : null;
                    endDt = endPicked ? endPicked : null;
                }

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

                // Clear pending visual state
                if (this.clearPendingState) this.clearPendingState();

                this.fetchData(apiUrl.toString());
            });
        }

        // Calendar icon click to toggle pickers
        const startPickerToggle = document.getElementById('start-picker-toggle');
        if (startPickerToggle && this.td_start) {
            startPickerToggle.addEventListener('click', () => {
                this.td_start.toggle();
            });
        }

        const endPickerToggle = document.getElementById('end-picker-toggle');
        if (endPickerToggle && this.td_end) {
            endPickerToggle.addEventListener('click', () => {
                this.td_end.toggle();
            });
        }

        // Snap to midnight buttons - Start date
        const snapStartBtn = document.getElementById('snap-start-midnight');
        if (snapStartBtn) {
            snapStartBtn.addEventListener('click', () => {
                if (this.td_start) {
                    const currentDate = this.getPickerDate(this.td_start);
                    if (currentDate) {
                        const snapped = new Date(currentDate);
                        snapped.setHours(0, 0, 0, 0);
                        this.td_start.dates.setValue(tempusDominus.DateTime.convert(snapped));
                    }
                }
            });
        }

        // Snap to start of day (00:00) - End date
        const snapEndStartBtn = document.getElementById('snap-end-start-of-day');
        if (snapEndStartBtn) {
            snapEndStartBtn.addEventListener('click', () => {
                if (this.td_end) {
                    const currentDate = this.getPickerDate(this.td_end);
                    if (currentDate) {
                        const snapped = new Date(currentDate);
                        snapped.setHours(0, 0, 0, 0);
                        this.td_end.dates.setValue(tempusDominus.DateTime.convert(snapped));
                    }
                }
            });
        }

        // Snap to end of day (23:59) - End date
        const snapEndEndBtn = document.getElementById('snap-end-end-of-day');
        if (snapEndEndBtn) {
            snapEndEndBtn.addEventListener('click', () => {
                if (this.td_end) {
                    const currentDate = this.getPickerDate(this.td_end);
                    if (currentDate) {
                        const snapped = new Date(currentDate);
                        snapped.setHours(23, 59, 59, 999);
                        this.td_end.dates.setValue(tempusDominus.DateTime.convert(snapped));
                    }
                }
            });
        }

        // Reset zoom button
        const resetZoomBtn = document.getElementById('reset-zoom');
        if (resetZoomBtn) {
            resetZoomBtn.addEventListener('click', () => {
                this.resetZoom();
            });
        }

        // Show NA toggle
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

        // Graph type change
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

        // Date range preset buttons - only set dates, do NOT submit
        if (this.debug) console.log("SensorChart: Attaching listeners to date range preset buttons.");
        const startPickerEl = document.getElementById('start-date-picker');
        const endPickerEl = document.getElementById('end-date-picker');

        const graphBtn = document.getElementById('apply-date-range');

        // Helper to show "pending update" visual state
        const showPendingState = () => {
            if (startPickerEl) {
                startPickerEl.classList.add('border-warning', 'border-2');
            }
            if (endPickerEl) {
                endPickerEl.classList.add('border-warning', 'border-2');
            }
            if (graphBtn) {
                graphBtn.classList.remove('btn-primary');
                graphBtn.classList.add('btn-warning', 'fw-bold');
                graphBtn.innerHTML = '<i class="bi bi-arrow-repeat me-1"></i>Update';
            }
        };

        // Helper to clear pending state (after Graph clicked)
        const clearPendingState = () => {
            if (startPickerEl) {
                startPickerEl.classList.remove('border-warning', 'border-2');
            }
            if (endPickerEl) {
                endPickerEl.classList.remove('border-warning', 'border-2');
            }
            if (graphBtn) {
                graphBtn.classList.remove('btn-warning', 'fw-bold');
                graphBtn.classList.add('btn-primary');
                graphBtn.innerHTML = '<i class="bi bi-graph-up me-1"></i>Graph';
            }
        };

        document.querySelectorAll('.date-range-preset').forEach(button => {
            button.addEventListener('click', () => {
                if (this.debug) console.log("SensorChart: Date range preset button clicked:", button.dataset.range);
                // Highlight the active preset button
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

                // Update Tempus Dominus pickers (no submit)
                if (this.td_start && this.td_end) {
                    this.td_start.dates.setValue(tempusDominus.DateTime.convert(start));
                    this.td_end.dates.setValue(tempusDominus.DateTime.convert(end));
                }

                // Show pending update visual cues
                showPendingState();
            });
        });

        // Clear preset highlight when user manually edits, but show pending state
        if (startPickerEl) {
            startPickerEl.addEventListener('input', () => {
                document.querySelectorAll('.date-range-preset').forEach(btn => btn.classList.remove('active'));
                showPendingState();
            });
        }
        if (endPickerEl) {
            endPickerEl.addEventListener('input', () => {
                document.querySelectorAll('.date-range-preset').forEach(btn => btn.classList.remove('active'));
                showPendingState();
            });
        }

        // Store clearPendingState for use in apply button handler
        this.clearPendingState = clearPendingState;

        // Temperature unit selector
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

        // Initialize Bootstrap tooltips
        const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
        tooltipTriggerList.forEach(el => new bootstrap.Tooltip(el));
    }
}
