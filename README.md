# SMK WebUI

Local lighting controls for SMK keyboards. A small Windows background app serves a browser interface and sends effects directly to the keyboard. OpenRGB is not required.

Currently supports **CIY X77 UK ISO (88 keys)** running the custom **SMK X77 Fast v1** firmware. Other SMK keyboards and stock firmware are not supported yet.

- Static colours, breathing, colour cycle, horizontal and vertical waves.
- Reactive typing and ripples with separate foreground and background colours.
- Per-key colours, brightness, speed, direction, fade and ripple width.
- Named presets with import and export.
- Tray controls and automatic reconnection. Closing the browser keeps lighting running.
- Firmware identification and separate PC/onboard lighting controls.
- With firmware 2.0: five stored colour modes, key/shortcut assignments and four eight-step macros that run without the app.

## Keyboard settings

Open **Keyboard** to load the stored configuration automatically, then edit assignments, CM colours and macros. Changes remain in a draft; **Save to keyboard** writes the complete configuration and verifies readback. A backup of the previous configuration is saved in `data/keyboard-backups`. Macros use one chord and delay per line, such as `Ctrl+C, 100`. Each chord is held for about 40 ms, with a minimum 10 ms gap. Esc cancels playback.

On the keyboard, Fn+1–5 selects CM1–CM5. Hold the combination for about one second to edit, tap keys to cycle colours, then press the same Fn+number to save. Fn+F9 cycles animations; Fn+−/Fn+= decreases/increases speed. Fn is reserved so the controls remain accessible.

These keyboard features require firmware 2.0; PC lighting continues to work with the earlier Fast v1 firmware. Updating firmware can erase onboard settings unless the flashing procedure preserves the configuration sectors.

## Run

Extract the Windows package and open **SMK WebUI.exe**. Keep the runtime and app folders beside it. Close the previous SMK OpenRGB bridge first. The tray icon reopens the controls; Quit returns to onboard lighting. Settings and presets live in the portable `data` folder.

The UI is served only on `127.0.0.1:8765`. It uses no external fonts, cloud services or accounts. Reactive effects observe Windows key state from any keyboard; they retain only transient key indices and timestamps, not typed text.

## Troubleshooting

Open **Settings → Diagnostics & Logs** to inspect connection failures, effect changes and application errors, including the current process ID and frame submission rate. **Export logs** downloads the current session. Rotating log files are saved under `data/logs` (three files, up to 512 KB each). Logs do not contain keystrokes or RGB frames.

Only one app can bind the control port, and the lighting device is opened with exclusive write access. If it is already in use, close the other SMK instance or old lighting bridge. Reopening the launcher normally opens the existing controls.

## Development

Windows and Python 3.10 or newer; no third-party Python packages.

```powershell
$env:PYTHONPATH = "$PWD/src"
python -m smk_webui
python -m unittest discover -s tests
```

Use `--demo --no-tray --port 8766` for a preview without keyboard access. `--background` starts without opening a browser. Device transport and layout live under `devices`; the initial effect engine uses the X77 matrix geometry.

Build a portable package using CPython and MinGW GCC:

```powershell
python scripts/build.py
```

The launcher and tray use the S-key icon from `src/smk_webui/web/icon.svg`. After editing it, run `./scripts/build-icon.ps1` to regenerate the Windows icon before building.

The package includes Python, so users do not need to install or launch it separately. This application controls lighting and keyboard configuration; it does not flash firmware.

## License

GPL-2.0. Built for [SMK](https://github.com/karstx/smk). Bundled CPython retains its own license in `runtime/LICENSE.txt`.

The SMK logo is from the upstream SMK project.

### Keyboard editing

Direct means PC-controlled lighting; Static is the non-animated colour effect. With firmware 2.1, Fn+0 requests Direct mode from the running app and restores the last PC effect used in that app session. The keyboard continues its onboard lighting when the app is closed.

Automatic loading reads the editable base-key assignments and, on firmware 2.1, a read-only view of the built-in Fn layer. Built-in Fn actions are currently changed in firmware, not through the base-key remap editor. Arbitrary application paths are not stored or executed by the keyboard.

In Colour modes, choose a brush colour and click or drag over keys. Select inspects keys without painting; Fill all, Clear and Undo work on the draft. Save to keyboard writes and verifies it. Firmware 2.3 factory CM layouts are Glacier (cool white/cyan), Arena (gaming keys), Midnight (blue/violet), Sunset (warm gradient) and Aurora (green/cyan/violet rows). Existing saved profiles are preserved during an update; use Reset to apply the defaults.

Reset supports one assignment, one CM, all CMs, assignments, individual macros, all macros, onboard lighting, or the complete keyboard configuration. A complete reset requires typing RESET. Settings → Reset keyboard confirms the selected scope and writes it immediately; a complete reset also requires typing RESET. Local Clear and Restore default controls only change the draft. Configuration backups are kept under data/keyboard-backups. This does not delete PC presets, logs or app preferences, or restore stock firmware.

### Input and games

Remaps and finite macros run on the keyboard and emit normal USB HID reports. The app does not inject into other processes, access game memory, install an input driver, or generate synthetic Windows keystrokes. Reactive PC effects poll transient key state only while active; input events are not logged or sent over the network.

This architecture is not an anti-cheat certification or a guarantee against bans. Game rules can prohibit automated inputs even when a physical keyboard produces them. Use macros only where permitted. System-audio lighting uses Windows WASAPI loopback capture. Screen-colour lighting uses Windows desktop graphics capture without game hooks or process injection.

### Studio and appearance

Lighting is the live studio. Choose a lighting preset from its dropdown, or Create new, name it, adjust the lighting and Finish. Preset cards load with one click; their options menu contains Edit, Rename, Duplicate, Export and Delete. Cancelling preset creation leaves the live lighting running but does not save a preset. Lighting presets never change keyboard assignments, macros or CM storage.

Settings contains Dark, Light and System themes, diagnostics, configuration reload and scoped resets. Theme choice is stored in the browser. Banner animations respect reduced-motion preferences.

Firmware 2.2 supports 15 editable RGB swatches plus Off, shared across CM1–CM5. The colour picker first reuses an existing colour or an unused slot; if all slots are used, replacing one requires confirmation because every CM referencing it will change. Swatches can be folded away. Upgrades migrate existing CM colours, assignments and macros without resetting them. The Windows key glows red while locked, with a matching status badge in WebUI.

### Advanced Studio

Simple keeps the original lighting controls. Advanced offers up to eight ordered layers, with 19 effect types, Normal/Add/Screen/Multiply blending, opacity, colour, speed, scale, angle, duration and density. Masks target all keys, WASD, arrows, modifiers, the function row or a custom selection. Choose Keys opens a selection step in the preview: click keys to toggle them, then Apply Keys. Cancel leaves the existing key target unchanged. The top layer in the list is drawn last. Drag a layer by its dotted handle to reorder it; a line marks the drop position. With the handle focused, Arrow Up/Down also reorders. Scene controls affect the whole composition; the inspector groups the selected layer into Colours, Animation and Blending.

The built-in library contains 18 editable examples. Editing a built-in creates a new personal preset; originals remain available. Animated card previews use the keyboard renderer, with simulated presses for reactive effects. They pause offscreen and respect reduced motion.

Scene JSON is a versioned, declarative format: a `version: 1` object with a `layers` array. Export Scene produces a complete example. Scene JSON validates and applies a pasted scene. It does not execute Python, JavaScript or expressions. Layers, values and key masks are bounded. Lighting presets include the scene and master brightness/speed. Colour Boost lifts dim pixels while preserving their RGB ratios; black and full-scale peaks stay unchanged. It stays within the existing output limit and does not change electrical drive. Sunset Orbit starts at 40%; existing saved scenes retain their original appearance until adjusted. This is a layered editor, not a full timeline or node-graph editor.

### Install and startup

Extract the package and run **Install.cmd** for a per-user installation under `%LOCALAPPDATA%\Programs\SMK WebUI`. It creates a Start Menu shortcut and enables startup at Windows sign-in. No administrator privileges or driver installation are needed. Existing installed settings are preserved; a first installation also copies portable settings if present beside the installer.

Toggle **Auto Start** in Settings or the tray menu. Startup runs in the background without opening a browser. Alternatively, keep using the portable executable. Windows Installed Apps can uninstall the application; saved data is retained. The installer and uninstaller must be run by the user in their Windows session.

### Studio editing tools

Undo and Redo retain the last 50 lighting edits in the current browser session, including layer deletion, duplication, ordering, colours, key targets and scene settings. Ctrl+Z undoes; Ctrl+Shift+Z or Ctrl+Y redoes. Text fields retain their native undo behaviour. Loading a preset or reloading the page starts fresh history. These controls do not undo keyboard configuration writes or preset deletion.

Duplicate copies the selected layer, including its key mask, immediately above the original, within the eight-layer limit. Solo temporarily renders only the selected layer, including a layer that is switched off. Exit Solo restores the composition. Solo does not change saved visibility, exported scenes or presets. Editing, changing presets or leaving Lighting ends Solo; its five-second lease also expires when the browser closes or stops renewing the preview.

### Preset edits and draft recovery

The selected preset stays named while you adjust its lighting. Modified compares the active effect and its controls with the saved preset. Update Preset overwrites a personal preset; Save Copy creates a new one. Built-in presets can only be saved as copies. Revert Changes restores saved lighting and can itself be undone.

Live settings are saved independently of presets. The selected preset, new draft name and editing workflow are stored in `data/workspace.json` and restored after reopening the app or browser. A normal app exit flushes live settings; undo history remains browser-session only. Choosing another preset asks before replacing unfinished edits. These lighting drafts never change onboard CM storage, key assignments or macros.

In Choose Keys, press and drag across keys to add them; starting on a selected key removes keys along the stroke. Repeatedly crossing a key in one stroke does not toggle it again. Cancelled pointer gestures restore the selection from before the stroke. Apply Keys commits the target; Cancel leaves the layer unchanged.

### Audio lighting

Select Spectrum Neon or Velvet Pulse in Presets, or add Audio Spectrum / Audio Pulse in Advanced. Capture follows the default Windows multimedia playback device. Play music or other system audio, then adjust Sensitivity, Smoothing and Noise Gate. Rising levels have a fast attack; Smoothing mainly controls the falling tail. Square-root amplitude scaling preserves changes between quiet and loud passages. Auto Level adapts gain using a recent four-second decaying peak, after the noise gate, with an 8x gain limit. It is enabled by default so lower playback levels can fill the keyboard; switch it off for fixed input scaling. Sensitivity remains the final height/intensity adjustment. Primary and Secondary set the colours; key masks and blending work like other layers. The Scene header reports capture status or an unavailable-device error. Master Speed does not change incoming audio.

A small native helper uses [WASAPI shared-mode loopback](https://learn.microsoft.com/en-us/windows/win32/coreaudio/loopback-recording). A 2,048-sample Hann-window FFT produces 16 logarithmic bands from 60 Hz to 12 kHz (limited by the device sample rate). Only transient samples and spectrum levels are held in memory; audio is never written to disk, logged, or transmitted. No microphone, process injection, game hooks, or additional driver is used. Capture starts only for an active audio layer and stops when it is no longer needed. Device changes and failures trigger reconnection. The card previews use simulated audio.

The Windows build includes `audio_capture.dll`, compiled from `scripts/audio_capture.c` with MinGW. Source runs look for it in `build/`. Optional native DSP tests use the same source compiled with `-DSMK_AUDIO_TEST` to `build/audio_capture_test.dll`; they verify silence and frequency placement at several sample rates. Spectrum, smoothing, stale-data expiry and capture activation are covered by Python tests.

### Screen colours

Choose Screen Mirror or Screen + Sound, or add a Screen Colours layer in Advanced. Display selects the primary monitor or a specific attached display. Region offers full display, halves, or custom left/top/width/height percentages. Custom regions apply with Apply Region; the diagram indicates the selected area without displaying a screenshot. Refresh Displays updates the monitor list.

Keyboard Zones maps an 18x6 colour grid to the key positions. Average Colour applies the region's average colour to all targeted keys. Saturation, Screen Brightness, Smoothing, masks, opacity and blending remain adjustable. Screen + Sound combines capture with an audio pulse. Card previews use synthetic colours rather than capturing the display.

The background worker samples at up to 10 Hz using documented Windows GDI calls, reduces the selected area to 72x24 pixels and averages these into 18x6 zones. Capture is local and only runs while a screen layer is active (including Solo). No screenshots are written to disk, logged or served to the browser. Only the resulting keyboard colours are shown. Capture continues when the browser closes while that effect remains active; selecting another effect or quitting releases it. Missing monitors and capture errors are shown in the Scene status; stale samples are dropped.

This initial capture path supports ordinary desktop and borderless-window content. Protected video, exclusive fullscreen applications and HDR may produce unavailable, black or differently mapped colours. It does not bypass capture restrictions. See Microsoft's [GDI capture documentation](https://learn.microsoft.com/en-us/windows/win32/gdi/capturing-an-image).

## Preset Recovery

**Presets > Export Library** downloads all personal lighting presets. **Import** accepts one preset or a library. Existing presets are kept; duplicate names receive a numbered suffix. Keyboard assignments, macros and onboard colour modes are separate.

Before changing personal presets, the app stores a recovery library in `data/preset-backups` and retains the latest 20 copies. Import one of these JSON files to recover a deleted or overwritten preset. Import validates the complete file before saving any entries.

## Release Package

The build creates a versioned Windows x64 ZIP and `dist/SHA256SUMS`. Extract it to use the portable app, or run **Install.cmd** for a per-user installation. No separate Python installation is needed. An upgrade preserves the existing Start With Windows preference. Quit the app before replacing files manually.
