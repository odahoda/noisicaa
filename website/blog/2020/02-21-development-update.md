Title: Development update (February 21)
Date: 2020-02-21

Took a while, but I finally managed to kick myself back into a more productive mood. It was just a
matter of getting started, but as usual that's the hardest part.

So here's the [latest commit](https://github.com/odahoda/noisicaa/commit/eb2abe9cb0ed85cf0adae5baeeecb2147153f27b).

There were also some more commits to the master branch afterwards, but those were just maintenance
work, i.e. upgrading the package dependencies, incl. `mypy`/`pylint`, which triggered some code
cleanups. I just did not bother to create a new branch for that.

# What's new

## Sample track improvements

[[thumb:2020-02-21-sample-tracks.png]] I made various improvements to the sample tracks (which I
should really rename to "Audio Track") to make them at least somewhat usable - for my current
purposes, which is to just import an existing song and then try to decompose it into its parts and
rebuild those using noisicaä. I.e. I do not need anything fancy, just the ability to import an `MP3`
or `FLAC` file into a track and play it back. And do that without the UI blowing up.

Audio files are either read with [`libsndfile`](http://www.mega-nerd.com/libsndfile/) (like before)
or piped through [`ffmpeg`](https://www.ffmpeg.org/) for formats like `MP3` or `AAC`.

To get reasonably performant rendering, the audio data is split into chunks, which are rendered
asynchronously and then cached. Even though the main number crunching is done by
[`numpy`](https://numpy.org/), reading directly from a mmap'ed files, you still notice that this is
`Python` (i.e. it could benefit quite a lot from a `C++`/`Cython` version).

The audio data is rendered as [`rms`](https://en.wikipedia.org/wiki/Root_mean_square) and min/max
(should be the same way as [`Audacity`](https://www.audacityteam.org/) does it). And stereo files
are now correctly rendered as well.

There are still no advanced features, like editing, enveloped, disk streaming, etc.

# Internal changes

* Audio files are now decoded into raw files (32bit floats, single channel per file) into the
  project directory, which can be directly loaded into memory for playback.
* Some test coverage improvements.
