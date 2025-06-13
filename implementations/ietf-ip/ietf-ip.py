#
# ***** BEGIN LICENSE BLOCK *****
#
# Copyright (C) 2024 MontaVista Software, LLC <source@mvista.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Alternatively, the contents of this file may be used under the terms of
# the GNU General Public License Version 3 or later (the "GPL"),
# in which case the provisions of the GPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of the GPL, and not to allow others to
# use your version of this file under the terms of Apache License version 2,
# indicate your decision by deleting the provisions above and replace them with
# the notice and other provisions required by the GPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the Apache License version 2 or the GPL.
#
# ***** END LICENSE BLOCK *****
#

# This is an implemetation of ietf-ip (on top of ietf-interfaces).

import os
import os.path
import shlex
import json
import clixon_beh
import clixon_beh.transaction_framework as tf

ipcmds = ("/usr/bin/ip", "/usr/sbin/ip")
ipcmd = None
for i in ipcmds:
    if os.path.exists(i):
        ipcmd = i
        break
    pass
if ipcmd is None:
    raise Exception("ip command is not present")

is_if_mib = clixon_beh.is_feature_set("ietf-interfaces", "if-mib")

IETF_INTERFACES_NAMESPACE = "urn:ietf:params:xml:ns:yang:ietf-interfaces"
IETF_IP_NAMESPACE = "urn:ietf:params:xml:ns:yang:ietf-ip"

# We create the main map first because it's used by everything else.
ietfip = tf.YangElemMap(None, "/")

class MapValue(tf.YangElemValueOnly):
    """Pull the given keyval from the value mapping."""
    def __init__(self, name, keyval, isconfig=True, maxint=None):
        self.keyval = keyval
        self.maxint = maxint
        super().__init__(name, tf.YangType.LEAF, isconfig=isconfig)
        return

    def getvalue(self, data, vdata=None):
        if self.keyval in vdata:
            rv = vdata[self.keyval]
            if self.maxint is not None:
                rv = int(rv)
                if rv > self.maxint:
                    rv = self.maxint
                    pass
                rv = str(rv)
                pass
            return rv
        return ""
    pass

class Map2Value(tf.YangElemValueOnly):
    """Pull the given keyval from the value mapping."""
    def __init__(self, name, keyval1, keyval2, isconfig=True):
        self.keyval1 = keyval1
        self.keyval2 = keyval2
        super().__init__(name, tf.YangType.LEAF, isconfig=isconfig)
        return

    def getvalue(self, data, vdata=None):
        if self.keyval1 in vdata:
            if self.keyval2 in vdata[self.keyval1]:
                return vdata[self.keyval1][self.keyval2]
            pass
        return ""
    pass

class ErrorValue(tf.YangElemValueOnly):
    """Pull the given all _error values from the value mapping."""
    def __init__(self, name, keyval = None, isconfig=True):
        self.keyval = keyval
        super().__init__(name, tf.YangType.LEAF, isconfig=isconfig)
        return

    def getvalue(self, data, vdata=None):
        if self.keyval is not None:
            vdata = vdata[self.keyval]
            pass
        count = 0
        for i in vdata:
            if i.endswith("_error"):
                count += int(vdata[i])
                pass
            pass
        return str(count)

    pass

class MapChild(tf.YangElemValueOnly):
    def __init__(self, name, mapval, children=None, validate_all=True,
                 isconfig=True):
        self.mapval = mapval
        super().__init__(name, tf.YangType.CONTAINER, children,
                         validate_all=validate_all, isconfig=isconfig)
        return

    def getxml(self, data, path, namespace=None, indexname=None,
               index=None, vdata=None):
        vdata = vdata[self.mapval]
        return super().getxml(data, path,
                              namespace=namespace, indexname=indexname,
                              index=index, vdata=vdata)

    def getvalue(self, data, vdata=None):
        vdata = vdata[self.mapval]
        return super().getvalue(data, vdata=vdata)

    pass

# /interfaces/interface/ipv4/neighbor/origin
# /interfaces/interface/ipv6/neighbor/origin
# /interfaces-state/interface/ipv4/neighbor/origin
# /interfaces-state/interface/ipv6/neighbor/origin
class NeighOrigin(tf.YangElemValueOnly):
    """Get the origin value of the address."""

    def getvalue(self, data, vdata=None):
        if "PERMANENT" in vdata["state"]:
            return "static"
        return "dynamic"

    pass

# /interfaces/interface/ipv6/enabled
class InterfaceIPv6Enabled(tf.YangElemValueOnly):
    """Get if the interface is enabled or not."""
    def getvalue(self, data, vdata=None):
        # If it's there it's enabled.
        return "true"
    pass

# /interfaces/interface/ipv6/forwarding
# /interfaces-state/interface/ipv6/forwarding
class InterfaceIPv6Forwarding(tf.YangElemValueOnly):
    """Get if the interface has forwarding enabled."""
    def getvalue(self, data, vdata=None):
        fname = "/proc/sys/net/ipv6/conf/" + vdata["ifname"] + "/forwarding"
        v = ""
        with open(fname, "r") as f:
            v = f.read().strip()
            pass
        if v == "1":
            return "true"
        return "false"
    pass

# /interfaces/interface/ipv6/dup-addr-detect-transmits
class InterfaceIPv6DADT(tf.YangElemValueOnly):
    """Get if the interface detect duplicate addresses."""
    def getvalue(self, data, vdata=None):
        # FIXME - find out how to get this.
        return "1"
    pass

# /interfaces/interface/ipv6/neighbor/state
# /interfaces-state/interface/ipv6/neighbor/state
class IPV6NeighState(tf.YangElemValueOnly):
    """Get the state value of the address."""
    def getvalue(self, data, vdata=None):
        if "INCOMPLETE" in vdata["state"]:
            return "incomplete"
        if "REACHABLE" in vdata["state"]:
            return "reachable"
        if "STALE" in vdata["state"]:
            return "stale"
        if "DELAY" in vdata["state"]:
            return "delay"
        if "PROBE" in vdata["state"]:
            return "probe"
        return "stale" # FIXME - is there a better default?

    pass

# /interfaces/interface/ipv6/neighbor/is-router
# /interfaces-state/interface/ipv6/neighbor/is-router
class IPV6NeighRouter(tf.YangElemValueOnly):
    """Get the state value of the address.  This returns raw XML,
    set wrapxml and xmlprocvalue to false"""
    def getvalue(self, data, vdata=None):
        if "router" in vdata:
            return "<is-router/>"
        return ""

    pass

# /interfaces/interface/ipv6/neighbor
class IPV6Neigh(tf.YangElemValueOnly):
    def get_neighs(self, vdata):
        return self.program_output([ipcmd, "-6", "-j", "neigh", "show", "dev",
                                    vdata["ifname"]],
                                   decoder = lambda x : json.loads(x))

    def fetch_index(self, indexname, index, vdata):
        neighs = self.get_neighs(vdata)
        for i in neighs:
            if i["dst"] == index:
                return i
            pass
        return None

    def fetch_full_index(self, vdata):
        return self.get_neighs(vdata)

    pass

# /interfaces/interface/ipv6/address/origin
# /interfaces-state/interface/ipv6/address/origin
class IPV6Origin(tf.YangElemValueOnly):
    """Get the origin value of the address."""
    def getvalue(self, data, vdata=None):
        if "dynamic" in vdata and vdata["dynamic"] == "true":
            return "random"
        if vdata["local"].startswith("fc") or vdata["local"].startswith("fd"):
            return "link-layer"
        return "static"

    pass

# /interfaces/interface/ipv6/address/status
# /interfaces-state/interface/ipv6/address/status
class IPV6Status(tf.YangElemValueOnly):
    """Get the origin value of the address."""
    def getvalue(self, data, vdata=None):
        if "dadfailed" in vdata and vdata["datafailed"] == "true":
            return "duplicate"
        if "optimistic" in vdata and vdata["optimistic"] == "true":
            return "optimistic"
        if "tenative" in vdata and vdata["tenative"] == "true":
            return "tenative"
        if "deprecated" in vdata and vdata["deprecated"] == "true":
            return "deprecated"
        if int(vdata["preferred_life_time"]) > 0:
            return "preferred"
        return "unknown"

    pass

# /interfaces/interface/ipv6/address
class IPV6Address(tf.YangElemValueOnly):
    def fetch_index(self, indexname, index, vdata):
        for i in vdata["addr_info"]:
            if i["ip"] == index:
                return i
            pass
        return None

    def fetch_full_index(self, vdata):
        rv = []
        for i in vdata["addr_info"]:
            if i["family"] == "inet6":
                rv.append(i)
                pass
            pass
        return rv

    pass

# /interfaces/interface/ipv6/autoconf/create-glboal-addresses
class InterfaceIPv6AutoconfCGA(tf.YangElemValueOnly):
    """Get if the interface creates a global IPV6 address."""
    def getvalue(self, data, vdata=None):
        # FIXME - how to get this?
        return "true"
    pass

# /interfaces/interface/ipv4/enabled
class InterfaceIPv4Enabled(tf.YangElemValueOnly):
    """Get if the interface is enabled or not."""
    def getvalue(self, data, vdata=None):
        # If it's there it's enabled.
        return "true"
    pass

# /interfaces/interface/ipv4/forwarding
# /interfaces-state/interface/ipv4/forwarding
class InterfaceIPv4Forwarding(tf.YangElemValueOnly):
    """Get if the interface has forwarding enabled."""
    def getvalue(self, data, vdata=None):
        v = ""
        with open("/proc/sys/net/ipv4/ip_forward", "r") as f:
            v = f.read().strip()
            pass
        if v == "1":
            return "true"
        return "false"
    pass

# /interfaces/interface/ipv4/address/origin
# /interfaces-state/interface/ipv4/address/origin
class IPV4Origin(tf.YangElemValueOnly):
    """Get the origin value of the address."""
    def getvalue(self, data, vdata=None):
        if "dynamic" in vdata and vdata["dynamic"] == "true":
            return "dhcp"
        if vdata["local"].startswith("169.254."):
            return "random"
        return "static"

    pass

# /interfaces/interface/ipv4/address
class IPV4Address(tf.YangElemValueOnly):
    def fetch_index(self, indexname, index, vdata):
        for i in vdata["addr_info"]:
            if i["ip"] == index:
                return i
            pass
        return None

    def fetch_full_index(self, vdata):
        rv = []
        for i in vdata["addr_info"]:
            if i["family"] == "inet":
                rv.append(i)
                pass
            pass
        return rv

    pass

class IPV4Neigh(tf.YangElemValueOnly):
    def get_neighs(self, vdata):
        return self.program_output([ipcmd, "-4", "-j", "neigh", "show", "dev",
                                    vdata["ifname"]],
                                   decoder = lambda x : json.loads(x))

    def fetch_index(self, indexname, index, vdata):
        neighs = self.get_neighs(vdata)
        for i in neighs:
            if i["dst"] == index:
                return i
            pass
        return None

    def fetch_full_index(self, vdata):
        return self.get_neighs(vdata)

    pass

# Convert beteen linux ip values and iana-if-type
link_types = {
    "loopback": "softwareLoopback",
    "ether": "ethernetCsmacd",
}

# /interfaces/interface/type
class InterfaceType(tf.YangElem):
    """Get the iana-if-type value of the link_type."""

    def validate_add(self, data, xml):
        self.validate(data, NULL, xml)
        return

    def validate_del(self, data, xml):
        self.validate(data, NULL, xml)
        return

    def validate(self, data, origxml, newxml):
        raise tf.RPCError("application", "invalid-value", "error",
                          "Setting interface type not allowed")

    def getvalue(self, data, vdata=None):
        v = vdata["link_type"]
        ns = "urn:ietf:params:xml:ns:yang:iana-if-type"
        if v == "none":
            v = "other"
            # It might be a tunnel.
            if vdata["ifname"].startswith("tun"):
                v = "tunnel"
                pass
            pass
        elif v in link_types:
            v = link_types[v]
        else:
            v = "other"
            pass
        return ("<%s xmlns:ianaift=\"%s\">ianaift:%s</%s>"
                % (self.name, ns, tf.xmlescape(v), self.name))
    pass

# /interfaces/interface/admin-status
class InterfaceAdminStatus(tf.YangElemValueOnly):
    """Get the admin-status value of the interface."""
    def getvalue(self, data, vdata=None):
        if "UP" in vdata["flags"]:
            return "up"
        # FIXME - do we need to add anything else?
        return "down"
    pass

# /interfaces/interface/oper-status
# /interfaces-state/interface/oper-status
class InterfaceOperStatus(tf.YangElemValueOnly):
    """Get the oper-status value of the interface."""
    def getvalue(self, data, vdata=None):
        # FIXME - "operstate" doesn't seem to always be correct.  Just use
        # flags.
        if "UP" in vdata["flags"]:
            return "up"
        # FIXME - do we need to add anything else?
        return "down"
    pass

# /interfaces/interface/enabled
class InterfaceEnabled(tf.YangElemValueOnly):
    """Get if the interface is enabled or not."""
    def getvalue(self, data, vdata=None):
        if "UP" in vdata["flags"]:
            return "true"
        return "false"
    pass

# /interfaces/interface
class Interface(tf.YangElemValueOnly):
    def getinterfaces(self):
        return self.program_output([ipcmd, "-p", "-s", "-s", "-j", "addr"],
                                   decoder = lambda x : json.loads(x))

    def fetch_index(self, indexname, index, vdata):
        ifs = self.getinterfaces()
        for i in ifs:
            if i["ifname"] == index:
                return i
            pass
        return None

    def fetch_full_index(self, vdata):
        return self.getinterfaces()

    pass

# /interfaces[-state]/interface/type
class InterfaceStateType(tf.YangElemValueOnly):
    """Get the iana-if-type value of the link_type."""
    def getvalue(self, data, vdata=None):
        v = vdata["link_type"]
        ns = "urn:ietf:params:xml:ns:yang:iana-if-type"
        if v == "none":
            v = "other"
            # It might be a tunnel.
            if vdata["ifname"].startswith("tun"):
                v = "tunnel"
                pass
            pass
        elif v in link_types:
            v = link_types[v]
        else:
            v = "other"
            pass
        return ("<%s xmlns:ianaift=\"%s\">ianaift:%s</%s>"
                % (self.name, ns, tf.xmlescape(v), self.name))

    pass

# /interfaces[-state]/interface/admin-status
class InterfaceStateAdminStatus(tf.YangElemValueOnly):
    """Get the admin-status value of the interface."""
    def getvalue(self, data, vdata=None):
        if "UP" in vdata["flags"]:
            return "up"
        # FIXME - do we need to add anything else?
        return "down"
    pass

# /interfaces[-state]/interface
class StateInterface(tf.YangElemValueOnly):
    def getinterfaces(self):
        return self.program_output([ipcmd, "-p", "-s", "-s", "-j", "addr"],
                                   decoder = lambda x : json.loads(x))

    def fetch_index(self, indexname, index, vdata):
        ifs = self.getinterfaces()
        for i in ifs:
            if i["ifname"] == index:
                return i
            pass
        return None

    def fetch_full_index(self, vdata):
        return self.getinterfaces()

    pass

# Create the maps for /interfaces
s = ietfip
s.add_map("/", tf.YangElem("interfaces", tf.YangType.CONTAINER,
                           namespace=IETF_INTERFACES_NAMESPACE))
s.add_map("/interfaces",
          StateInterface("interface", tf.YangType.LIST))

s.add_map("/interfaces/interface",
          tf.YangElem("ipv4", tf.YangType.CONTAINER,
                      namespace=IETF_IP_NAMESPACE))
s.add_leaf("/interfaces/interface/ipv4",
           InterfaceIPv4Enabled("enabled", tf.YangType.LEAF))
s.add_leaf("/interfaces/interface/ipv4",
           InterfaceIPv4Forwarding("forwarding", tf.YangType.LEAF))
s.add_leaf("/interfaces/interface/ipv4",
           MapValue("mtu", "mtu", maxint=65535))
s.add_map("/interfaces/interface/ipv4",
          IPV4Address("address", tf.YangType.LIST))
s.add_leaf("/interfaces/interface/ipv4/address",
           MapValue("ip", "local"))
s.add_map("/interfaces/interface/ipv4/address",
           tf.YangElemChoice("subnet"))
s.add_leaf("/interfaces/interface/ipv4/address/subnet",
           MapValue("prefix-length", "prefixlen"))
s.add_leaf("/interfaces/interface/ipv4/address",
           IPV4Origin("origin", tf.YangType.LEAF, isconfig=False))
s.add_map("/interfaces/interface/ipv4",
          IPV4Neigh("neighbor", tf.YangType.LIST))
s.add_leaf("/interfaces/interface/ipv4/neighbor",
          MapValue("ip", "dst"))
s.add_leaf("/interfaces/interface/ipv4/neighbor",
          MapValue("link-layer-address", "lladdr"))
s.add_leaf("/interfaces/interface/ipv4/neighbor",
          NeighOrigin("origin", tf.YangType.LEAF, isconfig=False))

s.add_map("/interfaces/interface",
          tf.YangElem("ipv6", tf.YangType.CONTAINER,
                      namespace=IETF_IP_NAMESPACE))
s.add_leaf("/interfaces/interface/ipv6",
           InterfaceIPv6Enabled("enabled", tf.YangType.LEAF))
s.add_leaf("/interfaces/interface/ipv6",
           InterfaceIPv6Forwarding("forwarding", tf.YangType.LEAF))
s.add_leaf("/interfaces/interface/ipv6",
           MapValue("mtu", "mtu", maxint=65535))
s.add_map("/interfaces/interface/ipv6",
          IPV6Address("address", tf.YangType.LIST))
s.add_leaf("/interfaces/interface/ipv6/address",
           MapValue("ip", "local"))
s.add_leaf("/interfaces/interface/ipv6/address",
           MapValue("prefix-length", "prefixlen"))
s.add_leaf("/interfaces/interface/ipv6/address",
           IPV6Origin("origin", tf.YangType.LEAF, isconfig=False))
s.add_leaf("/interfaces/interface/ipv6/address",
           IPV6Status("status", tf.YangType.LEAF, isconfig=False))

s.add_leaf("/interfaces/interface/ipv6",
           InterfaceIPv6DADT("dup-addr-detect-transmits", tf.YangType.LEAF))

s.add_map("/interfaces/interface/ipv6",
          IPV6Neigh("neighbor", tf.YangType.LIST))
s.add_leaf("/interfaces/interface/ipv6/neighbor",
           MapValue("ip", "dst"))
s.add_leaf("/interfaces/interface/ipv6/neighbor",
           MapValue("link-layer-address", "lladdr"))
s.add_leaf("/interfaces/interface/ipv6/neighbor",
           NeighOrigin("origin", tf.YangType.LEAF, isconfig=False))
s.add_leaf("/interfaces/interface/ipv6/neighbor",
           IPV6NeighRouter("is-router",
                           tf.YangType.LEAF, isconfig=False,
                           wrapxml = False, xmlprocvalue = False))
s.add_leaf("/interfaces/interface/ipv6/neighbor",
           IPV6NeighState("state", tf.YangType.LEAF, isconfig=False))

s.add_map("/interfaces/interface/ipv6",
          tf.YangElem("autoconf", tf.YangType.CONTAINER))
s.add_leaf("/interfaces/interface/ipv6/autoconf",
           InterfaceIPv6AutoconfCGA("create-global-addresses",
                                    tf.YangType.LEAF))

class DiscontinuityTime(tf.YangElemValueOnly):
    # FIXME - This just returns boot time, not sure what else to do.
    def getvalue(self, data, vdata=None):
        date = self.program_output(["/bin/date", "--rfc-3339=seconds"]).strip()
        date = date.split(" ")
        if len(date) < 2:
            raise Exception("Invalid date output: " + str(date))
        date = date[0] + "T" + date[1]

        bdate = shlex.split(self.program_output(["uptime","-s"]))
        if len(bdate) < 2:
            raise Exception("Invalid uptime -s output: " + str(bdate))
        # Steal the time zone from the main date.
        if "+" in date:
            zone = "+" + date.rsplit("+", 1)[1]
        else:
            zone = "-" + date.rsplit("-", 1)[1]
            pass
        if len(zone) < 2:
            raise Exception("Invalid zone in date: " + date)
        bdate = bdate[0] + "T" + bdate[1] + zone

        return bdate

s.add_map("/interfaces/interface",
          MapChild("statistics", "stats64", isconfig=False))
s.add_leaf("/interfaces/interface/statistics",
           DiscontinuityTime("discontinuity-time", tf.YangType.LEAF))
s.add_leaf("/interfaces/interface/statistics",
           Map2Value("in-octets", "rx", "bytes"))
s.add_leaf("/interfaces/interface/statistics",
           Map2Value("in-unicast-pkts", "rx", "bytes"))
s.add_leaf("/interfaces/interface/statistics",
           tf.YangElemValueOnlyUnimpl("in-broadcast-pkts", tf.YangType.LEAF))
s.add_leaf("/interfaces/interface/statistics",
           Map2Value("in-multicast-pkts", "rx", "multicast"))
s.add_leaf("/interfaces/interface/statistics",
           Map2Value("in-discards", "rx", "dropped"))
s.add_leaf("/interfaces/interface/statistics",
           ErrorValue("in-errors", keyval = "rx"))
s.add_leaf("/interfaces/interface/statistics",
           tf.YangElemValueOnlyUnimpl("in-unknown-protos", tf.YangType.LEAF))
s.add_leaf("/interfaces/interface/statistics",
           Map2Value("out-octets", "tx", "bytes"))
s.add_leaf("/interfaces/interface/statistics",
           Map2Value("out-unicast-pkts", "tx", "bytes"))
s.add_leaf("/interfaces/interface/statistics",
           tf.YangElemValueOnlyUnimpl("out-broadcast-pkts", tf.YangType.LEAF))
s.add_leaf("/interfaces/interface/statistics",
           Map2Value("out-multicast-pkts", "tx", "multicast"))
s.add_leaf("/interfaces/interface/statistics",
           Map2Value("out-discards", "tx", "dropped"))
s.add_leaf("/interfaces/interface/statistics",
           ErrorValue("out-errors", keyval = "tx"))

s.add_leaf("/interfaces/interface",
           MapValue("name", "ifname"))
s.add_leaf("/interfaces/interface",
           tf.YangElemConfigOnly("description"))
s.add_leaf("/interfaces/interface",
           InterfaceType("type", tf.YangType.LEAF,
                         xmlprocvalue=False, wrapxml=False))
if is_if_mib:
    s.add_leaf("/interfaces/interface",
               InterfaceAdminStatus("admin-status", tf.YangType.LEAF))
    pass
s.add_leaf("/interfaces/interface",
           InterfaceOperStatus("oper-status", tf.YangType.LEAF,
                               isconfig=False))
if is_if_mib:
    s.add_leaf("/interfaces/interface",
               MapValue("if-index", "ifindex", isconfig=False))
s.add_leaf("/interfaces/interface",
           MapValue("phys-address", "address", isconfig=False))
# FIXME - how to get speed?
s.add_leaf("/interfaces/interface",
           tf.YangElemValueOnlyUnimpl("speed", tf.YangType.LEAF))
# Also missing: last-change, higher-layer-if, lower-layer-if.
s.add_leaf("/interfaces/interface",
           tf.YangElemValueOnlyUnimpl("last-change", tf.YangType.LEAF))
s.add_leaf("/interfaces/interface",
           tf.YangElemValueOnlyUnimpl("higher-layer-if", tf.YangType.LEAFLIST))
s.add_leaf("/interfaces/interface",
           tf.YangElemValueOnlyUnimpl("lower-layer-if", tf.YangType.LEAFLIST))

s.add_leaf("/interfaces/interface",
           InterfaceEnabled("enabled", tf.YangType.LEAF))

# Set up /interfaces-state here.  We have to create the maps first
# because we have to create them in forward order so we can get the
# parent dependencies right, then we can add all the elements to each
# map.
s.add_map("/",
          tf.YangElem("interfaces-state", tf.YangType.CONTAINER,
                      namespace=IETF_INTERFACES_NAMESPACE,
                      isconfig=False))
s.add_map("/interfaces-state",
          StateInterface("interface", tf.YangType.LIST))
s.add_leaf("/interfaces-state/interface",
           MapValue("name", "ifname"))
s.add_leaf("/interfaces-state/interface",
           InterfaceStateType("type", tf.YangType.LEAF,
                              xmlprocvalue=False, wrapxml=False))
if is_if_mib:
    s.add_leaf("/interfaces-state/interface",
               InterfaceStateAdminStatus("admin-status", tf.YangType.LEAF))
s.add_leaf("/interfaces-state/interface",
           InterfaceOperStatus("oper-status", tf.YangType.LEAF))
if is_if_mib:
    s.add_leaf("/interfaces-state/interface",
               MapValue("if-index", "ifindex"))
s.add_leaf("/interfaces-state/interface",
           MapValue("phys-address", "address"))
# FIXME - how to get speed?
s.add_leaf("/interfaces-state/interface",
           tf.YangElemValueOnlyUnimpl("speed", tf.YangType.LEAF))
# Also missing: last-change, higher-layer-if, lower-layer-if.
s.add_leaf("/interfaces-state/interface",
           tf.YangElemValueOnlyUnimpl("last-change", tf.YangType.LEAF))
s.add_leaf("/interfaces-state/interface",
           tf.YangElemValueOnlyUnimpl("higher-layer-if", tf.YangType.LEAFLIST))
s.add_leaf("/interfaces-state/interface",
           tf.YangElemValueOnlyUnimpl("lower-layer-if", tf.YangType.LEAFLIST))

s.add_map("/interfaces-state/interface",
          tf.YangElemValueOnly("ipv4", tf.YangType.CONTAINER,
                               namespace=IETF_IP_NAMESPACE))
s.add_leaf("/interfaces-state/interface/ipv4",
           InterfaceIPv4Forwarding("forwarding", tf.YangType.LEAF))
s.add_leaf("/interfaces-state/interface/ipv4",
           MapValue("mtu", "mtu", maxint=65535))
s.add_map("/interfaces-state/interface/ipv4",
          IPV4Neigh("neighbor", tf.YangType.LIST))
s.add_leaf("/interfaces-state/interface/ipv4/neighbor",
           MapValue("ip", "dst"))
s.add_leaf("/interfaces-state/interface/ipv4/neighbor",
           MapValue("link-layer-address", "lladdr"))
s.add_leaf("/interfaces-state/interface/ipv4/neighbor",
           NeighOrigin("origin", tf.YangType.LEAF))
s.add_map("/interfaces-state/interface/ipv4",
          IPV4Address("address", tf.YangType.LIST))
s.add_leaf("/interfaces-state/interface/ipv4/address",
           MapValue("ip", "local"))
s.add_map("/interfaces-state/interface/ipv4/address",
           tf.YangElemChoice("subnet"))
s.add_leaf("/interfaces-state/interface/ipv4/address/subnet",
           MapValue("prefix-length", "prefixlen"))
s.add_leaf("/interfaces-state/interface/ipv4/address",
           IPV4Origin("origin", tf.YangType.LEAF))

s.add_map("/interfaces-state/interface",
          tf.YangElemValueOnly("ipv6", tf.YangType.CONTAINER,
                               namespace=IETF_IP_NAMESPACE))
s.add_leaf("/interfaces-state/interface/ipv6",
           InterfaceIPv6Forwarding("forwarding", tf.YangType.LEAF))
s.add_leaf("/interfaces-state/interface/ipv6",
           MapValue("mtu", "mtu", maxint=65535))
s.add_map("/interfaces-state/interface/ipv6",
          IPV6Neigh("neighbor", tf.YangType.LIST))
s.add_leaf("/interfaces-state/interface/ipv6/neighbor",
           MapValue("ip", "dst"))
s.add_leaf("/interfaces-state/interface/ipv6/neighbor",
           MapValue("link-layer-address", "lladdr"))
s.add_leaf("/interfaces-state/interface/ipv6/neighbor",
           NeighOrigin("origin", tf.YangType.LEAF))
s.add_leaf("/interfaces-state/interface/ipv6/neighbor",
           IPV6NeighRouter("is-router", tf.YangType.LEAF,
                           wrapxml = False, xmlprocvalue = False))
s.add_leaf("/interfaces-state/interface/ipv6/neighbor",
           IPV6NeighState("state", tf.YangType.LEAF))
s.add_map("/interfaces-state/interface/ipv6",
          IPV6Address("address", tf.YangType.LIST))
s.add_leaf("/interfaces-state/interface/ipv6/address",
           MapValue("ip", "local"))
s.add_leaf("/interfaces-state/interface/ipv6/address",
           MapValue("prefix-length", "prefixlen"))
s.add_leaf("/interfaces-state/interface/ipv6/address",
           IPV6Origin("origin", tf.YangType.LEAF))
s.add_leaf("/interfaces-state/interface/ipv6/address",
           IPV6Status("status", tf.YangType.LEAF))

s.add_map("/interfaces-state/interface",
          MapChild("statistics", "stats64"))
s.add_leaf("/interfaces-state/interface/statistics",
           DiscontinuityTime("discontinuity-time", tf.YangType.LEAF))
s.add_leaf("/interfaces-state/interface/statistics",
           Map2Value("in-octets", "rx", "bytes"))
s.add_leaf("/interfaces-state/interface/statistics",
           Map2Value("in-unicast-pkts", "rx", "bytes"))
s.add_leaf("/interfaces-state/interface/statistics",
           tf.YangElemValueOnlyUnimpl("in-broadcast-pkts", tf.YangType.LEAF))
s.add_leaf("/interfaces-state/interface/statistics",
           Map2Value("in-multicast-pkts", "rx", "multicast"))
s.add_leaf("/interfaces-state/interface/statistics",
           Map2Value("in-discards", "rx", "dropped"))
s.add_leaf("/interfaces-state/interface/statistics",
           ErrorValue("in-errors", keyval = "rx"))
s.add_leaf("/interfaces-state/interface/statistics",
           tf.YangElemValueOnlyUnimpl("in-unknown-protos", tf.YangType.LEAF))
s.add_leaf("/interfaces-state/interface/statistics",
           Map2Value("out-octets", "tx", "bytes"))
s.add_leaf("/interfaces-state/interface/statistics",
           Map2Value("out-unicast-pkts", "tx", "bytes"))
s.add_leaf("/interfaces-state/interface/statistics",
           tf.YangElemValueOnlyUnimpl("out-broadcast-pkts", tf.YangType.LEAF))
s.add_leaf("/interfaces-state/interface/statistics",
           Map2Value("out-multicast-pkts", "tx", "multicast"))
s.add_leaf("/interfaces-state/interface/statistics",
           Map2Value("out-discards", "tx", "dropped"))
s.add_leaf("/interfaces-state/interface/statistics",
           ErrorValue("out-errors", keyval = "tx"))

class Handler(tf.TopElemHandler, tf.ProgOut):
    def exit(self):
        self.p = None # Break circular dependency
        return 0

    def begin(self, t):
        rv = super().begin(t)
        if rv < 0:
            return rv
        data = t.get_userdata()
        return 0

    def end(self, t):
        data = t.get_userdata()
        return 0

    def abort(self, t):
        data = t.get_userdata()
        return 0

    def system_only(self, nsc, xpath):
        #print("***System_only: %s %s" % (xpath, str(nsc)))
        if xpath == "/":
            xpath = "/interfaces"
            pass
        rv = super().statedata(nsc, xpath, tf.GetData(False))
        if False:
            print("Y: " + str(rv))
            pass
        return rv

    def start(self):
        if not tf.check_topmap_against_yang(self, "data"):
            return -1
        return 0

    pass

handler = Handler("ietf-interfaces", ietfip)
handler.p = clixon_beh.add_plugin("ietf-ip", IETF_INTERFACES_NAMESPACE, handler)
