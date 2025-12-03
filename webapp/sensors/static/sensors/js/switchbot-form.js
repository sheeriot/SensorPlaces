document.addEventListener('DOMContentLoaded', function() {
    const switchbotEnableSwitch = document.getElementById('id_switchbot_enable');
    const switchbotCredsCollapse = new bootstrap.Collapse(document.getElementById('switchbot-creds-collapse'), {
        toggle: false
    });

    if (switchbotEnableSwitch) {
        switchbotEnableSwitch.addEventListener('change', function() {
            if (this.checked) {
                switchbotCredsCollapse.show();
            } else {
                switchbotCredsCollapse.hide();
            }
        });
    }
});
