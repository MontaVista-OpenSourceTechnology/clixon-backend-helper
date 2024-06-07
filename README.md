# clixon backend helper

A clixon backend that provides helpful functions for a backend.  These are:
* Per-namespace plugins.  A plugin may be bound to specific namespaces
  and is only called for XML items that have the top-level namespaces.
  That way the plugin doesn't have to parse everything, it just gets what
  it needs.
* External program helpers.  Since clixon drops privileges after it starts,
  if you need to perform certain operation at privilege you need an external
  program to do this.  This defines a program to run whose stdin/stdout
  is available to the plugin.
* python plugins.

## Compile and run

Build and install clixon first, or install it from your distro if
available.  Then run:
```
    meson build
    meson compile -C build
    meson install -C build
```

This will install the .so in ${prefix}/

## Examples

Each directory in the examples directory is a stand-alone build

