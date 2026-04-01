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

function _ayon_open_panel() {
    var id = app.findMenuCommandId("AYON");

    if (_ayon_phase === 1) {
        if (id > 0) {
            _ayon_phase = 2;
            _ayon_attempts = 0;
            app.scheduleTask("_ayon_open_panel()", 1000, false);
        } else if (_ayon_attempts < 30) {
            _ayon_attempts++;
            app.scheduleTask("_ayon_open_panel()", 1000, false);
        }
        return;
    }

    // Phase 2: wait for main.js to signal that the panel loaded.
    var isOpen = false;
    try {
        isOpen = app.preferences.getPrefAsBool("AYON", "panelOpen");
    } catch (e) {}

    if (isOpen) {
        // Workspace restored the panel — nothing to do.
        return;
    }

    if (_ayon_attempts < 5) {
        _ayon_attempts++;
        app.scheduleTask("_ayon_open_panel()", 1000, false);
    } else {
        // Panel was not restored after 5 seconds — open it.
        app.executeCommand(id);
    }
}

app.scheduleTask("_ayon_open_panel()", 1000, false);
