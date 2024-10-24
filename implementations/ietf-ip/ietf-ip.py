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
import shlex
import json
import clixon_beh
import clixon_beh.transaction_framework as tf

ipcmd = "/usr/bin/ip"

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
    def __init__(self, name, mapval, children, validate_all=True,
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
            # It might be a tunnel.
            if vdata["ifname"].startswith("tun"):
                v = "tunnel"
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
        if not is_if_mib:
            return ""
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

# Create the maps for /interfaces
interfaces = tf.YangElemMap(ietfip, "/interfaces")
interfaces_interface = tf.YangElemMap(
    interfaces, "/interfaces/interface")
interfaces_interface_statistics = tf.YangElemMap(
    interfaces_interface,
    "interfaces/interface/statistics")
interfaces_interface_ipv4 = tf.YangElemMap(
    interfaces_interface,
    "/interfaces/interface/ipv4")
interfaces_interface_ipv4_neighbor = tf.YangElemMap(
    interfaces_interface_ipv4,
    "/interfaces/interface/ipv6/neighbor/origin")
interfaces_interface_ipv4_children = tf.YangElemMap(
    interfaces_interface_ipv4,
    "/interfaces/interface/ipv4/children")
interfaces_interface_ipv6 = tf.YangElemMap(
    interfaces_interface,
    "/interfaces/interface/ipv6")
interfaces_interface_ipv6_children = tf.YangElemMap(
    interfaces_interface_ipv6,
    "/interfaces/interface/ipv6/children")
interfaces_interface_ipv6_neighbor = tf.YangElemMap(
    interfaces_interface_ipv6,
    "/interfaces/interface/ipv6/neighbor")

m = interfaces_interface_ipv6_neighbor
m.add(MapValue("ip", "dst"))
m.add(MapValue("link-layer-address", "lladdr"))
m.add(NeighOrigin("origin", tf.YangType.LEAF, isconfig=False))
# is-router
m.add(IPV6NeighState("state", tf.YangType.LEAF, isconfig=False))

m = interfaces_interface_ipv6_children
m.add(MapValue("ip", "local"))
m.add(MapValue("prefix-length", "prefixlen"))
m.add(IPV6Origin("origin", tf.YangType.LEAF, isconfig=False))
m.add(IPV6Status("status", tf.YangType.LEAF, isconfig=False))

m = interfaces_interface_ipv6
# forwarding
m.add(MapValue("mtu", "mtu", maxint=65535))
m.add(IPV6Address("address", tf.YangType.LIST,
                  interfaces_interface_ipv6_children))
m.add(IPV6Neigh("neighbor", tf.YangType.LIST,
                interfaces_interface_ipv6_neighbor))

m = interfaces_interface_ipv4_children
m.add(MapValue("ip", "local"))
m.add(MapValue("prefix-length", "prefixlen"))
m.add(IPV4Origin("origin", tf.YangType.LEAF, isconfig=False))

m = interfaces_interface_ipv4_neighbor
m.add(MapValue("ip", "dst"))
m.add(MapValue("link-layer-address", "lladdr"))
m.add(NeighOrigin("origin", tf.YangType.LEAF, isconfig=False))

m = interfaces_interface_ipv4
# enabled
# forwarding
m.add(MapValue("mtu", "mtu", maxint=65535))
m.add(IPV4Address("address", tf.YangType.LIST,
                  interfaces_interface_ipv4_children))
m.add(IPV4Neigh("neighbor", tf.YangType.LIST,
                interfaces_interface_ipv4_neighbor))

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

m = interfaces_interface_statistics
m.add(DiscontinuityTime("discontinuity-time", tf.YangType.LEAF))
m.add(Map2Value("in-octets", "rx", "bytes"))
m.add(Map2Value("in-unicast-pkts", "rx", "bytes"))
# in-broadcast-pkts
m.add(Map2Value("in-multicast-pkts", "rx", "multicast"))
m.add(Map2Value("in-discards", "rx", "dropped"))
m.add(ErrorValue("in-errors", keyval = "rx"))
# in-unknown-protos
m.add(Map2Value("out-octets", "tx", "bytes"))
m.add(Map2Value("out-unicast-pkts", "tx", "bytes"))
# out-broadcast-pkts
m.add(Map2Value("out-multicast-pkts", "tx", "multicast"))
m.add(Map2Value("out-discards", "tx", "dropped"))
m.add(ErrorValue("out-errors", keyval = "tx"))

m = interfaces_interface
m.add(MapValue("name", "ifname"))
m.add(tf.YangElemConfigOnly("description"))
m.add(InterfaceType("type", tf.YangType.LEAF,
                    xmlprocvalue=False, wrapxml=False))
m.add(InterfaceAdminStatus("admin-status", tf.YangType.LEAF))
m.add(InterfaceOperStatus("oper-status", tf.YangType.LEAF,
                          isconfig=False))
m.add(MapValue("if-index", "ifindex", isconfig=False))
m.add(MapValue("phys-address", "address", isconfig=False))
# FIXME - how to get speed?
# Also missing: last-change, higher-layer-if, lower-layer-if.
m.add(MapChild("statistics", "stats64",
               interfaces_interface_statistics,
               isconfig=False))
m.add(tf.YangElem("ipv4", tf.YangType.CONTAINER,
                  interfaces_interface_ipv4,
                  namespace=IETF_IP_NAMESPACE))
m.add(tf.YangElem("ipv6", tf.YangType.CONTAINER,
                  interfaces_interface_ipv6,
                  namespace=IETF_IP_NAMESPACE))

m = interfaces
m.add(Interface("interface", tf.YangType.LIST,
                interfaces_interface))

# /interfaces-state/interface/type
class InterfaceStateType(tf.YangElemValueOnly):
    """Get the iana-if-type value of the link_type."""
    def getvalue(self, data, vdata=None):
        v = vdata["link_type"]
        ns = "urn:ietf:params:xml:ns:yang:iana-if-type"
        if v == "none":
            # It might be a tunnel.
            if vdata["ifname"].startswith("tun"):
                v = "tunnel"
            pass
        elif v in link_types:
            v = link_types[v]
        else:
            v = "other"
            pass
        return ("<%s xmlns:ianaift=\"%s\">ianaift:%s</%s>"
                % (self.name, ns, tf.xmlescape(v), self.name))

    pass

# /interfaces-state/interface/admin-status
class InterfaceStateAdminStatus(tf.YangElemValueOnly):
    """Get the admin-status value of the interface."""
    def getvalue(self, data, vdata=None):
        if "UP" in vdata["flags"]:
            return "up"
        # FIXME - do we need to add anything else?
        return "down"
    pass

# /interfaces-state/interface
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

# Set up /interfaces-state here.  We have to create the maps first
# because we have to create them in forward order so we can get the
# parent dependencies right, then we can add all the elements to each
# map.
interfacesstate = tf.YangElemMap(ietfip, "/interfaces-state")
interfacesstate_interface = tf.YangElemMap(
    interfacesstate,
    "/interfaces-state/interface")
interfacesstate_interface_statistics = tf.YangElemMap(
    interfacesstate_interface,
    "interfaces-state/interface/statistics")
interfacesstate_interface_ipv4 = tf.YangElemMap(
    interfacesstate_interface,
    "/interfaces-state/interface/ipv4")
interfacesstate_interface_ipv6 = tf.YangElemMap(
    interfacesstate_interface,
    "/interfaces-state/interface/ipv6")
interfacesstate_interface_ipv4_neighbor = tf.YangElemMap(
    interfacesstate_interface_ipv4,
    "/interfaces-state/interface/ipv4/neighbor")
interfacesstate_interface_ipv4_children = tf.YangElemMap(
    interfacesstate_interface_ipv4,
    "/interfaces-state/interface/ipv4/children")
interfacesstate_interface_ipv6_children = tf.YangElemMap(
    interfacesstate_interface_ipv6,
    "/interfaces-state/interface/ipv6/children")
interfacesstate_interface_ipv6_neighbor = tf.YangElemMap(
    interfacesstate_interface_ipv6,
    "/interfaces-state/interface/ipv6/neighbor")

m = interfacesstate_interface_ipv6_neighbor
m.add(MapValue("ip", "dst"))
m.add(MapValue("link-layer-address", "lladdr"))
m.add(NeighOrigin("origin", tf.YangType.LEAF))
# is-router
m.add(IPV6NeighState("state", tf.YangType.LEAF))

m = interfacesstate_interface_ipv6_children
m.add(MapValue("ip", "local"))
m.add(MapValue("prefix-length", "prefixlen"))
m.add(IPV6Origin("origin", tf.YangType.LEAF))
m.add(IPV6Status("status", tf.YangType.LEAF))

m = interfacesstate_interface_ipv4_children
m.add(MapValue("ip", "local"))
m.add(MapValue("prefix-length", "prefixlen"))
m.add(IPV4Origin("origin", tf.YangType.LEAF))

m = interfacesstate_interface_ipv4_neighbor
m.add(MapValue("ip", "dst"))
m.add(MapValue("link-layer-address", "lladdr"))
m.add(NeighOrigin("origin", tf.YangType.LEAF))

m = interfacesstate_interface_ipv6
# forwarding
m.add(MapValue("mtu", "mtu", maxint=65535))
m.add(IPV6Address("address", tf.YangType.LIST,
                  interfacesstate_interface_ipv6_children))
m.add(IPV6Neigh("neighbor", tf.YangType.LIST,
                interfacesstate_interface_ipv6_neighbor))

m = interfacesstate_interface_ipv4
# forwarding
m.add(MapValue("mtu", "mtu", maxint=65535))
m.add(IPV4Address("address", tf.YangType.LIST,
                  interfacesstate_interface_ipv4_children))
m.add(IPV4Neigh("neighbor", tf.YangType.LIST,
                interfacesstate_interface_ipv4_neighbor))

m = interfacesstate_interface_statistics
m.add(DiscontinuityTime("discontinuity-time", tf.YangType.LEAF))
m.add(Map2Value("in-octets", "rx", "bytes"))
m.add(Map2Value("in-unicast-pkts", "rx", "bytes"))
# in-broadcast-pkts
m.add(Map2Value("in-multicast-pkts", "rx", "multicast"))
m.add(Map2Value("in-discards", "rx", "dropped"))
m.add(ErrorValue("in-errors", keyval = "rx"))
# in-unknown-protos
m.add(Map2Value("out-octets", "tx", "bytes"))
m.add(Map2Value("out-unicast-pkts", "tx", "bytes"))
# out-broadcast-pkts
m.add(Map2Value("out-multicast-pkts", "tx", "multicast"))
m.add(Map2Value("out-discards", "tx", "dropped"))
m.add(ErrorValue("out-errors", keyval = "tx"))

m = interfacesstate_interface
m.add(MapValue("name", "ifname"))
m.add(InterfaceStateType("type", tf.YangType.LEAF,
                         xmlprocvalue=False, wrapxml=False))
m.add(InterfaceStateAdminStatus("admin-status", tf.YangType.LEAF))
m.add(InterfaceOperStatus("oper-status", tf.YangType.LEAF))
m.add(MapValue("if-index", "ifindex"))
m.add(MapValue("phys-address", "address"))
# FIXME - how to get speed?
# Also missing: last-change, higher-layer-if, lower-layer-if.
m.add(MapChild("statistics", "stats64",
               interfacesstate_interface_statistics))
m.add(tf.YangElemValueOnly("ipv4", tf.YangType.CONTAINER,
                           interfacesstate_interface_ipv4,
                           namespace=IETF_IP_NAMESPACE))
m.add(tf.YangElemValueOnly("ipv6", tf.YangType.CONTAINER,
                           interfacesstate_interface_ipv6,
                           namespace=IETF_IP_NAMESPACE))

m = interfacesstate
m.add(StateInterface("interface", tf.YangType.LIST,
                     interfacesstate_interface))

m = ietfip
m.add(tf.YangElem("interfaces", tf.YangType.CONTAINER,
                  interfaces,
                  namespace=IETF_INTERFACES_NAMESPACE))
m.add(tf.YangElem("interfaces-state", tf.YangType.CONTAINER,
                  interfacesstate,
                  namespace=IETF_INTERFACES_NAMESPACE,
                  isconfig=False))

class Handler(tf.TopElemHandler, tf.ProgOut):
    # FIXME - this is a hack for now
    first_call_done = False

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

    # FIXME - this is a hack for now
    def validate(self, t):
        if not self.first_call_done:
            return 0
        return super().validate(t)

    # FIXME - this is a hack for now
    def commit(self, t):
        if not self.first_call_done:
            self.first_call_done = True
            return 0
        return super().commit(t)

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

    pass

handler = Handler("ietf-ip", ietfip)
handler.p = clixon_beh.add_plugin("ietf-ip", IETF_INTERFACES_NAMESPACE, handler)
