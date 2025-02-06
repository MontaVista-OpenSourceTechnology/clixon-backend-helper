# Clixon Backend Helper Vade Mecum

What does Vade Mecum mean?  Well, it's Latin, sort of meaning "as we
walk" or "as we go".  It's used for explainations that walk a user
through something.  Since this is a a fairly complex item, we will
walk through a basic things.

You will need to already have `clixon` and `clixon-backend-helper`
installed.  If these are installed in `/usr/local` (or anyplace but
`/usr`) see the notes in README.md in the main directory for
instructions.

We pick a relatively simple example here, we will configure the server
side of chronyd.  That's a program that provides a time
synchronization server and client.  The client side is already handled
by linux-server, so we will just do the server side here.

## Starting

To begin, we want to make the configuration as simple as possible.
The client side is configured in /etc/chrony/sources.d.  We will
configure the server side in /etc/chrony/conf.d/serve.conf.

We only have one server configuration, so we only need one file.  If
we supplied multiple independent server, each server could have its
own file.  This makes it easy to configure; the filename can be what
is provided as the key in the YANG list But that's not what we are
doing here.  You can look in linux-system.py for examples of that.

The contents of a server file are:
```
   allow address/subnet
   allow....
   deny address/subnet
   deny...
   port <port>
   ntsport <port>
   ntsdumpdir /var/lib/chrony
   ntsserverkey /crypto/keys/nts.key
   ntsservercert /crypto/keys/nts.crt
```

There are many other options, but these are the ones we care about.
Note that we will not make ntsdumpdir, or the key/certificate file
names configurable.  You could put these in another file, but it's not
a big deal.

We also have some statistics that might be useful, you can look at the
chronyc `tracking`, `clients` and `serverstats` commands.

Now we need some YANG code.  RFC 9249 has an NTP one, but it's not
really very useful.  It doesn't have NTS support, it has a lot of
things not in chrony, and kind of assumes ntpd.  So we will write our
own and maybe use that as a reference.  Note that I'm not giving a
YANG lesson here, you need to learn that on your own.

In the `examples/chronyd-server-1` directory, an example has been
created to show how to tie in the the `clixon_beh` code.  It has some
YANG code for this, and some other files for installation, and a
python file.

In that directory, you can run `meson build`, `meson compile -C build`,
then `sudo meson install -C build`.  This assumes you have already installed
clixon and clixon_beh in /usr/local, it should install in /usr/local, too.

Then you can start clixon with:
```
sudo CHRONYD_SERVER_SYSBASE=/home/cminyard/tmp/clixon \
  clixon_backend -f /usr/local/etc/clixon/chronyd-server.xml -s startup -F -l e
```
This will start with the startup database, which is fine. The
`CHRONYD_SERVER_SYSBASE` will be explained later.  You will notice
that it tries to fetch some system\_only data, we will talk about that
later, too.

Now lets set the port through RESTCONF:
```
curl -X POST http://localhost/restconf/data \
  -H "Content-Type: application/yang-data+json" \
  -d '{"chronyd-server:server":{"port":"1234"}}'
```
This is not a RESTCONF tutorial, either, you will need to read up on that,
too.  You will get the following output from clixon:
```
Validate:
  orig: <server xmlns="http://mvista.com/chronyd" clixonflags="change"><port clixonflags="change,default">123</port><ntsport clixonflags="default">4460</ntsport></server>
  new: <server xmlns="http://mvista.com/chronyd" clixonflags="change"><port clixonflags="change">1234</port><ntsport clixonflags="default">4460</ntsport></server>
Commit: <server xmlns="http://mvista.com/chronyd" clixonflags="change"><port clixonflags="change">1234</port><ntsport clixonflags="default">4460</ntsport></server>
Commit Done: <server xmlns="http://mvista.com/chronyd" clixonflags="change"><port clixonflags="change">1234</port><ntsport clixonflags="default">4460</ntsport></server>
End:
```

If you look at the code, you can see that it's just printing out the
xml received.  This will be stored in the clixon database and applied
through the `clixon_beh` interface.  The operations on the transaction
object are explained in the README.md file in this directory.

Looking in the XML, you can see the top level has the "change" flag
because something is being changed under it, and that the `port` field
has the "change" flag in it, because that is what is being changed,
and the `ntsport` does not, but it does have the "default" flag
because that's the default.

We can fetch the data:
```
curl -X GET http://localhost/restconf/data/chronyd-server:server?content=config
```
which will output:
```
{"chronyd-server:server":{"port":1234}}
```
which comes from clixon's database.

Now let's add an allows:
```
curl -X PATCH http://localhost/restconf/data/chronyd-server:server \
  -H "Content-Type: application/yang-data+json" \
  -d '{"chronyd-server:server": [ { "allows": "192.168.100.0/24"}]}'
```
and we get the output:
```
Validate:
  orig: <server xmlns="http://mvista.com/chronyd"><port>1234</port><ntsport clixonflags="default">4460</ntsport></server>
  new: <server xmlns="http://mvista.com/chronyd" clixonflags="change"><allows clixonflags="add">192.168.100.0/24</allows><port>1234</port><ntsport clixonflags="default">4460</ntsport></server>
Commit: <server xmlns="http://mvista.com/chronyd" clixonflags="change"><allows clixonflags="add">192.168.100.0/24</allows><port>1234</port><ntsport clixonflags="default">4460</ntsport></server>
Commit Done: <server xmlns="http://mvista.com/chronyd" clixonflags="change"><allows clixonflags="add">192.168.100.0/24</allows><port>1234</port><ntsport clixonflags="default">4460</ntsport></server>
End:
```
You can again see the "change" flag at the top level, because something
under it is being changed.  We can again query it:
```
curl -X GET http://localhost/restconf/data/chronyd-server:server?content=config
```
and get:
```
{"chronyd-server:server":{"allows":["192.168.100.0/24"],"port":1234}}
```

And we can delete the list element:
```
curl -X DELETE http://localhost/restconf/data/chronyd-server:server/allows='192.168.100.0%2f24
```
and here's the output from clixon:
```
Validate:
  orig: <server xmlns="http://mvista.com/chronyd" clixonflags="change"><allows clixonflags="del">192.168.100.0/24</allows><port>1234</port><ntsport clixonflags="default">4460</ntsport></server>
  new: <server xmlns="http://mvista.com/chronyd"><port>1234</port><ntsport clixonflags="default">4460</ntsport></server>
Commit: <server xmlns="http://mvista.com/chronyd"><port>1234</port><ntsport clixonflags="default">4460</ntsport></server>
Commit Done: <server xmlns="http://mvista.com/chronyd"><port>1234</port><ntsport clixonflags="default">4460</ntsport></server>
End:
```
where you can see the "del" flag on the item that is being deleted.
(Note that the "/' in the field had to be replaced with %2f in the URL
due to encoding rules.)

So we can play around with this and get/set various data.  We can set
a key or a certificate, but it will not be returned to you because
it's system-only data and we haven't added that code.  Except we won't
add that code, because you never want to be able to fetch a key
through this interface.

We could go through the XML here, look for "change", "add", and "del"
flags, and implement this all ourselves.  But that would be hard, and
that's why the transaction framework exists.  It handles all the XML
parsing and such and just calls the functions you need.

## The Transaction Framework

So lets go to the next stage, n the `examples/chronyd-server-2`
directory.  This adds the setting of `sysbase`, some basic
infrastructure that we will need later, and notice that `Handler` now
derives from some other types and is created a little differently.

The `sysbase` things lets us override where configuration files are.
That way it's easier to test the program without screwing up our
system.

This will do basically the same thing as our previous plugin, but is a
step in the direction we need.  Let's start it with the "running"
database instead of startup, so it will have the data we saved earlier:
```
sudo CHRONYD_SERVER_SYSBASE=/home/cminyard/tmp/clixon \
  clixon_backend -f /usr/local/etc/clixon/chronyd-server.xml -s running -F -l e
```
You can query that; not much has changed.

So lets go ahead and fill in everything.  Look in
`implementations/chronyd-server` for a full implementation.  You will
notice that the Handler has been mostly remove, all of the handling
is default.

We have created a `ServerFile` class that can read in and write out
the server file and key and certificate.  This is the central class
for reading and updating information.

Next we have a `Server` class that represents the top level server
YANG element.  We do all the commit processing here, so we add ourself
as an operation in the validate method so the commit operation will
happen on this class.  You can see the `commit`, `revert`, and `end`
methods below.  These will be called with raised privileges (root)
because `priv=True` is set when we add the op.

There is also a getxml() function.  This is used for fetching
configuration data.  This reads in the server data file and passes the
information to lower function, eventually all the other things under
server are called with this data.

Next are all the children of the `server` node, the allow list, the
deny list, the port, ntsport, and key/certs.  The non-list ones are
pretty straightforward; we have already fetch the data in the Server
class, so we just return the data we fetch, and we set the data as
necessary.  The `allow` and `deny` lists are more complicated because
they are lists.  Read the comments in the Allow class for details.

We then create our top-level element map.  An element map holds the
children and the child processing for a non-leaf node.  You create one
of these and then add children to it.  Next you can see that we create
a `server` with `chronydserver` as the parent.  We put the `xpath` in
it, too, mostly as documentation for now.  Then we add all the
children of the `server` node.

We have a similar sort of thing for the `statistics` node.

Then at the end we add the server and statistics nodes to the
top-level node.  Notice that the namespace is set on both of these.
At this level, you must set the namespace.  Also, if you have
something else that is in a different namespace (like an augment or
deviation) you must put the proper namespace on that node.  For
instance, the "certificate" filed in the DNS namespace is an augment
done in linux-system.py, it is in the namespace of linux-system, not
ietf-system, so it's namespace is set.

Then we come to our handler.

## Exceptions

Note that if you raise an exception anywhere when using the
transaction framework, the transaction framework handles returning a
response with the error information.  It has a special exception,
`RPCError`, that let's you put your own data.  In some cases the YANG
files will say to return a specific error and it's good for this, but
you can also return specific information about things the user has
done wrong.  Here's an example:
```
raise tf.RPCError("application", "invalid-value", "error",
                  "systemd DNS update not supported here")
```

## System Only and Source of Truth

`clixon` has a concept called "system only" defined in
https://clixon-docs.readthedocs.io/en/latest/datastore.html#system-only-config
that lets use handle a few things special.

In general, clixon considers its database the "source of truth".  This
means that when clixon comes up, it will take its database and apply
it to the system.  This is fairly normal with NETCONF/RESTCONF, but
has a few problems:

* Some things are managed by the system.  For instance, linux-system can
  manage the password file.  But you can add an RPM package and have the
  password file change, too, and clixon won't see that.  Other things of
  this nature can happen, too.
  
* `clixon` would then hold all the keys and certificates that are
  configured in the system.  This is, of course, bad.  Generally those
  are stored in secure places, like a TPM or a secure partition, and
  the clixon database is not a secure place.
  
To solve this problem, you can mark a YANG node as "system only" by adding
the following:
```
import clixon-lib {
    prefix cl;
}
...
container/leaf/... name {
    cl:system-only-config {
	description
	    "Keys and certificates are system-only.";
    }
    ...
}
```

When clixon needs to operate on something, it will fetch the system
only data from the system using the `system_only` callback.  So, for
instance, if it adds a user to the password file, it will first fetch
the data, do the operation, commit it, then purge the system only data
from its database.

For secure data, you don't want to return the data to clixon.  You may
not be able to.  So instead, just return a dummy value, generally "x".
Something that won't be a valid key/certificate/hash.  You should then
ignore that value if it happens to be sent to you to validate.  That
*shouldn't* happens, but just to be safe...
