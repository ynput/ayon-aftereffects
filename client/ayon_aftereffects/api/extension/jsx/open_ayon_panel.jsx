// Deployed by AYON to auto-open the AYON panel on every launch.
//
// Reset the flag synchronously here — Scripts/Startup JSX runs during AE
// initialization, before the CEP framework loads and before main.js can
// set the flag.  This guarantees a clean slate every session.
app.preferences.savePrefAsBool("AYON", "panelOpen", false);

// Two-phase polling:
//
//   Phase 1: Wait for the AYON menu command to be registered (CEP loaded).
//
//   Phase 2: Poll for up to 5 seconds waiting for main.js to set
//            "panelOpen" to true (workspace restored the panel).
//            If the flag is set → do nothing (panel already open).
//            If the timeout expires → call executeCommand to open the panel.
var _ayon_phase = 1;
var _ayon_attempts = 0;
var _ayon_command_id = -1;

function _ayon_open_panel() {
    if (_ayon_command_id < 0) {
        _ayon_command_id = app.findMenuCommandId("AYON");
    }

    if (_ayon_phase === 1) {
        if (_ayon_command_id > 0) {
            _ayon_phase = 2;
            _ayon_attempts = 0;
            app.scheduleTask("_ayon_open_panel()", 1000, false);
        } else if (_ayon_attempts < 30) {
            _ayon_attempts++;
            app.scheduleTask("_ayon_open_panel()", 1000, false);
        }
        return;
    }

    var isOpen = false;
    try {
        isOpen = app.preferences.getPrefAsBool("AYON", "panelOpen");
    } catch (e) {
        // Preference absent on first launch — treat as false.
    }

    if (isOpen) {
        return;
    }

    if (_ayon_attempts < 5) {
        _ayon_attempts++;
        app.scheduleTask("_ayon_open_panel()", 1000, false);
    } else {
        app.executeCommand(_ayon_command_id);
    }
}

app.scheduleTask("_ayon_open_panel()", 1000, false);
