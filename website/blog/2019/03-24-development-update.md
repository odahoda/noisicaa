Title: Development update (March 24)
Date: 2019-03-24

I got a little bit distracted by reading too much about Emacs and tweaking my config for it, so
noisicaä had a little downtime of about three weeks. But to get things rolling about, I had a little
"Expose Ports" sprint, which I just
[merged](https://github.com/odahoda/noisicaa/commit/6d52afb424e277c9884228d99fb88d98ddce5237) into
master.

### What's new

Control ports, which previously could only be set interactively to a fixed value, can now be
"exposed" as normal ports, so you can connect them to other nodes. Basically what other DAWs call
"automation"...

The UI is still suboptimal - it's just a nameless checkbox next to the dial. This also only works
 for the generic node UI so far. Other built-in nodes with a custom UI should also get that feature,
 but I'll have to think about the UI design. Perhaps make this available via a popup menu on all
 controls?

Also a-rate control ports, can now be used like k-rate control ports, i.e. either set the value via
a UI dial or expose and connect them to other nodes.

### Bug fixes

* Fixed a crash when removing node with connections.
* Fixed a crash when removing some LV2 plugin nodes, where there is some issue with the [State
  extension](http://lv2plug.in/ns/ext/state/). The issue still exists (a traceback is dumped to the
  log and state collection stops), but doesn't cause a crash anymore.

### Internal changes

* Dump audio engine opcodes to the log (via the "Dev" menu).
