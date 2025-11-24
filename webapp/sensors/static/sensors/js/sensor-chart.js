class SensorChart {
    constructor(graphCardId) {
        this.graphCard = document.getElementById(graphCardId);
        if (!this.graphCard) {
            console.error('Graph card not found!');
            return;
        }

        this.sensorChartConfig = { debug: false };
        this.chart = null;
        this.originalData = [];
        this.currentGraphType = this.graphCard.dataset.graphType;
        this.originalUnit = this.graphCard.dataset.sensorUnit;
        this.sensorType = this.graphCard.dataset.sensorType;
        this.dataTable = null;

        this.initialize();
    }

    // --- Conversion Helpers ---
    celsiusToFahrenheit(celsius) { return celsius * 9 / 5 + 32; }
    fahrenheitToCelsius(fahrenheit) { return (fahrenheit - 32) * 5 / 9; }

    // --- UI Helper ---
    showLoadingState(isLoading) {
        const sensorId = this.graphCard.dataset.sensorId;
        const placeholder = document.getElementById(`graph-placeholder-${sensorId}`);
        const content = document.getElementById(`graph-content-${sensorId}`);

        if (isLoading) {
            if (placeholder) placeholder.classList.add('d-none');
            if (content) content.classList.remove('d-none');

            const chartCanvas = document.getElementById('sensorChart');
            if (this.chart) this.chart.destroy();
            if (chartCanvas) {
                const ctx = chartCanvas.getContext('2d');
                ctx.clearRect(0, 0, chartCanvas.width, chartCanvas.height);
                ctx.textAlign = "center";
                ctx.fillText("Loading...", chartCanvas.width / 2, chartCanvas.height / 2);
            }
        }
    }

    // --- Data Fetching and Processing ---
    async fetchData(apiUrl) {
        console.log('SensorChart: fetchData called with URL:', apiUrl);
        this.showLoadingState(true);

        if (!apiUrl) {
            console.error('API URL is missing.');
            this.renderChart([], this.currentGraphType);
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
            console.log('Fetching data from URL:', url.toString());

            const response = await window.utils.fetchWithCSRF(url.toString());
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

            const responseData = await response.json();

            if (responseData.status !== 'success') {
                throw new Error(responseData.description || 'The server returned an error.');
            }

            const data = responseData.payload;

            // --- Log unexpected keys if in debug mode ---
            if (this.sensorChartConfig.debug) {
                const expectedKeys = ['sensor', 'query_range', 'query_time_ms', 'data_points'];
                const receivedKeys = Object.keys(data);
                const unexpectedKeys = receivedKeys.filter(key => !expectedKeys.includes(key));
                if (unexpectedKeys.length > 0) {
                    console.warn('Unexpected keys in API response payload:', unexpectedKeys);
                }
            }

            // --- Populate Footer Stats ---
            const queryTimeEl = document.getElementById('graph-query-time');
            if (queryTimeEl && data.query_time_ms) {
                queryTimeEl.textContent = `Data: ${data.query_time_ms.toFixed(0)}ms`;
            }

            const datapointCountEl = document.getElementById('datapoint-count');
            if (datapointCountEl && data.data_points) {
                datapointCountEl.textContent = `${data.data_points.length} points`;
            }

            const firstReadingEl = document.getElementById('first-reading-time');
            const lastReadingEl = document.getElementById('last-reading-time');
            if (data.data_points && data.data_points.length > 0) {
                const firstPoint = data.data_points[0][0];
                const lastPoint = data.data_points[data.data_points.length - 1][0];

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

            this.currentGraphType = data.sensor.graph_type;
            this.graphCard.dataset.sensorUnit = data.sensor.unit || 'N/A';
            this.originalUnit = this.graphCard.dataset.sensorUnit;

            this.originalData = data.data_points.map(p => [new Date(p[0]), p[1]]);

            const tempUnitSelect = document.getElementById('temp-unit-select');
            if (tempUnitSelect && tempUnitSelect.value !== this.originalUnit.replace('°','')) {
                tempUnitSelect.dispatchEvent(new Event('change'));
            } else {
                this.renderChart(this.originalData, this.currentGraphType);
            }
        } catch (error) {
            console.error('Error fetching or rendering chart:', error);
            const sensorId = this.graphCard.dataset.sensorId;
            const placeholder = document.getElementById(`graph-placeholder-${sensorId}`);
            const content = document.getElementById(`graph-content-${sensorId}`);
            if (placeholder) {
                placeholder.classList.remove('d-none');
                placeholder.innerHTML = `<i class="bi bi-exclamation-triangle-fill fs-1 text-danger"></i><p class="mt-2 text-danger">Failed to load graph data.</p>`;
            }
            if (content) content.classList.add('d-none');
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
        console.log(`SensorChart: renderChart called with ${data.length} data points and type: ${type}`);
        const sensorId = this.graphCard.dataset.sensorId;
        const placeholder = document.getElementById(`graph-placeholder-${sensorId}`);
        const content = document.getElementById(`graph-content-${sensorId}`);
        const chartCanvas = document.getElementById('sensorChart');
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
        const minValue = this.graphCard.dataset.minValue !== '' ? parseFloat(this.graphCard.dataset.minValue) : null;
        const maxValue = this.graphCard.dataset.maxValue !== '' ? parseFloat(this.graphCard.dataset.maxValue) : null;
        const decimalPlaces = this.graphCard.dataset.decimalPlaces !== '' ? parseInt(this.graphCard.dataset.decimalPlaces) : 2;
        const sensorName = this.graphCard.dataset.sensorName || 'Sensor';
        const deviceName = this.graphCard.dataset.deviceName || 'Device';

        if (this.chart) this.chart.destroy();

        const chartData = data.map(item => ({ x: item[0], y: item[1] }));
        const chartType = type === 'SCATTER' ? 'scatter' : (type === 'BAR' ? 'bar' : 'line');

        const yAxisOptions = { title: { display: true, text: `Value (${displayUnit})` } };
        if (minValue !== null) yAxisOptions.min = minValue;
        if (maxValue !== null) yAxisOptions.max = maxValue;
        if (this.sensorType && this.sensorType.toLowerCase().includes('humidity')) {
            yAxisOptions.min = 0;
            yAxisOptions.max = 100;
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

        this.chart = new Chart(chartCanvas.getContext('2d'), {
            type: chartType,
            data: {
                datasets: [{
                    label: `${sensorName} (${deviceName})`,
                    data: chartData,
                    borderColor: 'rgba(75, 192, 192, 1)',
                    backgroundColor: 'rgba(75, 192, 192, 0.2)',
                    fill: chartType === 'line',
                    tension: 0.1,
                    pointRadius: 2,
                    pointHoverRadius: 5
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
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
                                const stepHours = this.chart.options.scales.x.time.stepSize;

                                // Only draw labels that fall on our exact step interval
                                if (date.getHours() % stepHours !== 0) {
                                    return '';
                                }

                                if (date.getHours() === 0 && date.getMinutes() === 0) {
                                    return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(date);
                                }
                                // For multi-day views, only show the hour.
                                const durationHours = (this.max - this.min) / (1000 * 60 * 60);
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
                                if (context.tick.major) {
                                    return 'rgba(218, 165, 32, 0.7)'; // Dark gold for major ticks (midnight)
                                }
                                return 'rgba(0, 0, 0, 0.1)';
                            },
                            lineWidth: function(context) {
                                if (context.tick.major) {
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

        this.chart.data.datasets[0].data = chartData;
        this.chart.update();

        this.updateDataPointsTable(chartData, displayUnit, decimalPlaces);
    }

    updateDataPointsTable(chartData, displayUnit, decimalPlaces) {
        const sensorId = this.graphCard.dataset.sensorId;
        const dataPointsBody = document.getElementById(`data-points-body-${sensorId}`);
        const dataPointsHeader = document.getElementById(`data-points-value-header-${sensorId}`);
        const dataPointsCard = document.getElementById(`graph-datapoints-${sensorId}`);
        const dataTableElement = document.querySelector(`#graph-datapoints-${sensorId} table`);

        if (this.dataTable) {
            this.dataTable.destroy();
            this.dataTable = null;
        }

        if (dataPointsHeader) dataPointsHeader.textContent = `Value (${displayUnit})`;

        if (dataPointsBody && dataPointsCard) {
            dataPointsBody.innerHTML = '';

            if (chartData.length > 0) {
                dataPointsCard.classList.remove('d-none');

                let rows = [];
                chartData.slice().reverse().forEach(item => {
                    const valueDisplay = (item.y !== null && typeof item.y !== 'undefined') ? item.y.toFixed(decimalPlaces) : 'N/A';
                    rows.push([window.utils.formatTimestamp(item.x), valueDisplay]);
                });

                // Using the new library
                if (dataTableElement && window.simpleDatatables) {
                    this.dataTable = new simpleDatatables.DataTable(dataTableElement, {
                        data: {
                            headings: ["Timestamp", `Value (${displayUnit})`],
                            data: rows
                        },
                        searchable: false,
                        perPageSelect: false,
                        paging: false,
                        labels: {
                            noRows: "No data points found",
                            info: "Showing {start} to {end} of {rows} entries",
                        }
                    });
                }
            } else {
                dataPointsCard.classList.add('d-none');
            }
        }
    }

    // --- Event Listeners and Initialization ---
    initialize() {
        console.log("SensorChart: Initializing for graph card:", this.graphCard.id);
        if (!this.graphCard) {
            console.error("SensorChart: Initialization failed, graph card not found.");
            return;
        }
        console.log("SensorChart: Initializing flatpickr and event listeners.");
        this.fp_start = flatpickr("#start-date-picker", {
            altInput: true,
            altFormat: "M j, Y",
            dateFormat: "Y-m-d",
            onChange: (selectedDates, dateStr, instance) => {
                if (this.fp_end) {
                    this.fp_end.set("minDate", selectedDates[0]);
                }
            }
        });
        this.fp_end = flatpickr("#end-date-picker", {
            altInput: true,
            altFormat: "M j, Y",
            dateFormat: "Y-m-d",
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
        console.log("SensorChart: Initial date range set:", start, "to", end);

        this.setupEventListeners();
    }

    setupEventListeners() {
        console.log("SensorChart: Setting up event listeners.");
        const applyBtn = document.getElementById('apply-date-range');
        if(applyBtn) {
            console.log("SensorChart: Attaching listener to Apply button.");
            applyBtn.addEventListener('click', () => {
                console.log("SensorChart: Apply button clicked.");
                document.querySelectorAll('.date-range-preset').forEach(btn => btn.classList.remove('active'));

                const startDt = this.fp_start.selectedDates[0];
                const endDt_raw = this.fp_end.selectedDates[0];
                console.log("SensorChart: Apply dates:", startDt, endDt_raw);

                if (!startDt || !endDt_raw) {
                    alert("Please select both a start and end date.");
                    return;
                }

                let endDt = new Date(endDt_raw.getTime());

                const today = new Date();
                if (endDt.getFullYear() === today.getFullYear() &&
                    endDt.getMonth() === today.getMonth() &&
                    endDt.getDate() === today.getDate()) {
                    endDt = today;
                } else {
                    endDt.setHours(23, 59, 59, 999);
                }

                this.graphCard.dataset.startDate = startDt.toISOString();
                this.graphCard.dataset.endDate = endDt.toISOString();

                const apiUrl = new URL(this.graphCard.dataset.apiUrl, window.location.origin);
                apiUrl.searchParams.delete('delta');
                apiUrl.searchParams.set('start_date', this.graphCard.dataset.startDate);
                apiUrl.searchParams.set('end_date', this.graphCard.dataset.endDate);

                this.fetchData(apiUrl.toString());
            });
        }

        this.graphCard.addEventListener('graphTypeChange', (e) => {
            if (this.sensorChartConfig.debug) console.log('sensor-chart.js: Received graphTypeChange event with detail:', e.detail);
            this.currentGraphType = e.detail.newType;
            const tempUnitSelect = document.getElementById('temp-unit-select');
            if (tempUnitSelect && tempUnitSelect.value !== this.originalUnit.replace('°','')) {
                 tempUnitSelect.dispatchEvent(new Event('change'));
            } else {
                this.renderChart(this.originalData, this.currentGraphType);
            }
        });
        if (this.sensorChartConfig.debug) console.log('sensor-chart.js: Event listener for graphTypeChange added to graphCard.');

        console.log("SensorChart: Attaching listeners to date range preset buttons.");
        document.querySelectorAll('.date-range-preset').forEach(button => {
            button.addEventListener('click', () => {
                console.log("SensorChart: Date range preset button clicked:", button.dataset.range);
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
            console.log("SensorChart: Attaching listener to temperature unit selector.");
            tempUnitSelect.addEventListener('change', () => {
                const selectedUnit = tempUnitSelect.value;
                console.log("SensorChart: Temperature unit changed to:", selectedUnit);
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
