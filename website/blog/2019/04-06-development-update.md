Title: Development update (April 6)
Date: 2019-04-06

This [commit](https://github.com/odahoda/noisicaa/commit/c3e5c3a88dcf7cfac5f13cd67601be0b8c2fe3a5)
adds the capability to have nodes with dynamic ports, i.e. the list and types of ports are not
static anymore, but can change during the lifetime of the node. For now this is only used by one
builtin node type, but I plan to make more use of that feature in the future. E.g. to have a single
"VCA" node with a flexible number of channels, instead of needing a number of separate "VCA (mono)",
"VCA (stereo)" nodes.

### What's new

The Custom CSound node now has a dynamic port list. Ports can be added, removed and modified.

### Internal changes

* The NodeDescription of a node can be generated dynamically. Changes are propagated to the audio
  engine and for some changes, e.g. port type or direction changes, the underlying processor
  instance gets reinitialized (which does cause a brief audio glitch, if the processor is hooked up
  and producing sound).

* Added node parameters, which are persistent in the audio engine graph, but not part of the
  project. Used for setting the CSound orchestra and score of the Custom CSound node. Processors
  already had the concept of parameters, which has been assimilated into the more generic node
  parameters.

* A new ObjectListEditor class, which provides a table widget for editing lists of
  objects. Currently only used for the port list editor of the Custom CSound node.
