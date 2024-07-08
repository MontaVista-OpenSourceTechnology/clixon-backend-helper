# Python and clixon

This directory contains a basic Python 3 interface to clixon and a
transaction framework module that simplifies the handling of
transactions coming from clixon.

## A Python interface to clixon

The python interface is a semi-thin veneer over the C interface of
clixon_beh.  It has the same basic functions as the C interface, but
it's wrapped into a more python-like OO interface.

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
deleted, you need to store it someplace to keep it from getting garbage
collected.

### The Main Interface

Now when a top-level element with your registered namespace changes,
the methods in the registered handler will be called.  If you pass in
NULL for the namespace, you will get the entire XML tree every time,
all changed and unchanged items.

All the same callbacks for the clixon `C` interface are available here:

```
class Handler(tf.Elem:
    def pre_daemon(self):
        return 0

    def daemon(self):
        return 0

    def reset(self, cb):
        return 0

    def lockdb(self, db, lock, id):
        return 0

    def exit(self):
        return 0

    def begin(self, t):
        return 0

    def validate(self, t):
        return 0

	def complete(self, t):
		return 0

    def commit(self, t):
        return 0

    def commit_done(self, t):
		return 0

    def revert(self, t):
		return 0

    def end(self, t):
		return 0

    def abort(self, t):
		return 0

	def statedata(self, nsc, xpath):
        return (0, "<xml data>")
```

The statedata method returns a tuple, the first items is an integer
error, the second is a string holding xml for the state data.  If you
return an error, the xml value may be empty.  The rest return -1 on
error an 0 on success.  If they return an error, they should call
`clixon_err` first to report what went wrong.

### Transaction Objects

The transaction data is passed to you in an object (all named `t` in
the previous section).  It has userdata, which you can get and set as
a python object, and you can get the original and new XML as either a
string or an XML object.  Note that these may return None if they
don't exist; if you are processing an add, the orig part will be None.
The following methods exist on transactions:

```
   t.set_userdata(obj)
   obj = t.get_userdata()
   origxmlstr = t.orig_str()
   newxmlstr = t.new_str()
   origxml = t.orig_xml()
   newxml = t.new_xml()
```

You can use something like `lxml` to parse the strings.  In that case
all clixon XML flags are passed in the `clixonflags` attribute,
separated by commas, with the strings as lower case ending of the
`#define` for them.  For the elements that have changed, it will be
one or more of "add", "del", and "change" flags.

The transaction also has an xmlobj object, returned by `orig_xml` and
`new_xml`, which is basically the same as the cxobj object in main
clixon.  You can fetch those and process them using the object's
methods, which are:

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
char *to_str() // Convert to an xml string
```

These are a pretty close match to the `clixon_xml` functions.  The
`xmlobj` object is, unfortunately, immutable.  The way it works
internally in clixon means that if you changed something, you could
delete or change something that a python object is pointing to, which
could result in crashes.  In `C` it's expected that you know what you
are doing, but that doesn't map very well into Python.  The only real
limitation here is with statedata; it would be nice if that could
return an `xmlobj`.

### RPCs, Actions, and Notifications
The python interface contains functions to register for RPC and action
callbacks, and functions to register and send notifications.

#### RPCs
To register an RPC, call the following:
```
clixon_beh.add_rpc_callback(name, namespace, cbobj)
```
where `name` is the RPC name, `namespace` is the namespace it's in, and
`cbobj` is an object that has the following method:
```
def rpc(self, x, username):
```
When the RPC is called on the external interface, this rpc function will
be called. The `x` value is an `xmlobj` of the input parameters.  This
function should return a tuple with the first value an error value and
the second value the return XML string (or `None` if an error).

#### Actions
Actions are much like RPCs, except they are registered against a path
in the YANG structures.  The register function is:
```
clixon_beh.add_action_callback(yang_path, cbobj)
```
where `yang_path` is the path in the yang structures where the action
is.  If you are using the example-server-farm from RFC7950, for instance,
the reset action would be registered with the path
`/sfarm:server/sfarm:reset`.  The `sfarm` part is the prefix from the
module and the `server` and `reset` parts are the path to the action.

#### Notifications
To use a notification, you must first register it with:
```
clixon_beh.add_stream(name, description)
```
where `name` must match the name in notify and `description` should be
some sort of descriptive string.  To publish a notification to the stream,
do:
```
clixon_beh.stream_notify(name, xmlstr)
```
where `xmlstr` must be the full XML of the notification.  For instance,
if you had something like:
```
notification event {
    leave event-type {
	    type string;
	}
}
```
then your `xmlstr` would be something like:
```
<event xmlns=...>
  <event-type>error</event-type>
</event>
```

### Other Stuff

In addition to the main interface, this has some interfaces to some
basic things not related to other clixon things:

```
int geteuid();
int restore_priv();
int drop_priv_temp(int euid);
void clixon_err(int oe, int ev, char *str);
void clixon_log(int logtype, char *str);
```

`geteuid`, `restore_priv`, and `drop_priv_temp` are thin wrappers over
the C functions of the same name, and do the same thing.  `clixon_err`
and `clixon_log` are also thin wrappers over those function.
Generally you would use `plugin.log` instead of `clixon_log`, but it's
there if you need it.

All the log levels are available in the `clixon_beh` module as:

```
LOG_TYPE_LOG
LOG_TYPE_ERR
LOG_TYPE_DEBUG
```

The clixon error types are available as:
```
OE_DB
OE_DAEMON
OE_EVENTS
OE_CFG
OE_NETCONF
OE_PROTO
OE_REGEX
OE_UNIX
OE_SYSLOG
OE_ROUTING
OE_XML
OE_JSON
OE_RESTCONF
OE_PLUGIN
OE_YANG 
OE_FATAL
OE_UNDEF
OE_SSL
OE_SNMP 
OE_NGHTTP2
```

All the same as the `C` interface.

## The Transaction Framework

The transaction framework sits on top of the base python interface to
simplify writing your own backends for clixon.  It handles a lot of
the boilerplate and parsing of the XML.  It uses the XML objects from
a transaction, not the string interface.

The first class you deal with is TopElemHandler.  This is a handler
for the top element of an XML tree from clixon, what you get from
registering with `clixon_beh.add_plugin()`.  You can descend from this
class and override things you might need, like begin, daemon, etc.  Or
if it meets your needs, you can use it directly.

You register a namespace and a map with this.  You should really
register a namespace; this interface isn't really designed to handle a
full XML tree, though you could override some of the methods if you
really wanted to do this.

The map is the key here.  It is a map from the XML element name to a
handler for that XML element.  So if you had some XML that looked like:

```
<system xmlns="my-namespace">
   <hostname>clixon-master</hostname>
</system>
```

you would have some code like:

```
class Hostname(tf.ElemOpBaseLeaf):
    def validate_add(self, data, xml):
        self.validate(data, None, xml)

    def validate_del(self, data, xml):
        raise Exception("Delete of hostname not allowed")

    def validate(self, data, origxml, newxml):
        value = newxml.get_body()
        if len(value) > 64: # Linux only allow 64 characters
            raise Exception("Host name too long, 64-character max.")
        data.add_op(self, None, value)

    def commit(self, op):
        op.oldvalue = self.getvalue()
        self.do_priv(op)

    def revert(self, op):
        self.do_priv(op)

    def priv(self, op):
        if op.revert:
            if op.oldvalue is None:
                return # We didn't set it, nothing to do
            try:
                self.setvalue(op.oldvalue)
            except:
                pass
        else:
            self.setvalue(op.value)
        return

    def setvalue(self, value):
        self.program_output(["/bin/hostname", value])
        f = open("/etc/hostname", "w")
        try:
            f.write(value + "\n")
        finally:
            f.close()

    def getvalue(self):
        return self.program_output(["/bin/hostname"]).strip()

import clixon_beh.transaction_framework as tf
system_children = {
   "hostname": Hostname("hostname")
}
children = {
   "system": tf.ElemOpBase("system", system_children)
}

handler = tf.TopElemHandler("ietf-system",
                            "my-namespace",
                            children)
handler.p = clixon_beh.add_plugin("system-handler",
                                  handler.namespace, handler)
```

This code shows a number of things about the transaction framework.
Working from the bottom up, you have the `TopElemHandler` class being
allocated with a name, namespace, and a child handler.  Then you add
that as a plugin named `system-handler` with the namespace.

When a toplevel XML tree comes in with the given XML, matching the
namespace, it will call the methods in the `TopElemHandler` in
sequence, `begin`, `validate`, `commit`, etc.  The `begin` call will
create some basic data for the transaction.  `validate` will look at
the top XML element's name.  If it matches something in the registered
map (`children` is the map, it will match "system" in this case), it
will call the handler registered in the map for that name, In this
case `ElemOpBase`.

The `validate`, `validate_add`, or `validate_del` method of
`ElemOpBase` will be called, depending of if this is a change, add or
delete operation.  It will go through the child elements of the XML
object passed to it and call handlers in its children.  In this case,
it will see "hostname" and call the validate method of the `Hostname`
class.  That validates the data then adds an operation to the
operation queue.

One all validation completes successfully, it returns back to clixon.
clixon will call the `complete` method (which does nothing in
`TopElemHandler`) then the `commit` method where the real work
happens.  In this case, it pulls the operation registered in the
queue, which will call the commit method in `Hostname` which then
calls the `hostname` program to set the hostname, and sets the value
in `/etc/hostname`.

If commit completes successfully, the `complete_done` and `end`
methods are called, which are not handled in `TopElemHandler` since
they don't matter for its work.  The user may override these if they
have need.

If commit fails, then the `revert` method will be called to return the
contents to its original state.  The `op` object has a boolean named
`revert`, if it is true then a revert is in process.  It also contains
an `oldvalue` element which is set by default to None.  The user can
set the value in the commit call at the beginning to the original
value so it can know how to restore the data.

### ElemOpBase and Children

`ElemOpBase` is the main class for handling of elements and commit
operations.  All classes that handle XML and/or commits should descend
from this type.

The basic operation was described in the previous section.

When allocating one of these, the `name` and `children` values have
already been discussed.  It has two more options:

* `validate_all` - Normally when processing a validate() call, it will
  only call children validate calls on only XML elements that have
  changed.  This causes it to call validate on all children.  This is
  useful if you need to collect data from all the children.  For
  instance, if you are changing the IP address of an interface, it may
  still be useful to have the netmask, gateway, etc. from the XML
  data, even if it hasn't hanged.
  
* `xmlprocvalue` - By default no processing is done on strings
  returned from `getvalue`.  This causes XML escaping to be done on
  the value returned from `getvalue`.  This is mostly useful on leaf
  classes, and is set by default on all leaf classes in the framework,
  but may be useful for a higher-level class that aggregates all the
  data for something (like getting all the IP address information in
  one shot above the IP address, netmask, etc. XML elements) and
  returns the string.  The user may also call `xmlescape` on their own
  to do this, if that is more convenient.
  
`ElemOpBase` has the following methods:

* `validate_add(self, data, xml)` - This is called when an added
  element is seen, and is called on all its children.  A leaf element
  should override this to add the value.  The data element is data
  about the transaction.  It has the operation queue for the
  transaction.  Users may add their own data to this; in this case the
  name must begin with "user".  Operations would be added to the data
  object with the `data.add_op()` method.
  
* `validate_del(self, data, xml)` - This is called when a deleted element is
  seen, and is called on all its children.  Again, leaf elements would
  override this.

* `validate(self, data, origxml, newxml)` - Called when an element
  with the change flag is seen which means either it or one of its
  children has changed.The old XML and new XML trees are passed in.

* `commit(self, op)` - When the commit phase runs, the operations
  added with `add_op()` have their commit methods called in order.
  This should actually cause the operation to occur on the system.
  
* `revert(self, op)` - If a commit fails, then this method is called
  on all operations in the queue in reverse order to undo what they
  have done.
  
* `do_priv(self, op)` - Called to perform the operation at the
  original privilege clixon was run at, generally root.  This will
  call the `priv(self, op)` method on the class at privilege.
  
* `getxml(self, path, namespace=None)` - Return an XML string for
  class or some child.  If the path is empty, that means return the
  value for this class.  In that case, getvalue() for the class is
  called, escaped if that is set, and returned wrapped in the XML
  name.  If the path is not empty, that means we are not returning the
  full XML for this path, we are just wrapping it and returning it for
  a child.  In that case pull the first item off the patch (which
  should be this class) and call `getxml` on the child with that name,
  still wrapping it in the XML name.
  
  If `namespace` is not None, then it should be a string and the
  `xmlns` value is set in this elements XML tag.
  
* `getvalue(self)` - Return the string for this value.  By default
  this goes through the children of the class and calls `getvalue` on
  them, wrapping it with the child's XML name.  Leaf children, or
  children that are handling the final assembly of the string for a
  tree, must override this.

* `program_output(self, args, timeout=1000)` - This is a convenience
  method that calls a program and gets its stdout, stderr, and return
  value.  If the return value is not 0, an exception is raised with
  the stderr output of the program.  If the return value is 0, then
  the stdout of the program is returned.
  
`ElemOpBaseLeaf` is `ElemOpBase` but with `xmlprocval` set to True by
default.

`ElemOpBaseConfigOnly` is `ElemOpBaseLeaf` with everything default to
do nothing.  This is for an XML leaf element that is for the
configuration database only, that doesn't do anything in the backend.

`ElemOpBaseCommitOnly` is `ElemOpBase` with all the validate and value
calls exceptions, and only take a name at creation time.  This is only
for use as an operation class for `add_op()`.

`ElemOpValidateOnly` is `ElemOpBase` with commit, revert, and getvalue
causing exceptions.  This is for things that are only used for
validation and not for committing.  This sets `validate_all` to True
by default.  This would be used for elements that collect data, but a
higher-level element is used for the commit.  For instance, if you had
an IP address, you could use the `ElemOpValidateOnlyLeaf` class for
the individual IP, netmask, and gateway addresses and store the values
in the data parameter.  In the class that's the parent of those use
`ElemValidateOnly` as the class but override `getvalue` to get all the
values together, and have the commit set all the values together from
what was set in the data value.

`ElemOpValidateOnlyLeaf` is `ElemOpValidateOnly` with `xmlprocvalue`
set to True.  `validate_del` doesn't do anything, and `validate` calls
`validate_add`.

`ElemOpBaseValueOnly` is `ElemOpBaseLeaf` with all validation and
commit operations raising exception.  The only thing this can be used
for is fetching the value.  This is useful for "config false" items in
the YANG.
