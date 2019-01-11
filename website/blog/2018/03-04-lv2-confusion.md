Title: LV2 confusion with internal presets
Date: 2018-03-04

I managed to get the [Helm](http://tytel.org/helm/) synth working as an LV2 in noisicaä, including
UI. Which is great, because that's a very nice synth.

But I ran into an issue, which caused me some head scratching, because I thought that I was doing
something wrong. As it turned out, this is really a problem with (at least) LV2 and Helm's feature
to load presets from within its own UI.

Helm's internal state is determined by the values of the 100+ control input ports, plus some
additional state that isn't captured by those ports (e.g. which controls are modulated by an LFO).

Now when you load a preset, Helm sets all of its control to specific values, but it has no way to
tell the host about those values. Which means the host is still feeding the previous values into all
control input ports. Helm seems to have some logic to ignore those values from the host, until you
actually change them from outside of Helm (e.g. via automation or the generic UI). If you change
some control manually in Helm's UI, then the values are posted from the UI to the host, so it can
update the value that it feeds into the respective control port.

But if you now close the project and open it again, Helm's state gets all messed up, because for
most control the host never learned about the right value from the preset that you selected, and
Helm gets initialized with effectively random values. Things get even more confusing, because the
control values are also stored in Helm's '[internal
state](http://lv2plug.in/ns/ext/state/state.html)' blob and depending on the order in which control
ports and internal state are initialized you get different results.

Turns out that [Ardour](https://ardour.org/) has the same issue, so I'm not alone with it.  I don't
know, if e.g. the VST API solves this issue, or if it was generally a bad idea to have presets,
which change the values of control ports - and manage them within the plugin itself. If the presets
would be handled in the UI, then LV2 has the API to set the control ports... or is it just a bug in
Helm, that this API isn't used when switching presets?

So the lesson is to not touch the preset browser in Helm, but instead use the preset menu from the
host - which has the same list of presets, and knows how to set the control port correctly when
loading a preset.

But noisicaä doesn't know about presets yet...
