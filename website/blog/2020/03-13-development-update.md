Title: Development update (March 13)
Date: 2020-03-13

[Today's
commit](https://github.com/odahoda/noisicaa/commit/3fb19792d4fdc2b09f3011b4d96e7bb7f2855880) is just
an assorted set of bug fixes and minor improvements.

### What's new

#### Append Measures

[[thumb:2020-03-13-append-measures.png]] A new dialog to append measures to measured tracks (i.e. Score and Beat Tracks). Either a given number or filling the track till the end of the project.

#### Improved Audio Settings

[[thumb:2020-03-13-audio-settings.png]] Now the engine state and load is displayed in the audio settings dialog.

#### Random Changes

- Renaming a node is triggered from the context menu. It was previously supposed to work by double clicking on the node name itself, but that was very flaky and often did not work.
- After a crash, noisicaä starts up with the open project dialog instead of reopening the previously opened project(s). This is to avoid annoying crash loops.
- noisicaä now runs `./waf build` when the app is reloaded with `F5`. Of course this only works, if you built and run it from the sources. This is primarily to reduce the turnaround times when making changes to the code, i.e. it's only useful for developers.
- The "AudioProc Dump" contains more information. Again only useful for developers.

### Bug fixes

- Playing the test sample from the settings dialog triggered an exception and did not properly cleanup some state in the audio engine.
- Some crashes while restarting the engine (e.g. when changing engine settings).
- Changing the BPM now triggers rerendering of samples in Sample Tracks.
- Changing the BPM could trigger a crash in the Sample Track processor.
- Fix the size of control dial widgets in mixer node UI.
- Remove crackling when changing mixer control values.
- Engine state wasn't updated when undoing a node or connection removal.
- The device list in the MIDI Source node could get corrupted when plugging in or unplugging a device.
- Gracefully handle more crashes while opening/creating projects.
- The name labels for hidden tracks could sometimes become visible.
- Renaming a track did not resize the track's name label widget, e.g. truncating the displayed name.
- Unittest results might not get written to disk, creating the illusion that everything was fine, when it actually wasn't.

### Internal changes

- Use separate messages for engine load and state.
- The `EngineState` tracker is owned by the `EditorApp` (which already owns the engine client) instead of `EditorWindow`.
