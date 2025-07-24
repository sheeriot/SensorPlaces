/**
 * Live Counts Updater
 *
 * This script periodically fetches live counts for a specific place and updates
 * the UI with the latest data. It's designed to be used on pages that
 * display the live_counts_card.html partial.
 *
 * It requires a 'placeSlug' to be available in the global scope, which should
 * be set in the template that includes this script.
 */

const liveCountsUpdater = {
    config: {
        debug: false,
        updateInterval: 60000, // 1 minute
    },

    init(placeSlug) {
        if (!placeSlug) {
            if (this.config.debug) {
                console.error('LiveCountsUpdater: placeSlug is not defined.');
            }
            return;
        }

        this.placeSlug = placeSlug;
        this.startPolling();
    },

    startPolling() {
        if (this.config.debug) {
            console.log(`LiveCountsUpdater: Starting polling for place ${this.placeSlug} every ${this.config.updateInterval / 1000}s.`);
        }
        this.fetchCounts(); // Fetch immediately on init
        setInterval(() => this.fetchCounts(), this.config.updateInterval);
    },

    async fetchCounts() {
        if (this.config.debug) {
            console.log('LiveCountsUpdater: Fetching counts...');
        }
        try {
            const response = await fetch(`/api/${this.placeSlug}/stats/`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            this.updateUI(data);
        } catch (error) {
            if (this.config.debug) {
                console.error('LiveCountsUpdater: Error fetching counts:', error);
            }
        }
    },

    updateUI(data) {
        if (this.config.debug) {
            console.log('LiveCountsUpdater: Updating UI with data:', data);
        }
        this.updateCount('locations-active', data.locations_active_count);
        this.updateCount('locations-inactive', data.locations_inactive_count);
        this.updateCount('devices-active', data.devices_active_count);
        this.updateCount('devices-inactive', data.devices_inactive_count);
        this.updateCount('sensors-active', data.sensors_active_count);
        this.updateCount('sensors-inactive', data.sensors_inactive_count);
    },

    updateCount(elementId, newValue) {
        const element = document.getElementById(elementId);
        if (element) {
            element.textContent = newValue;
        } else if (this.config.debug) {
            console.warn(`LiveCountsUpdater: Element with ID '${elementId}' not found.`);
        }
    },
};

document.addEventListener('DOMContentLoaded', function() {
    const placeSlug = document.body.dataset.placeSlug;
    if (placeSlug && placeSlug !== 'none') {
        liveCountsUpdater.init(placeSlug);
    }
});

// Expose to global scope for initialization from templates
window.liveCountsUpdater = liveCountsUpdater; 