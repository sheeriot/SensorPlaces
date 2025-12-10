/**
 * Htmx Response Target Extension
 *
 * This extension allows you to specify a target for error responses, using
 * the `hx-target-error` attribute. If a request returns a status code in the
 * error range (4xx or 5xx), the content of the response will be swapped into
 * the element specified by `hx-target-error`.
 *
 * This is useful for displaying error messages in a designated area of the
 * page, rather than replacing the content of the primary target.
 *
 * Usage:
 *
 * <button hx-post="/example"
 *         hx-target="#success-target"
 *         hx-target-error="#error-target">
 *   Submit
 * </button>
 *
 * <div id="success-target"></div>
 * <div id="error-target"></div>
 */
htmx.defineExtension('response-targets', {
    onEvent: function(name, evt) {
        if (name === 'htmx:beforeSwap' && evt.detail.xhr.status >= 400) {
            // If the response status is an error, check for an error target
            const errorTarget = evt.detail.requestConfig.elt.getAttribute('hx-target-error');
            if (errorTarget) {
                // If an error target is specified, redirect the swap to that target
                evt.detail.target = htmx.find(errorTarget);
            }
        }
    }
});
