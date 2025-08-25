class SensorChart {
    constructor(graphCardId) {
        this.graphCard = document.getElementById(graphCardId);
        if (!this.graphCard) {
            console.error('Graph card not found!');
            return;
        }

        this.sensorChartConfig = { debug: true };
        this.chart = null;
        this.originalData = [];
        this.currentGraphType = this.graphCard.dataset.graphType;
        this.originalUnit = this.graphCard.dataset.sensorUnit;
        this.sensorType = this.graphCard.dataset.sensorType;

        this.initialize();
    }

    // --- Conversion Helpers ---
    celsiusToFahrenheit(celsius) { return celsius * 9 / 5 + 32; }
    fahrenheitToCelsius(fahrenheit) { return (fahrenheit - 32) * 5 / 9; }

    // --- UI Helper ---
    showLoadingState(isLoading) {
        const chartCanvas = document.getElementById('sensorChart');
        const sensorId = this.graphCard.dataset.sensorId;
        const dataPointsBody = document.getElementById(`data-points-body-${sensorId}`);

        if (isLoading) {
            if (this.chart) this.chart.destroy();
            const ctx = chartCanvas.getContext('2d');
            ctx.clearRect(0, 0, chartCanvas.width, chartCanvas.height);
            ctx.textAlign = "center";
            ctx.fillText("Loading...", chartCanvas.width / 2, chartCanvas.height / 2);

            if (dataPointsBody) {
                dataPointsBody.innerHTML = `<tr><td colspan="2" class="text-center py-5"><div class="spinner-border spinner-border-sm" role="status"><span class="visually-hidden">Loading...</span></div><span class="ms-2">Loading data...</span></td></tr>`;
            }
        }
    }

    // --- Data Fetching and Processing ---
    async fetchData(apiUrl) {
        this.showLoadingState(true);

        if (!apiUrl) {
            console.error('API URL is missing.');
            this.renderChart([], this.currentGraphType);
            this.showLoadingState(false);
            return;
        }
        try {
            const response = await window.utils.fetchWithCSRF(apiUrl);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            
            const responseData = await response.json();
            
            this.currentGraphType = responseData.sensor.graph_type;
            this.graphCard.dataset.sensorUnit = responseData.sensor.unit || 'N/A';
            this.originalUnit = this.graphCard.dataset.sensorUnit;

            this.originalData = responseData.data_points.map(p => [new Date(p[0]), p[1]]);
            
            const tempUnitSelect = document.getElementById('temp-unit-select');
            if (tempUnitSelect && tempUnitSelect.value !== this.originalUnit.replace('°','')) {
                tempUnitSelect.dispatchEvent(new Event('change'));
            } else {
                this.renderChart(this.originalData, this.currentGraphType);
            }
        } catch (error) {
            console.error('Error fetching or rendering chart:', error);
            this.renderChart([], this.currentGraphType);
        } finally {
            this.showLoadingState(false);
        }
    }

    // --- Chart Rendering ---
    renderChart(data, type) {
        const chartCanvas = document.getElementById('sensorChart');
        if (!chartCanvas) return;
        
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

        this.chart = new Chart(chartCanvas.getContext('2d'), {
            type: chartType,
            data: {
                datasets: [{
                    label: `${sensorName} (${deviceName})`,
                    data: chartData,
                    borderColor: 'rgba(75, 192, 192, 1)',
                    backgroundColor: 'rgba(75, 192, 192, 0.2)',
                    fill: chartType === 'line',
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        type: 'time',
                        time: { unit: 'day', tooltipFormat: 'MMM D, YYYY, h:mm:ss a' },
                        title: { display: true, text: 'Timestamp' }
                    },
                    y: yAxisOptions
                },
                plugins: {
                    legend: {
                        position: 'top',
                        align: 'end',
                        labels: { usePointStyle: true, pointStyle: 'circle', padding: 10 }
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
            }
        });

        this.updateDataPointsTable(chartData, displayUnit, decimalPlaces);
    }

    updateDataPointsTable(chartData, displayUnit, decimalPlaces) {
        const sensorId = this.graphCard.dataset.sensorId;
        const dataPointsBody = document.getElementById(`data-points-body-${sensorId}`);
        const dataPointsHeader = document.querySelector(`#data-points-container th:nth-child(2)`);

        if (dataPointsHeader) dataPointsHeader.textContent = `Value (${displayUnit})`;
        
        if (dataPointsBody) {
            if (chartData.length > 0) {
                let rows = '';
                chartData.slice().reverse().forEach(item => {
                    const valueDisplay = (item.y !== null && typeof item.y !== 'undefined') ? item.y.toFixed(decimalPlaces) : 'N/A';
                    rows += `<tr><td>${window.utils.formatTimestamp(item.x)}</td><td class="text-end">${valueDisplay}</td></tr>`;
                });
                dataPointsBody.innerHTML = rows;
            } else {
                dataPointsBody.innerHTML = '<tr><td colspan="2" class="text-center text-muted py-5">No data available for this time range.</td></tr>';
            }
        }
    }

    // --- Event Listeners and Initialization ---
    initialize() {
        document.addEventListener('DOMContentLoaded', () => {
            const initialApiUrl = new URL(this.graphCard.dataset.apiUrl, window.location.origin);
            const startDate = this.graphCard.dataset.startDate;
            const endDate = this.graphCard.dataset.endDate;
            const startDatePicker = document.getElementById('start-date-picker');
            const endDatePicker = document.getElementById('end-date-picker');

            if (startDate && endDate) {
                initialApiUrl.searchParams.set('start', startDate);
                initialApiUrl.searchParams.set('end', endDate);
                if (startDatePicker) startDatePicker.value = startDate.split('T')[0];
                if (endDatePicker) endDatePicker.value = endDate.split('T')[0];
            } else {
                initialApiUrl.searchParams.set('delta', '7d');
                const end = new Date();
                const start = new Date();
                start.setDate(end.getDate() - 7);
                if (startDatePicker) startDatePicker.value = start.toISOString().split('T')[0];
                if (endDatePicker) endDatePicker.value = end.toISOString().split('T')[0];
            }
            this.fetchData(initialApiUrl.toString());

            this.setupEventListeners();
        });
    }

    setupEventListeners() {
        this.graphCard.addEventListener('dateRangeApplied', (event) => this.fetchData(event.detail.apiUrl));

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

        document.querySelectorAll('.date-range-preset').forEach(button => {
            button.addEventListener('click', () => {
                document.querySelectorAll('.date-range-preset').forEach(btn => btn.classList.remove('active'));
                button.classList.add('active');

                const range = button.dataset.range;
                const apiUrl = new URL(this.graphCard.dataset.apiUrl, window.location.origin);
                apiUrl.searchParams.delete('start');
                apiUrl.searchParams.delete('end');
                apiUrl.searchParams.set('delta', range);
                this.fetchData(apiUrl.toString());

                const end = new Date();
                const start = new Date();
                if (range.includes('h')) start.setHours(start.getHours() - parseInt(range));
                else if (range.includes('d')) start.setDate(start.getDate() - parseInt(range));
                
                document.getElementById('start-date-picker').value = start.toISOString().split('T')[0];
                document.getElementById('end-date-picker').value = end.toISOString().split('T')[0];
            });
        });

        const tempUnitSelect = document.getElementById('temp-unit-select');
        if (tempUnitSelect) {
            tempUnitSelect.addEventListener('change', () => {
                const selectedUnit = tempUnitSelect.value;
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

// Initialize the chart object
if (document.getElementById('sensor-graph-card')) {
    new SensorChart('sensor-graph-card');
} 