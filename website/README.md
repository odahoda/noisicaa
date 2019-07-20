This is the source code for the http://noisicaa.odahoda.de/ website.

Note that it's using a static site generator called `odasite`, which is currently not publically
available, so the following instructions only work for myself.

# Install odasite

```bash
venv/bin/pip install -e ~/projects/odasite
```

# Editing

```bash
cd website/
../venv/bin/python -m odasite serve
```

View website at http://localhost:8000/

# Upload

```bash
../venv/bin/python -m odasite remote-diff  # Review changes
../venv/bin/python -m odasite upload
```
