# Python and clixon

This directory contains a basic Python 3 interface to clixon and a
transaction framework module that simplifies the handling of
transactions coming from clixon.

This is more of an explaination of everything.  If you want something
that leads you through the creation of your own code, see
VADE\_MECUM.md in this directory.

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

	def system_only(self, nsc, xpath):
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

    def start(self):
        return 0

    def yang_patch(self):
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
        if xpath == "/":
           return (0, ("<xmldata1>", "xmldata2"))
        else
           return (0, "<xml data>")
		   
	def system_only(self, nsc, xpath):
		return (0, "<xml data>")
```

The statedata method returns a tuple, the first items is an integer
error, the second is either a string holding xml for the state data,
or a tuple of strings holding multiple XML trees to add.  If you
return an error, the xml value may be empty, it is ignored.  The rest
return -1 on error an 0 on success.  If they return an error, they
should call `clixon_err` first to report what went wrong.

The system_only part is used if you have data that is always
represented by the system.  See
https://clixon-docs.readthedocs.io/en/latest/datastore.html#system-only-config
for detail on that.

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

#### Error Handling

If an exception occurs and is returned into the clixon interface, an
error and traceback will be printed by default.  If you want to catch
the error yourself, you can call:
```
def handler(exc, value, traceback):
    if exc.__class__ == type:
        traceback.print_exception(exc, value, traceback)
    else:
        traceback.print_exception(exc)

clixon_beh.set_err_handler(handler)
```

The interface here is unfortunate, but due to changes in the python
API in version 3.12.  Older python C APIs returned three values, type,
value and traceback, when getting the exception.  That is now
deprecated and the new function returns a single exception object.

So in the handler, if `exc.__class__` is `type`, then it's the old
interface and the `value` and `traceback` should be valid.  Otherwise
it's the new interface and only the `exc` value is valid.

### User Name

clixon will extract the user name from a number of sources depending
on the access method.  For NETCONF and CLI, it's the user doing the
operation.  For RESTCONF, it's the common name in the certificate.

This is available via the `username_get()` function.  This can be used
to restrict some operations to specific users.  Note that this may
return `None` if the username is not set, like during initialization.

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
for the top element of an XML tree from clixon, what you register with
`clixon_beh.add_plugin()`.  You can derive from this class and
override things you might need, like begin, daemon, etc.  Or if it
meets your needs, you can use it directly.

You register a namespace and a map with this.  You should really
register a namespace; this interface isn't really designed to handle a
full XML tree, though you could override some of the methods if you
really wanted to do this.

The map is the key here.  It is a map from the XML element name to a
handler for that XML element.  So if you had some YANG that looked like:

```
module sysinfo {
    yang-version 1.1;
    namespace "my-namespace";
    prefix sys;
    container system {
        leaf hostname {
            type string;
            description "The host name";
        }
    }
}
```

the XML for it might be:

```
<system xmlns="my-namespace">
   <hostname>clixon-master</hostname>
</system>
```

you would have some code like:

```
import clixon_beh.transaction_framework as tf

MY_NAMESPACE = "my-namespace"

class Hostname(tf.YangElem):
    def validate_add(self, data, xml):
        self.validate(data, None, xml)

    def validate_del(self, data, xml):
        raise tf.RPCError("application", "invalid-value", "error",
                          "Delete of hostname not allowed")

    def validate(self, data, origxml, newxml):
        value = newxml.get_body()
        if len(value) > 64: # Linux only allow 64 characters
            raise tf.RPCError("application", "invalid-value", "error",
                              "Host name too long, 64-character max.")
        data.add_op(self, None, value)

    def commit(self, op):
        op.oldvalue = self.getvalue(None)
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

    def getvalue(self, data, vdata=None):
        return self.program_output(["/bin/hostname"]).strip()

sysinfo = tf.YangElemMap(None, "/")
s = sysinfo # shorthand

s.add_map("/", tf.YangElem("system", tf.YangType.CONTAINER,
                           namespace=MY_NAMESPACE))
s.add_leaf("/system", Hostname("hostname", tf.YangType.LEAF))

handler = tf.TopElemHandler("sysinfo", sysinfo)
handler.p = clixon_beh.add_plugin("sysinfo", MY_NAMESPACE, handler)
```

This code shows a number of things about the transaction framework.
Working from the bottom up, you have the `TopElemHandler` class being
allocated with a name, namespace, and a child handler.  Then you add
that as a plugin named `sysinfo` with the namespace, matching the yang
module.

When a toplevel XML tree comes in with the given XML, matching the
namespace, it will call the methods in the `TopElemHandler` in
sequence, `begin`, `validate`, `commit`, etc.  The `begin` call will
create some basic data for the transaction.  `validate` will look at
the top XML element's name.  If it matches something added to the
registered `YangElemMap`, it will recurse down to that element's
handler.

The top-level children (with "/" as the starting path) must set the
namespace for all the elements.

The `begin` call in `TopElemHandler` will create an item of the class
`Data` that you can use to store data about the transaction as you
work on it.  The general scheme is that in the validation call you
store data about the transaction in the `Data` object.  You generally
do this with the `add_op` call to the `Data` class; it adds an
operation to a queue with a handler and some data you provide.  That
handler gets run when commit happens.

The `validate`, `validate_add`, or `validate_del` method of
`YangElem` will be called, depending of if this is a change, add or
delete operation.  It will go through the child elements of the XML
object passed to it and call handlers in its children.  In this case,
it will see "hostname" and call the validate method of the `Hostname`
class.  That validates the data then adds an operation to the
operation queue.

One all validation completes successfully, it returns back to clixon.
clixon will call the `complete` method (which does nothing in
`TopElemHandler`) then the `commit` method where the real work
happens.  In this case, it pulls the operations registered in the
queue, which will call the `commit` method in `Hostname` which then
calls the `hostname` program to set the hostname, and sets the value
in `/etc/hostname`.

If commit completes successfully, the `commit_done` and `end` methods
are called, which are not handled in `TopElemHandler` since they don't
matter for its work.  The user may override these if they have need.
There is an `done` boolean in the `op` parameter that's passed around
the various commit operations, you can use that to tell if you are in
a done operation.

If commit fails, then the `revert` method will be called to return the
contents to its original state.  Unlike the clixon plugin interface,
which will *not* call the revert on the plugin that failed, the
`revert` method for the `transaction_framework` handler *will* be
called on the plugin that failed in addition to all previously called
plugins.  The `op` parameter to the `revert` method has a boolean
named `revert`, if it is true then a revert is in process.  It also
contains an `oldvalue` element which is set by default to None.  The
user can save the old value in the commit call at the beginning so the
it can set it back to the original value if a `revert` happens.

### userdata

The `userdata` field in the transaction is created by the transaction
framework as an object of class Data.  This is used by the transaction
framework for storing information, and it's passed into all the
methods.  The user can add their own items; they should prefix the
name with "user" if they do.

The transaction framework adds the username performing the operation
(see "User Name" above) as the `tf_username` field.

### YangElem and Children

`YangElem` is the main class for handling of elements and commit
operations.  All classes that handle XML and/or commits should descend
from this type.

The basic operation was described in the previous section.

The second parameter for the `__init__` call, `etype` is one of:

* YangType.CONTAINER
* YangType.LEAF
* YangType.LIST
* YangType.LEAFLIST

That corresponds to the Yang element types.

When allocating one of these, the `name`, `etype`, and `children`
values have already been discussed.  It has two more options:

* `validate_all` - Normally when processing a validate() call, it will
  only call children validate calls on only XML elements that have
  changed.  This causes it to call validate on all children.  This is
  useful if you need to collect data from all the children.  For
  instance, if you are changing the IP address of an interface, it may
  still be useful to have the netmask, gateway, etc. from the XML
  data, even if it hasn't hanged.

* `xmlprocvalue` - If true, the string returned from `getvalue` will
  be processed by `xmlescape`.  This should only be set on leaf types.
  The default is False for non-leaf values and True for leaf values.
  The user may also call `xmlescape` on their own to do this, if that
  is more convenient.

* `wrapxml` - If true, the value returned from `getvalue` will be in
  wrapped the xml name of the class.  This should only be set on leaf
  types.  If you have a leaf type where you need to do your own XML
  processing (like it's in a different namespace) you need to set this
  to False.

`YangElem` has the following methods:

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

* `getxml(self, path, indexname=None, index=None, vdata=None)` -
  Return an XML string for class or some child.  If the path is empty,
  that means return the value for this class.  In that case,
  getvalue() for the class is called, escaped if that is set, and
  returned wrapped in the XML name.  If the path is not empty, that
  means we are not returning the full XML for this path, we are just
  wrapping it and returning it for a child.  In that case pull the
  first item off the path (which should be this class) and call
  `getxml` on the child with that name, still wrapping it in the XML
  name.

  If processing a list, indexname and index will be set to the index
  to fetch.

  If `namespace` is not None, then it should be a string and the
  `xmlns` value is set in this elements XML tag.

* `getonevalue(self, data, vdata=None)` - Called to fetch an individual
  value.  For non-lists, this is basically the same as
  getvalue().  For lists, this is for getting data from the list
  element (from the item returned by `fetch_index` or iterated from
  the list returned by `fetch_full_index`.

* `getvalue(self, data, vdata=None)` - Return the string for this value.  By
  default this goes through the children of the class and calls
  `getvalue` on them, wrapping it with the child's XML name.  Leaf
  children, or children that are handling the final assembly of the
  string for a tree, must override this.

* `fetch_index(self, indexname, index, vdata)` - Return the list item for
  the element with the name indexname and the value index.

* `fetch_full_index(self, vdata)` - Return the full list of items in
  an iterable object.

* `program_output(self, args, timeout=1000)` - This is a convenience
  method that calls a program and gets its stdout, stderr, and return
  value.  If the return value is not 0, an exception is raised with
  the stderr output of the program.  If the return value is 0, then
  the stdout of the program is returned.

`YangElemConfigOnly` is `YangElem` with everything default to
do nothing.  This is for an XML leaf element that is for the
configuration database only, that doesn't do anything in the backend.

`YangElemCommitOnly` is `YangElem` with all the validate and value
calls exceptions, and only take a name at creation time.  This is only
for use as an operation class for `add_op()`.

`YangElemValidateOnly` is `YangElem` with commit, revert, and getvalue
causing exceptions.  This is for things that are only used for
validation and not for committing.  This sets `validate_all` to True
by default.  This would be used for elements that collect data, but a
higher-level element is used for the commit.  For instance, if you had
an IP address, you could use the `YangElemValidateOnly` class with type
set to LEAF for the individual IP, netmask, and gateway addresses and
store the values in the data parameter.  In the class that's the
parent of those use `YangElemValidateOnly` as the class but override
`getvalue` to get all the values together, and have the commit set all
the values together from what was set in the data value.

`YangElemValidateOnlyLeafList` is like `YangElemValidateOnly`, but
does most of the work for leaf lists.  It assumes that the
`fetch_full_index()` method returns a tuple of strings that are the
same as the string values in the leaf list.  And it adds a method
`validate_fetch_full_index()` that the user class must override that
returns a mutable tuple of strings for add/delete operations.

### Containers

We have only shown a top-level container, YANG specifies a
tree-structured model for the system.  Let's assume we have to change
the YANG to add a boot time, and we want that combined with the

```
module sysinfo {
    yang-version 1.1;
    namespace "my-namespace";
    prefix sys;
    container system {
        container hostinfo {
            leaf hostname {
                type string;
                description "The host name";
            }
            leaf boot-datetime {
                config false;
                type yang:date-and-time;
                description "The time the host booted";
            }
            leaf current-datetime {
                config false;
                type yang:date-and-time;
                description "The time ont the host now";
            }
        }
    }
}
```

So we have added a new container name `hostinfo` that has the
hostname, a boot time that is read-only, and a current time that is
read-only.  We create another level of mapping:

```
class SystemStateClock(tf.YangElemValueOnly):
    def getvalue(self, vdata=None):
        date = self.program_output([datecmd, "--rfc-3339=seconds"]).strip()
        date = date.split(" ")
        if len(date) < 2:
            raise Exception("Invalid date output: " + str(date))
        if "+" in date[1]:
            date[1] = date[1].replace("+", "Z+", 1)
        else:
            date[1] = date[1].replace("-", "Z-", 1)
            pass
        date = date[0] + "T" + date[1]

        if self.name == "boot-datetime":
            bdate = shlex.split(self.program_output(["/bin/who","-b"]))
            if len(bdate) < 4:
                raise Exception("Invalid who -b output: " + str(bdate))
            # Steal the time zone from the main date.
            zone = date.split("Z")
            if len(zone) < 2:
                raise Exception("Invalid zone in date: " + date)
            date = bdate[2] + "T" + bdate[3] + "Z" + zone[1]

        return date

    pass

sysinfo = tf.YangElemMap(None, "/")
s = sysinfo #shorthand

s.add_map("/", tf.YangElem("system", tf.YangType.CONTAINER,
                           namespace=MY_NAMESPACE))
s.add_map("/system", tf.YangElem("hostinfo", tf.YangType.CONTAINER))
s.add_leaf("/system/hostinfo",
           Hostname("hostname", tf.YangType.LEAF))
s.add_leaf("/system/hostinfo",
           SystemStateClock("boot-datetime", tf.YangType.LEAF))
s.add_leaf("/system/hostinfo",
           SystemStateClock("current-datetime", tf.YangType.LEAF))
del s
```

We haven't discussed this before, but the `add_map` and `add_leaf` are
used to add elements to a the structure map.  The first parameter,
path, is obviously the YANG path to the element being added.  Then you
allocate the proper element for the second parameter.  `add_map` can
only be used on containers and lists; these are things that have
sub-elements (in a data structure called a map).  Leafs do not have
sub-elements.

Notice that you can re-use classes with some sort of differentiator.
If there are containers in containers in containers, you can continue
to create new maps; building a tree-structure of maps.

### Lists

In addition to containers, there are also lists, which hold lists of
containers and/or leafs, and leaf lists, which is a list of single leaf
items.  These are both handled in a similar manner.

#### Leaf Lists

If we had a weird system that had a list of hostnames, the YANG for
that might be:
```
        leaf-list hostname {
            type string;
            description "The host name";
        }
```

The class to handle this might be:

```
class Hostname(tf.YangElem):
    def validate_add(self, data, xml):
        self.validate(data, None, xml)

    def validate_del(self, data, xml):
        raise tf.RPCError("application", "invalid-value", "error",
                          "Delete of hostname not allowed")

    def validate(self, data, origxml, newxml):
        if data.hostname_op is None:
            data.hostname_op = data.add_op(self, None, [])

        value = newxml.get_body()
        if len(value) > 64: # Linux only allow 64 characters
            raise tf.RPCError("application", "invalid-value", "error",
                              "Host name too long, 64-character max.")
        data.hostname_op.value.append(value)

    def commit(self, op):
        op.oldvalue = method_to_get_the_current_list_of_values()
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
        set_the_list_of_values(value)

    def fetch_full_index(self, vdata):
        return method_to_get_the_current_list_of_values()

    def getonevalue(self, vdata):
        return vdata

s.add_leaf("/system/hostname", Hostname("hostname", tf.YangType.LEAFLIST))
```

You see a number of new things here.  First of all, there is a
`hostname_op` member added in the data.  It's added in the begin
method of the top level handler; More on that in the next section.  We
use that member to hold data for the hostnames until they are all
collected and can be committed.  The validate call will create a list
and add to it for each new validate call.

That covers the validation side, next we move to fetching the values.

You see the `fetch_full_index` method.  (Ignore `vdata` for now, we
will discuss this later).  This will fetch all the data items into a
list (or some iterable object) and is called once for a transaction.
The code will then call `getonevalue` with each item in the list as
`vdata`.  As usual, the framework handles all the XML wrapping and
such.

#### Normal Lists

In another weird system, we have a list of hostinfo items, so the
container becomes a list and it's indexed by hostname.  Instead of
using `tf.YangElem`, we must now create our own class:

```
class HostData:
    def __init__(self):
        self.hostname = None

class HostInfo(tf.YangElem):
    def validate_add(self, data, xml):
        if data.hostinfo_op is None:
            data.hostinfo_op = data.add_op(self, None, [])
        data.hostinfo_data = HostData()
        data.hostinfo_op.value.append(data.hostinfo_data)

        super().validate_add(data, xml)
        return

    def validate(self, data, origxml, newxml):
        self.validate_add(data, newxml)
        return

    def commit(self, op):
        op.oldvalue = get_all_hostinfo_in_a_list()
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
        set_the_list_of_values(value)

    def fetch_index(self, indexname, index, vdata):
        mydata = get_all_hostinfo_in_a_list()
        for i in vdata:
            if i.hostname == index:
                return i
            pass
        return None

    def fetch_full_index(self, vdata):
        # Returns a list of HostData items.
        return get_all_hostinfo_in_a_list()

s.add_map("/system", HostInfo("hostinfo", tf.YangType.LIST,
                              validate_all = True))
# Add children here with add_map and add_leaf
```

This is something like a leaf list, but instead, the
`fetch_full_index` method returns all the items.  The transaction
framework will call this when it's fetching the full list of hostinfo,
and will then call the children's `getvalue` calls.

We might also get a query where just a single list item is being set.
In this case thetransaction framework will call `fetch_index` returns
a single one of these items.

For query, the children will be called with the `vdata` item set to
their element's data.  They can fetch the data they need from it.

For validation, we create an operation and then fill in the individual
items.  Each child will will need to fill in their piece of the data.
Here's the hostname child in this case:

```
class Hostname(tf.YangElemValidateOnly):
    def validate_add(self, data, xml):
        self.validate(data, None, xml)

    def validate_del(self, data, xml):
        raise tf.RPCError("application", "invalid-value", "error",
                          "Delete of hostname not allowed")

    def validate(self, data, origxml, newxml):
        value = newxml.get_body()
        if len(value) > 64: # Linux only allow 64 characters
            raise tf.RPCError("application", "invalid-value", "error",
                              "Host name too long, 64-character max.")
        data.hostinfo_data.hostname = value

    def getvalue(self, vdata=None):
        return vdata.hostname
```

The data has already been fetched for query and set up for validation,
this just needs to either set its element or get its element.  The
parent handles the commit here, too.  The ```YangElemValidateOnly```
is for this case, the commit and revert are errored out there if they
ever get called.

### Unimplemented Items

You may have optional things in the YANG spec that you don't
implement.  If you want YANG validation to succeed, you will need to
add those to your implementation as unimplemented items.

The easiest way to do this is add the item as a
`YangElemValueOnlyUnimpl`.  This will just return an empty string for
the result, doing nothing.  But that way it shows up in the tree so
the YANG validation will succeed for those items.

### Higher Level Containers Handling Data For Lower Level Items

It is often better to fetch all the data for an operation at once.
The following examples fetches data from /etc/resolv.conf.  Instead of
fetching data for each data item from resolv.conf, it's better to just
fetch it all at once and provide it in a data structure to the
lower-level items.

In the same way, when committing, it is better to collect up all the
data in a data structure and write resolv.conf all at once.  That's
safer and easier to recover from.

The YANG for this is in the standard ietf-system.yang file under
dns-resolver, you can look at that yourself; I won't include it here.

To implement this, we first must add a data item to the main data
object:

```
class Handler(tf.TopElemHandler, tf.ProgOut):
    def exit(self):
        self.p = None # Break circular dependency
        return 0;

    def begin(self, t):
        rv = super().begin(t)
        if rv < 0:
            return rv
        data = t.get_userdata()
        data.userDNSOp = None # Replaced when DNS operations are done.
        return 0

    pass

handler = Handler("ietf-system", children)
handler.p = clixon_beh.add_plugin(handler.name, handler.namespace, handler)
```

Notice that we have added an `exit` override; since we store `p` in
the handler, and `p` has a pointer to the handler, we have a circular
reference and we need to break it so Python will garbage collect it.

In the `begin` method we have added a `useDataOp` item.  When processing
DNS data, this will hold the current operation being done.

Now we add dns-resolver to the system map:

```
class DNSResolver(tf.YangElem):
    def validate_del(self, data, xml):
        # FIXME - maybe delete /etc/resolv.conf?  or fix the YANG?
        raise tf.RPCError("application", "invalid-value", "error",
                          "Cannot delete main DNS data")

    def fetch_resolv_conf(self):
        # Read resolve.conf into vdata.  vdata will be a map holding
        # the search values in "search", a list of servers in "server",
        # and the options in a map in "options".
        return vdata

    def getxml(self, path, indexname=None, index=None, vdata=None):
        vdata = self.fetch_resolv_conf()
        if vdata is None:
            return ""
        return super().getxml(path, indexname, index, vdata=vdata)

    def getvalue(self, vdata=None):
        vdata = self.fetch_resolv_conf()
        if vdata is None:
            return ""
        return super().getvalue(vdata=vdata)

s.add_map("/system", tf.YangElem("dns-resolver", tf.YangType.CONTAINER,
                                 validate_all = True))
s.add_map("/system/dns-resolver",
          tf.YangElem("options", tf.YangType.CONTAINER))
```

We have `validate_all` set to true; this will cause the framework to
call the validation calls for all items in the tree, even if they
haven't changed.  This is important because we must collect all the
data for resolv.conf to do a full write of it.

The `DNSResolver` class overrides `getxml` and `setvalue` to fetch the
vdata value, all the data from resolv.conf, and pass it to super().

Now for the children:

```
s.add_leaf("/system/dns-resolver",
           DNSSearch("search", tf.YangType.LEAFLIST, validate_all=True))
s.add_map("/system/dns-resolver",
           DNSServer("server", tf.YangType.LIST, validate_all=True))
s.add_map("/system/dns-resolver",
          tf.YangElem("options", tf.YangType.CONTAINER, validate_all=True))
```

These children will all get `vdata` as the full data read from
resolv.conf and they must process that.  For instance, here is the
options handling:

```
class DNSTimeout(tf.YangElemValidateOnly):
    def validate_add(self, data, xml):
        ddata = dns_get_opdata(data)
        ddata.timeout = xml.get_body()
        return

    def getvalue(self, vdata=None):
        return vdata["timeout"]

    pass

class DNSAttempts(tf.YangElemValidateOnly):
    def validate_add(self, data, xml):
        ddata = dns_get_opdata(data)
        ddata.attempts = xml.get_body()
        return

    def getvalue(self, vdata=None):
        return vdata["attempts"]

    pass

class DNSUseVC(tf.YangElemValidateOnly):
    def validate_add(self, data, xml):
        ddata = dns_get_opdata(data)
        ddata.use_vc = xml.get_body().lower() == "true"
        return

    def getvalue(self, vdata=None):
        # We have to add our own namespace, so set wrapxml to false for
        # this class and do it ourself.
        return ("<use-vc xmlns=\"" + MY_NAMESPACE + "\">" +
                vdata["use-vc"] + "</use-vc>")

    pass

s.add_leaf("/system/dns-resolver/options",
           DNSTimeout("timeout", tf.YangType.LEAF))
s.add_leaf("/system/dns-resolver/options",
           DNSAttempts("attempts", tf.YangType.LEAF))
s.add_leaf("/system/dns-resolver/options",
            DNSUseVC("use-vc", tf.YangType.LEAF,
                     wrapxml=False, xmlprocvalue=False))
```

Note that what is passed into the super() calls is passed into the
"options" `tf.YangElem` and is then passed into its children.

Notice also the user of `wrapxml` and `xmlprocvalue` for "use-vc".
This is because this particular item is in a different namespace, so
the namespace must be inserted.  You could also set the namespace on
DNSUseVC to do this, too.  Other reason may exist that require
hand-formatting the returned data, that's what these are for.

Note that the value of vdata, both here and what's returned from
`fetch_index` and `fetch_full_index` need not be the full data.  They
could just be indexes into a database, or filenames, or whatever.  But
whatever is passed in is given to the children for their use.

### Checking your implementation against the YANG

You are basically implementing a tree structure in your code that
should match the YANG implementation.  The transaction framework
provides a tool to tell if your implementation matches the YANG.  Just
add the following to your top-level handler, the thing that implements
`tf.TopElemHandler`:
```
    def start(self):
        if not tf.check_topmap_against_yang(self, "data"):
            return -1
        return 0
```

This will look up the YANG code for what you are implementing and
compare it to the tree you have created.  It will issue clixon error
logs for things that don't match so you can fix them.  This way if
things change and there's a bug, like if someone enables a feature but
it's not implemented, clixon will fail at startup.

The "data" parameter is the mount, that's the default place where YANG
specifications are mounted.

### Error Handling

The transaction framework sets an error handler.  If you raise an
RPCError() type, then it will automatically create an rpc error return
based on the values.  Otherwise it handles a generic exception.
