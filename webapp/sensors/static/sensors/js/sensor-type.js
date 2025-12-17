/**
 * Sensor Type form JavaScript - handles aliases tag-based input
 */
(function() {
    const config = {
        debug: false
    };

    function log(...args) {
        if (config.debug) console.log('[SensorType]', ...args);
    }

    /**
     * Renders the current aliases as Bootstrap badges
     */
    function renderAliases(aliases, container, hiddenInput) {
        container.innerHTML = '';
        aliases.forEach((alias, index) => {
            const badge = document.createElement('span');
            badge.className = 'badge bg-secondary d-flex align-items-center gap-1';
            badge.innerHTML = `
                ${alias}
                <button type="button" class="btn-close btn-close-white btn-sm"
                        aria-label="Remove" data-index="${index}"></button>
            `;
            container.appendChild(badge);
        });
        hiddenInput.value = JSON.stringify(aliases);
        log('Rendered aliases:', aliases);
    }

    /**
     * Adds an alias to the list
     */
    function addAlias(aliasInput, aliases, container, hiddenInput) {
        const value = aliasInput.value.trim();
        if (!value) return;

        // Prevent duplicates
        if (aliases.includes(value)) {
            log('Alias already exists:', value);
            aliasInput.value = '';
            return;
        }

        aliases.push(value);
        aliasInput.value = '';
        renderAliases(aliases, container, hiddenInput);
        log('Added alias:', value);
    }

    /**
     * Removes an alias from the list by index
     */
    function removeAlias(index, aliases, container, hiddenInput) {
        const removed = aliases.splice(index, 1);
        renderAliases(aliases, container, hiddenInput);
        log('Removed alias:', removed);
    }

    /**
     * Initializes the aliases tag input UI
     */
    function initializeAliasesInput() {
        const aliasInput = document.getElementById('alias-input');
        const addButton = document.getElementById('add-alias-btn');
        const container = document.getElementById('aliases-container');
        const hiddenInput = document.getElementById('id_aliases');

        if (!aliasInput || !addButton || !container || !hiddenInput) {
            log('Aliases input elements not found, skipping initialization');
            return;
        }

        // Parse existing aliases from hidden input
        let aliases = [];
        try {
            aliases = JSON.parse(hiddenInput.value || '[]');
            if (!Array.isArray(aliases)) aliases = [];
        } catch (e) {
            log('Error parsing aliases JSON:', e);
            aliases = [];
        }

        // Render existing aliases
        renderAliases(aliases, container, hiddenInput);

        // Add button click handler
        addButton.addEventListener('click', function() {
            addAlias(aliasInput, aliases, container, hiddenInput);
        });

        // Enter key handler for input
        aliasInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                addAlias(aliasInput, aliases, container, hiddenInput);
            }
        });

        // Remove button click handler (delegated)
        container.addEventListener('click', function(e) {
            const closeButton = e.target.closest('.btn-close');
            if (closeButton) {
                const index = parseInt(closeButton.dataset.index, 10);
                removeAlias(index, aliases, container, hiddenInput);
            }
        });

        log('Aliases input initialized with', aliases.length, 'aliases');
    }

    // Initialize on DOMContentLoaded
    document.addEventListener('DOMContentLoaded', function() {
        initializeAliasesInput();
    });

    // Re-initialize after HTMX swaps
    document.body.addEventListener('htmx:afterSwap', function(evt) {
        if (evt.detail.target.querySelector('#alias-input')) {
            initializeAliasesInput();
        }
    });
})();
