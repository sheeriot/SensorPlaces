function handleLocationStatusChange(isLocationActive, currentCheckboxState) {
    console.log("[Active Status] Location status changed:", {
        isLocationActive: isLocationActive,
        checkboxState: currentCheckboxState
    });

    if (isLocationActive) {
        return {
            state: 'Active',
            disabled: false
        };
    } else {
        return {
            state: 'Inactive',
            disabled: true
        };
    }
}

function updateCheckboxUI(formId, checkboxId, state, disabled) {
    const checkbox = document.getElementById(checkboxId);
    if (checkbox) {
        checkbox.checked = (state === 'Active');
        checkbox.disabled = disabled;
        
        console.log("[Active Status] UI updated:", {
            State: state,
            Disabled: disabled ? 'Yes' : 'No',
            Label: state.toLowerCase(),
            Help Text: 'Visible'
        });
    }
} 