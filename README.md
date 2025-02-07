# clixon backend helper

A clixon backend that provides helpful functions for a backend.  These are:
* Per-namespace plugins.  A plugin may be bound to specific namespaces
  and is only called for XML items that have the top-level namespaces.
  That way the plugin doesn't have to parse everything, it just gets what
  it needs.
* External program helpers.  Since clixon drops privileges after it starts,
  if you need to perform certain operation at privilege you need an external
  program to do this.  (Not yet implmented.)
* python plugins.

## Compile and run

NOTE: This requires a version of clixon after 7.3.0.  As of writing,
that is the latest version, so you will need to pull the end of the
clixon git tree at the moment.

Build and install clixon first, or install it from your distro if
available.  Then run:
```
    meson setup build
    meson compile -C build
    meson install -C build
```

This will install the .so in ${prefix}/libexec/clixon_beh.so.  It will
install a python `_clixon_beh.so` and `clixon_beh.py` file into the proper
place for python to pick it up.  And it will install `clixon_beh.h` in
the include directory.  It will install a `clixon-beh-config` yang file
into clixon's yang directory.  And that should be all you need.

Note that if you are installing clixon in `/usr/local`, it will
install the python files there, too.  Unfortunately, python doesn't
work consistently there, it will generally install in
`/usr/local/lib/python3/...`, but python will look in the specific
directory for the python version, like `/usr/local/lib/python3.12/...`
so you will need to override the python installation directories.
First you need to find them, run:
```
python -m sysconfig | less
```
and look for `platlib` and `purelib`.  Then for setup, run:
```
meson setup build -Dpython.platlibdir=... -Dpython.purelibdir=...
```
making the obvious substitutions for `...`.  Then you can compile and
install.

Note that if you install in `/usr` python will look in
`/usr/lib/python3` so everything works fine in that case.

## Examples

Each directory in the examples directory is a stand-alone build

## Interfaces

Each of this is an implementation of a full YANG specification.

## The C Interface

The C interface for clixon_beh is similar to the one for the clixon
proper.  The major differences are:
* The module init function is `clixon_beh_plugin_init()`.
* You must call `clixon_beh_add_plugin()` to register a plugin.  You don't
  return a pointer from the module init function.  You can register
  multiple plugins from the same module.
* You can pass a namespace to `clixon_beh_add_plugin()`.  You will only
  get called when those namespaces change at the top level, and only
  with the xml subtrees with thost namespaces (again, top-level).
  If you pass in `NULL` for the namespace, you get everything, just like
  the main clixon API.
* You get a plugin object when you add it.  This will be passed in to
  all your functions.  You can store a void * in it to keep data around.
* A transaction is passed around, and you can store a data item in it
  with `clixon_beh_trans_set_data()` and retrieve it with
  `clixon_beh_trans_get_data()`.  Make sure to free it in the end and
  abort functions!
* Currently the transaction only has the old and new trees, not the
  added, deleted, and changed trees.

### External Program Interface

Not yet implemented.

## The Python Interface

See the README.md in the `clixon_beh` directory for information about
the Python interface.  For a starter overview, see VADE\_MECUM.md in
the `clixon_beh` directory.
