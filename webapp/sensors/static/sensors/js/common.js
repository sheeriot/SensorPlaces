/**
 * Common JavaScript functionality for the sensors application
 * 
 * Configuration:
 * -------------
 * To enable debugging, set debug: true in commonConfig below
 */

// System Configuration
const commonConfig = {
    debug: false  // Set to true to enable debug mode
};

// Global state
if (typeof window.currentPlaceSlug === 'undefined') {
    window.currentPlaceSlug = null;
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    if (commonConfig.debug) {
        console.group('=== Common System Startup ===');
        console.log('Current place slug:', window.currentPlaceSlug);
        console.groupEnd();
    }
});