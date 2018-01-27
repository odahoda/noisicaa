<!--
  -*- fill-column: 98 -*-
-->

# vmtests

## Description

The vmtests are a suite of tests which verify that noisicaä is compatible with the officially
supported set of distributions.

The tests run under [virtualbox](https://www.virtualbox.org/), install a minimal version of each
distribution, build noisicaä from source and then run the test suite.

## Prerequisites

Before you can run test vmtests, you might have to install some additional packages:

```bash
pip install $(./listdeps --pip --vmtests)
sudo apt install $(./listdeps --system --vmtests)
```

The VMs are stored in a `vmtests` directory. That directory will contain some large files, so if you
don't want those to be place in your home directory (e.g. because it's hosted on a NFS server, you
don't want to waste precious space on your SSD, etc.), you can create it as a symlink to some
suitable place.

```bash
mkdir /path/to/vmtests
ln -s /path/to/vmtests vmtests
```

## Running the tests

```bash
python -m noisidev.runvmtests
```

* Each distribution runs in a separate VM.

* Distributions are named `$DIST-$RELEASE`, e.g. `ubuntu-16.04`.

* When no argument is given, tests for all supported distributions are run. You can restrict the
  tests by listing the desired distributions as arguments:
```bash
python -m noisidev.runvmtests ubuntu-16.04
```

* Once a the distribution has been installed in a VM, a snapshot called 'clean' is created. On
  subsequent runs that snapshot gets restored, so the tests always run from the same state. If you
  just want to retry a test without reverting to the clean state, use `--clean-snapshot=false`.

* If you want to reinstall the VMs from scratch, use `--rebuild-vm=true`.

## Debugging test failures

If inspecting the output is not sufficient to pin down the problem, you can restart the VM in the
state as it was after the test finished:

```bash
python -m noisidev.runvmtests --just-start $DISTNAME
```

Login as user `testuser` with passwork `123`, change into the `noiscaa` directory and active the
virtuenenv:

``` bash
cd noisicaa/
. ENV/bin/activate
```
