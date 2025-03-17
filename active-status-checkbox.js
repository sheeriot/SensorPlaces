function handleLocationStatusChange(event) {
    const { isLocationActive, checkboxState, checkboxDisabled, inactiveReason } = event.detail;
    
    console.log("[Active Status] Location status changed:", {
        isLocationActive: isLocationActive,
        checkboxState: checkboxState,
        disabled: checkboxDisabled,
        hasInactiveReason: !!inactiveReason
    });

    // Find the help text container within the same form-check div
    const container = event.target;
    const helpTextContainer = container.querySelector('[data-help-text-container]');
    
    // Only show help text if we have an inactiveReason (location forcing inactive)
    if (helpTextContainer) {
        if (inactiveReason) {
            helpTextContainer.innerHTML = inactiveReason;
            helpTextContainer.classList.remove('d-none');
        } else {
            helpTextContainer.classList.add('d-none');
        }
    }

    return {
        state: isLocationActive ? 'Active' : 'Inactive',
        disabled: checkboxDisabled
    };
}

function updateCheckboxUI(formId, checkboxId, state, disabled) {
    const checkbox = document.getElementById(checkboxId);
    if (checkbox) {
        checkbox.checked = (state === 'Active');
        checkbox.disabled = disabled;
        
        // Find help text container
        const container = checkbox.closest('.form-check');
        const helpTextContainer = container?.querySelector('[data-help-text-container]');
        
        // Hide help text on manual checkbox changes
        if (helpTextContainer && !disabled) {
            helpTextContainer.classList.add('d-none');
        }
        
        console.log("[Active Status] UI updated:", {
            State: state,
            Disabled: disabled ? 'Yes' : 'No',
            Label: state.toLowerCase(),
            HelpTextVisible: !helpTextContainer?.classList.contains('d-none')
        });
    }
} 