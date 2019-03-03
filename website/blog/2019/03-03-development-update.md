Title: Development update (March 3)
Date: 2019-03-03

Just [merged the
branch](https://github.com/odahoda/noisicaa/commit/da16c0626ab6a5b327a4927528c95718d3c1b3bb) for the
"Proto IPC" sprint. This was again mostly an internal cleanup with no significant user visible
changes.

### Internal changes

The internal communication between processes now uses (almost exclusively) protocol buffers instead
of pickled Python objects. The IPC code has also been optimized a bit to make it a faster.

### WTF am I doing here?

So I started out with the ambition to make music. Instead of, you know, pick up some existing
software and just go ahead, I decided to write my own. As if that would be more efficient in any way
(but it's fun and enjoyable for me).

And now, instead of, you know, adding musical features to it, I spend my time working on completely
unrelated infrastructure stuff, for which there is probably some existing library that does a better
job than me (but it's fun and enjoyable for me).

I guess you can call that "productive procrastination", though [existing
usages](https://medium.com/@protoio/why-productive-procrastination-can-be-beneficial-6540e95459f9)
of that term seem to be see it in a more favorable view that I would do. So I would like to get more
focused on what I really want and at least work more on the musical features of noisicaä. The
ambition to eventually make music with it shouldn't totally disappear. But I won't be able to
completely suppress my urge to give the code base some polish from time to time...
