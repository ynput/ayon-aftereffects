// Deployed by AYON to auto-open the AYON panel on every launch.
//
// Uses an AE preference ("AYON" / "panelOpen") as a handshake with
// the CEP panel JS (main.js):
//   - main.js sets the flag to true when the panel loads.
//   - This script reads the flag, resets it to false, then opens the
//     panel only when the flag was false (panel not restored by the
//     workspace).  On the next launch the workspace will restore the
//     panel and main.js will set the flag again.
var _ayon_attempts = 0;

function _ayon_open_panel() {
    var id = app.findMenuCommandId("AYON");
    if (id > 0) {
        var wasOpen = false;
        try {
            wasOpen = app.preferences.getPrefAsBool("AYON", "panelOpen");
        } catch (e) {
            // Preference not set yet — first run.
        }
        // Reset so the next launch opens the panel if the workspace
        // does not restore it (e.g. after a crash or workspace reset).
        app.preferences.savePrefAsBool("AYON", "panelOpen", false);
        if (!wasOpen) {
            app.executeCommand(id);
        }
    } else if (_ayon_attempts < 10) {
        _ayon_attempts++;
        app.scheduleTask("_ayon_open_panel()", 1000, false);
    }
}

app.scheduleTask("_ayon_open_panel()", 1000, false);
