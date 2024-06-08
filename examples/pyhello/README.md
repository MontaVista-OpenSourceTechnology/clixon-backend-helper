# Clixon back end helper hello world example

  * [Content](#content)
  * [Compile and run](#compile)
  * [Using the CLI](#using-the-cli)
  * [Netconf](#netconf)	
  * [Restconf](#restconf)
  * [Next steps](#next-steps)
  
## Content

This directory contains a simple Clixon hello world host example. It contains the following files:
* `hello_beh.xml`: the XML configuration file
* `clixon-hello-beh@....yang`: the YANG spec
* `hello_beh_cli.cli`: the CLIgen spec
* `startup_db`: The startup datastore containing restconf port configuration
* `meson.build`: meson build file
* `clixon_beh.xml`: The config file for the loadable modules for the backend helper

## Compile and run

Before you start,
* Make [group setup](https://github.com/clicon/clixon/blob/master/doc/FAQ.md#do-i-need-to-setup-anything)

```
    meson build
    meson install -C build
```
Start backend in the background:
```
    sudo clixon_backend -f /usr/local/etc/clixon/pyhello_beh.xml -s startup
```

Start cli:
```
    clixon_cli -f /usr/local/etc/clixon/pyhello.xml
```

## Using the CLI

The example CLI allows you to modify and view the data model using `set`, `delete` and `show` via generated code.

The following example shows how to add a very simple configuration `hello world` using the generated CLI. The config is added to the candidate database, shown, committed to running, and then deleted.
```
   $ clixon_cli -f /usr/local/etc/clixon/pyhello_beh.xml
   cli> set <?>
     hello                 
   cli> set hello to world 
   cli> show configuration 
   hello world;
   cli> commit 
   cli> delete <?>
     all                   Delete whole candidate configuration
     hello                 
   cli> delete hello 
   cli> show configuration 
   cli> commit 
   cli> quit
   $
```

## Netconf

Clixon also provides a Netconf interface. The following example starts a netconf client form the shell, adds the hello world config, commits it, and shows it:
```
   $ clixon_netconf -qf /usr/local/etc/pyhello_beh.xml
   <rpc message-id="42" xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"><edit-config><target><candidate/></target><config><hello xmlns="urn:example:pyhello_beh"><world/></hello></config></edit-config></rpc>]]>]]>
   <rpc-reply><ok/></rpc-reply>]]>]]>
   <rpc><commit/></rpc>]]>]]>
   <rpc-reply><ok/></rpc-reply>]]>]]>
   <rpc><get-config><source><running/></source></get-config></rpc>]]>]]>
   <rpc-reply><data><hello xmlns="urn:example:pyhello_beh"><world/></hello></data></rpc-reply>]]>]]>
   $
```

## Restconf

Clixon also provides a Restconf interface. See [documentation on RESTCONF](https://clixon-docs.readthedocs.io/en/latest/restconf.html).

The example startup datastore contains config for a pre-configured restconf server listening on port 80. Edit `startup_db` if you want to change options or start the backend without it using `-s init` if you dont want restconf.

Send restconf commands (using Curl):
```
   $ curl -X POST http://localhost/restconf/data -H "Content-Type: application/yang-data+json" -d '{"clixon-pyhello-beh:hello":{"to":"country"}}'
   $ curl -X GET http://localhost/restconf/data/clixon-pyhello-beh:hello
   {"clixon-pyhello-beh:hello":{"to":"country"}}
   $ curl -X PUT http://localhost/restconf/data/clixon-pyhello-beh:hello/to -H "Content-Type: application/yang-data+json" -d '{"clixon-pyhello-beh:to":"city"}'
```

## Notes

### Restconf datastore config 

You can use the config of restconf in the startup datastore as an alternative:
```
    sudo clixon_backend -f /usr/local/etc/clixon/pyhello_beh.xml -s startup
```

### Installdirs

See meson configuration for setting the various directories.