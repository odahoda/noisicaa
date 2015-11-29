import imp
import os
import os.path
import sys
from distutils.core import setup
from distutils.extension import Extension
from Cython.Build import cythonize

def path2mod(path):
    mod = []
    while path:
        path, tail = os.path.split(path)
        mod.insert(0, tail)
    return '.'.join(mod)


extensions = []
packages = []
for root, dirs, files in os.walk(
        os.path.join(os.path.dirname(__file__), 'noisicaa')):
    if os.path.exists(os.path.join(root, '__init__.py')):
        packages.append(path2mod(root))

    for path in files:
        path = os.path.join(root, path)
        if path.endswith('.pyx'):
            modname = path2mod(path[:-4])

            ext = None
            if os.path.exists(path + 'bld'):
                bldmod = imp.load_source(
                    "XXXX", path + 'bld', open(path + 'bld'))
                make_ext = getattr(bldmod, 'make_ext', None)
                if make_ext:
                    ext = make_ext(modname, path)
                    assert ext

            if ext is None:
                ext = Extension(modname, [path])
            extensions.append(ext)

    for ignored in ['.svn', '__pycache__', 'testdata']:
        if ignored in dirs:
            dirs.remove(ignored)

setup(
    name = 'noisicaä',
    version = '0.1',
    author = 'Ben Niemann',
    author_email = 'pink@odahoda.de',
    # license = 'TODO',
    classifiers = [
        'Development Status :: 2 - Pre-Alpha',
        'Environment :: X11 Applications :: Qt',
        'Intended Audience :: End Users/Desktop',
        # TODO: 'License :: OSI Approved :: ',
        'Natural Language :: English',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Cython',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: Implementation :: CPython',
        'Topic :: Artistic Software',
        'Topic :: Multimedia :: Sound/Audio :: Editors',
    ],
    packages = packages,
    ext_modules = cythonize(extensions),
)
