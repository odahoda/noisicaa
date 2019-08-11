Custom `waf` tools used for building noisicaä.

Running pylint on these files (these files are used to build, they are not built themselves, so
`./waf test` does not know about them):

```bash
PYTHONPATH=$(ls -d .waf*) bin/runpylint build_utils.waf
```
