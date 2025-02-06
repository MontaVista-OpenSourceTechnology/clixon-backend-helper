# Clixon Backend Helper Vade Mecum

What does Vade Mecum mean?  Well, it's Latin, sort of meaning "as we
walk" or "as we go".  It's used for explainations that walk a user
through something.  Since this is a a fairly complex item, we will
walk through a basic things.

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

In that directory, you can run `meson build`, `meson compile -c build`,
then `sudo meson install -c build`.  This assumes you have already installed
clixon and clixon_beh in /usr/local, it should install in /usr/local, too.

Then you can start clixon with:
```
sudo LINUX_SYSTEM_SYSBASE=/home/cminyard/tmp/clixon \
  clixon_backend -f /usr/local/etc/clixon/chronyd-server.xml -s startup -F -l e
```
This will start with the startup database, which is fine.  You will notice
that it tries to fetch some system\_only data, we will talk about that later.

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

## Source of Truth
