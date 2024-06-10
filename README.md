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

Build and install clixon first, or install it from your distro if
available.  Then run:
```
    meson build
    meson compile -C build
    meson install -C build
```

This will install the .so in ${prefix}/libexec/clixon_beh.so.  It will
install a python `_clixon_beh.so` and `clixon_beh.py` file into the proper
place for python to pick it up.  And it will install `clixon_beh.h` in
the include directory.  It will install a `clixon-beh-config` yang file
into clixon's yang directory.  And that should be all you need.

## Examples

Each directory in the examples directory is a stand-alone build

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

The python interface is a semi-thin veneer over the C interface.  It
has the same basic functions as the C interface, but it's wrapped into
a more python-like OO interface.

To use this, you create a handler class and register it
```
class ClixonHelloOp:
    def __init__(self):
	    # setup data.

class ClixonHelloHandler:
    def __init__(self):
        self.namespace = "urn:example:pyhello_beh"

    def begin(self, t):
        t.set_userdata(ClixonHelloOp())
        return 0

    def validate(self, t):
	    data = t.get_userdata()
        return 0

    def commit(self, t):
	    data = t.get_userdata()
        origxml = t.orig_str()
        newxml = t.new_str()
        return 0

    def statedata(self, nsc, xpath):
        return (0, "<xml data>")

handler = ClixonHelloHandler()
handler.p = clixon_beh.add_plugin_strxml("pyhello",
                                         handler.namespace, handler)
```
Make sure the return value from `add_plugin_strxml()` doesn't get
deleted, you need to store it someplace.

The transaction data is passed to you in an object.  It has userdata,
which you can get and set as a python object, and you can get the
original and new XML strings.  Note that these may return None if they
don't exist.  The following methods exist on transactions:
```
   t.set_userdata(obj)
   obj = t.get_userdata()
   origxmlstr = t.orig_str()
   newxmlstr = t.new_str()
   origxml = t.orig_xml()
   newxml = t.new_xml()
```

You can use something like lxml to parse the strings.  All clixon XML
flags are passed in the `clixonflags` attribute, separated by commas,
with the strings as lower case ending of the `#define` for them.  For
the elements that have changed, it will be one or more of "add",
"del", and "change" flags.

The transaction also has an xmlobj object, which is basically the same
as the cxobj object in main clixon.  You can fetch those and process
them using the object's methods, which are:
```
char *get_name()
char *get_prefix()
xmlobj *get_parent()
char *get_flags()
char *get_value()
char *get_type_str()
int get_type()
int nr_children()
int nr_children_type(int type)
xmlobj *child_i(int i)
xmlobj *child_i_type(int i, int type)
xmlobj *find(char *name)
xmlobj *find_type(char *prefix, char *name, int type)
char *find_type_value(char *prefix, char *name, int type)
char *get_body()
char *get_attr(char *prefix, char *name)
```
These are a pretty close match to the `clixon_xml` functions.  The
`xmlobj` object is, unfortunately, immutable.  The way it works
internally in clixon means that if you changed something, you could
delete or change something that a python object is pointing to, which
could result in crashes.  In `C` it's expected that you know what you
are doing, but that doesn't map very well into Python.  The only real
limitation here is with statedata; it would be nice if that could
return an `xmlobj`.

Now when a top-level namespace changed and matches what you have
registered, the methods in the registered handler will be called.  If
you pass in NULL for the namespace, you will get the entire namespace
every time, all changed and unchanged items.

One thing to note is that the begin function returns a tuple with an
error as the first item and an object as the second item.  The object
will be passed into the rest of the transaction-based functions as the
data item, and it will be automatically deleted when the transaction
completes.  That lets you keep data around for a transaction.

The statedata method also returns a tuple, the first items is an
integer error, the second is a string holding xml for the state data.
If you return an error, the xml value may be empty.
