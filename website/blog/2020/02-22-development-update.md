Title: Development update (February 22)
Date: 2020-02-22

Oops, already the [next
commit](https://github.com/odahoda/noisicaa/commit/8fd99a2ef97b1dc89ac517d857db80f0dd8f2383), though
not a very big one (and I have to admit that I was already working on it when I wrote yesterday's
update).

### What's new

#### New toolbar

[[thumb:2020-02-22-toolbar.png]] The toolbar has been redesigned. Instead of using the normal
`QToolBar` widget, this is now using a custom layout. I rearranged the buttons, added buttons to
move the playhead back and forward by a single beat, added a widget to display the current time
(both in musical time and wall time), added a VU meter to display the master output level and move
the engine load graph from the status bar at the bottom of the window into the toolbar.

#### VU Meter node

[[thumb:2020-02-22-vumeter.png]] A simple node with just a VU meter display. I just needed the
processor, which is invisibly added to the engine in order so send the master output level to the
toolbar. Adding a UI to it and thus making it available to the user was simple enough.

#### Snap-to-grid when moving the playhead

Not much more to say about this.

### Bug fixes

* Some previous refactoring broke the status updates of the playback and loop buttons.
* The time alignment of measured tracks (Beat and Score tracks) got out of sync with the other
  tracks due to rounding errors.
