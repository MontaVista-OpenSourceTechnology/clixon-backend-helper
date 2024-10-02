# Clixon back end helper linux-system impementation

  * [Content](#content)
  * [Compile and run](#compile)
  * [Using the CLI](#using-the-cli)
  * [Netconf](#netconf)	
  * [Restconf](#restconf)
  * [Next steps](#next-steps)
  
## Content

This directory contains a Linux implementation of the ietf-system,
without RADIUS support, with extensions for Linux.

Before you start,
* Make [group setup](https://github.com/clicon/clixon/blob/master/doc/FAQ.md#do-i-need-to-setup-anything)

```
    meson build
    meson install -C build
```
Start backend in the background:
```
    sudo clixon_backend -f /usr/local/etc/clixon/linux-system.xml -s startup
```

Start cli:
```
    clixon_cli -f /usr/local/etc/clixon/linux-system.xml
```

## Using the CLI


## Netconf


## Restconf


## Notes

### Restconf datastore config 

You can use the config of restconf in the startup datastore as an alternative:
```
    sudo clixon_backend -f /usr/local/etc/clixon/linux-system.xml -s startup
```

### Installdirs

See meson configuration for setting the various directories.
