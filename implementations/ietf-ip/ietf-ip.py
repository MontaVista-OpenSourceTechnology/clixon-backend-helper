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

IETF_INTERFACES_NAMESPACE = "urn:ietf:params:xml:ns:yang:ietf-interfaces"
IETF_IP_NAMESPACE = "urn:ietf:params:xml:ns:yang:ietf-ip"

class MapValue(tf.YangElemValueOnly):
    """Pull the given keyval from the value mapping."""
    def __init__(self, name, keyval):
        self.keyval = keyval
        super().__init__(name, tf.YangType.LEAF)
        return

    def getvalue(self, vdata=None):
        if self.keyval in vdata:
            return vdata[self.keyval]
        return ""
    pass

class Map2Value(tf.YangElemValueOnly):
    """Pull the given keyval from the value mapping."""
    def __init__(self, name, keyval1, keyval2):
        self.keyval1 = keyval1
        self.keyval2 = keyval2
        super().__init__(name, tf.YangType.LEAF)
        return

    def getvalue(self, vdata=None):
        if self.keyval1 in vdata[self.keyval1]:
            return vdata[self.keyval1][self.keyval2]
        return ""
    pass

class ErrorValue(tf.YangElemValueOnly):
    """Pull the given all _error values from the value mapping."""
    def __init__(self, name, keyval = None):
        self.keyval = keyval
        super().__init__(name, tf.YangType.LEAF)
        return

    def getvalue(self, vdata=None):
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
    def __init__(self, name, mapval, children, validate_all=True):
        self.mapval = mapval
        super().__init__(name, tf.YangType.CONTAINER, children,
                         validate_all=validate_all)
        return

    def getxml(self, path, namespace=None, indexname=None, index=None,
               vdata=None):
        vdata = vdata[self.mapval]
        return super().getxml(path, namespace=namespace, indexname=indexname,
                              index=index, vdata=vdata)

    def getvalue(self, vdata=None):
        vdata = vdata[self.mapval]
        return super().getvalue(vdata=vdata)

    pass

# /interfaces/interface/ipv4/neighbor/origin
# /interfaces/interface/ipv6/neighbor/origin
# /interfaces-state/interface/ipv4/neighbor/origin
# /interfaces-state/interface/ipv6/neighbor/origin
class NeighOrigin(tf.YangElemValueOnly):
    """Get the origin value of the address."""
    def getvalue(self, vdata=None):
        if "PERMANENT" in vdata["state"]:
            return "static"
        return "dynamic"

    pass

# /interfaces/interface/ipv6/neighbor/state
# /interfaces-state/interface/ipv6/neighbor/state
class IPV6NeighState(tf.YangElemValueOnly):
    """Get the state value of the address."""
    def getvalue(self, vdata=None):
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
ipv6_neighbor = {
    "ip": MapValue("ip", "dst"),
    "link-layer-address": MapValue("link-layer-address", "lladdr"),
    "origin": NeighOrigin("origin", tf.YangType.LEAF),
    # is-router
    "state": IPV6NeighState("state", tf.YangType.LEAF)
}

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
    def getvalue(self, vdata=None):
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
    def getvalue(self, vdata=None):
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

# /interfaces/interface/ipv6
ipv6_children = {
    "ip": MapValue("ip", "local"),
    "prefix-length": MapValue("prefix-length", "prefixlen"),
    "origin": IPV6Origin("origin", tf.YangType.LEAF),
    "status": IPV6Status("status", tf.YangType.LEAF)
}

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

# /interfaces/interface/ipv6
interfaces_interface_ipv6_children = {
    # forwarding
    "mtu": MapValue("mtu", "mtu"),
    "address": IPV6Address("address", tf.YangType.LIST, ipv6_children),
    "neighbor": IPV6Neigh("neighbor", tf.YangType.LIST, ipv6_neighbor),
}

# /interfaces/interface/ipv4/address/origin
# /interfaces-state/interface/ipv4/address/origin
class IPV4Origin(tf.YangElemValueOnly):
    """Get the origin value of the address."""
    def getvalue(self, vdata=None):
        if "dynamic" in vdata and vdata["dynamic"] == "true":
            return "dhcp"
        if vdata["local"].startswith("169.254."):
            return "random"
        return "static"

    pass

# /interfaces/interface/ipv4/address
ipv4_children = {
    "ip": MapValue("ip", "local"),
    "prefix-length": MapValue("prefix-length", "prefixlen"),
    "origin": IPV4Origin("origin", tf.YangType.LEAF)
}

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

# /interfaces-state/interface/ipv6/neighbor/origin
ipv4_neighbor = {
    "ip": MapValue("ip", "dst"),
    "link-layer-address": MapValue("link-layer-address", "lladdr"),
    "origin": NeighOrigin("origin", tf.YangType.LEAF)
}

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

# /interfaces-state/interface/ipv4
interfaces_interface_ipv4_children = {
    # enabled
    # forwarding
    "mtu": MapValue("mtu", "mtu"),
    "address": IPV4Address("address", tf.YangType.LIST, ipv4_children),
    "neighbor": IPV4Neigh("neighbor", tf.YangType.LIST, ipv4_neighbor),
}

# /interfaces-state/interface/statistics
interfaces_interface_statistics_children = {
    # discontinuity-time
    "in-octets": Map2Value("in-octets", "rx", "bytes"),
    "in-unicast-pkts": Map2Value("in-unicast-pkts", "rx", "bytes"),
    # in-broadcast-pkts
    "in-multicast-pkts": Map2Value("in-multicast-pkts", "rx", "multicast"),
    "in-discards": Map2Value("in-discards", "rx", "dropped"),
    "in-errors": ErrorValue("in-errors", keyval = "rx"),
    # in-unknown-protos
    "out-octets": Map2Value("out-octets", "tx", "bytes"),
    "out-unicast-pkts": Map2Value("out-unicast-pkts", "tx", "bytes"),
    # out-broadcast-pkts
    "out-multicast-pkts": Map2Value("out-multicast-pkts", "tx", "multicast"),
    "out-discards": Map2Value("out-discards", "tx", "dropped"),
    "out-errors": ErrorValue("out-errors", keyval = "tx")
}

# Convert beteen linux ip values and iana-if-type
link_types = {
    "loopback": "softwareLoopback",
    "ether": "ethernetCsmacd",
}

# /interfaces-state/interface/type
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

    def getvalue(self, vdata=None):
        v = vdata["link_type"]
        if v == "none":
            # It might be a tunnel.
            if vdata["ifname"].startswith("tun"):
                return "tunnel"
            pass
        elif v in link_types:
            return link_types[v]
        return "other"
    pass

# /interfaces-state/interface/admin-status
class InterfaceAdminStatus(tf.YangElemValueOnly):
    """Get the admin-status value of the interface."""
    def getvalue(self, vdata=None):
        if "UP" in vdata["flags"]:
            return "up"
        # FIXME - do we need to add anything else?
        return "down"
    pass

# /interfaces/interface/oper-status
# /interfaces-state/interface/oper-status
class InterfaceOperStatus(tf.YangElemValueOnly):
    """Get the oper-status value of the interface."""
    def getvalue(self, vdata=None):
        # FIXME - "operstate" doesn't seem to always be correct.  Just use
        # flags.
        if "UP" in vdata["flags"]:
            return "up"
        # FIXME - do we need to add anything else?
        return "down"
    pass

# /interfaces/interface
interfaces_interface_children = {
    "name": MapValue("name", "ifname"),
    "description": tf.YangElemConfigOnly("description"),
    "type": InterfaceType("type", tf.YangType.LEAF),
    "admin-status": InterfaceAdminStatus("admin-status", tf.YangType.LEAF),
    "oper-status": InterfaceOperStatus("oper-status", tf.YangType.LEAF),
    "if-index": MapValue("if-index", "ifindex"),
    "phys-address": MapValue("phys-address", "address"),
    # FIXME - how to get speed?
    # Also missing: last-change, higher-layer-if, lower-layer-if.
    "statistics": MapChild("statistics", "stats64",
                            interfaces_interface_statistics_children),
    "ipv4": tf.YangElem("ipv4", tf.YangType.CONTAINER,
                        interfaces_interface_ipv4_children,
                        namespace=IETF_IP_NAMESPACE),
    "ipv6": tf.YangElem("ipv6", tf.YangType.CONTAINER,
                        interfaces_interface_ipv6_children,
                        namespace=IETF_IP_NAMESPACE)
}

# /interfaces/interface
class Interface(tf.YangElem):
    def validate_add(self, data, xml):
        raise tf.RPCError("application", "invalid-value", "error",
                          "Setting interface not allowed")

    def validate_del(self, data, xml):
        raise tf.RPCError("application", "invalid-value", "error",
                          "Setting interface not allowed")

    def validate(self, data, origxml, newxml):
        raise tf.RPCError("application", "invalid-value", "error",
                          "Setting interface not allowed")

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

# /interfacesstate
interfaces_children = {
    "interface": Interface("interface", tf.YangType.LIST,
                           interfaces_interface_children)
}

state_ipv6_neighbor = {
    "ip": MapValue("ip", "dst"),
    "link-layer-address": MapValue("link-layer-address", "lladdr"),
    "origin": NeighOrigin("origin", tf.YangType.LEAF),
    # is-router
    "state": IPV6NeighState("state", tf.YangType.LEAF)
}

state_ipv6_children = {
    "ip": MapValue("ip", "local"),
    "prefix-length": MapValue("prefix-length", "prefixlen"),
    "origin": IPV6Origin("origin", tf.YangType.LEAF),
    "status": IPV6Status("status", tf.YangType.LEAF)
}

interfaces_state_interface_ipv6_children = {
    # forwarding
    "mtu": MapValue("mtu", "mtu"),
    "address": IPV6Address("address", tf.YangType.LIST, state_ipv6_children),
    "neighbor": IPV6Neigh("neighbor", tf.YangType.LIST, state_ipv6_neighbor),
}

state_ipv4_children = {
    "ip": MapValue("ip", "local"),
    "prefix-length": MapValue("prefix-length", "prefixlen"),
    "origin": IPV4Origin("origin", tf.YangType.LEAF)
}

class StateIPV4Address(tf.YangElemValueOnly):
    def fetch_index(self, indexname, index, vdata):
        for i in vdata["addr_info"]:
            if i["ip"] == index:
                return i
            pass
        return None

    def fetch_full_index(self, vdata):
        return vdata["addr_info"]

    pass

# /interfaces-state/interface/ipv6/neighbor/origin
state_ipv4_neighbor = {
    "ip": MapValue("ip", "dst"),
    "link-layer-address": MapValue("link-layer-address", "lladdr"),
    "origin": NeighOrigin("origin", tf.YangType.LEAF)
}

class StateIPV4Neigh(tf.YangElemValueOnly):
    def get_neighs(self, vdata):
        return self.program_output([ipcmd, "-4", "-j", "neigh", "show", "dev",
                                    vdata["ifname"]],
                                   decoder = lambda x : json.loads(x))

    def fetch_index(self, indexname, index, value):
        neighs = self.get_neighs(vdata)
        for i in neighs:
            if i["dst"] == index:
                return i
            pass
        return None

    def fetch_full_index(self, vdata):
        return self.get_neighs(vdata)

    pass

interfaces_state_interface_ipv4_children = {
    # forwarding
    "mtu": MapValue("mtu", "mtu"),
    "address": StateIPV4Address("address", tf.YangType.LIST,
                                state_ipv4_children),
    "neighbor": StateIPV4Neigh("neighbor", tf.YangType.LIST,
                               state_ipv4_neighbor),
}

# /interfaces-state/interface/type
class InterfaceStateType(tf.YangElemValueOnly):
    """Get the iana-if-type value of the link_type."""
    def getvalue(self, vdata=None):
        v = vdata["link_type"]
        if v == "none":
            # It might be a tunnel.
            if vdata["ifname"].startswith("tun"):
                return "tunnel"
            pass
        elif v in link_types:
            return link_types[v]
        return "other"
    pass

# /interfaces-state/interface/admin-status
class InterfaceStateAdminStatus(tf.YangElemValueOnly):
    """Get the admin-status value of the interface."""
    def getvalue(self, vdata=None):
        if "UP" in vdata["flags"]:
            return "up"
        # FIXME - do we need to add anything else?
        return "down"
    pass

# /interfaces-state/interface
interfaces_state_interface_children = {
    "name": MapValue("name", "ifname"),
    "type": InterfaceStateType("type", tf.YangType.LEAF),
    "admin-status": InterfaceStateAdminStatus("admin-status", tf.YangType.LEAF),
    "oper-status": InterfaceOperStatus("oper-status", tf.YangType.LEAF),
    "if-index": MapValue("if-index", "ifindex"),
    "phys-address": MapValue("phys-address", "address"),
    # FIXME - how to get speed?
    # Also missing: last-change, higher-layer-if, lower-layer-if.
    "statistics": MapChild("statistics", "stats64",
                            interfaces_interface_statistics_children),
    "ipv4": tf.YangElemValueOnly("ipv4", tf.YangType.CONTAINER,
                                 interfaces_interface_ipv4_children,
                                 namespace=IETF_IP_NAMESPACE),
    "ipv6": tf.YangElemValueOnly("ipv6", tf.YangType.CONTAINER,
                                 interfaces_interface_ipv6_children,
                                 namespace=IETF_IP_NAMESPACE)
}

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

# /interfaces-state
interfaces_state_children = {
    "interface": StateInterface("interface", tf.YangType.LIST,
                                interfaces_state_interface_children)
}

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

    def statedata(self, nsc, xpath):
        return super().statedata(nsc, xpath)

    pass

children = {
    "interfaces": tf.YangElem("interfaces", tf.YangType.LIST,
                              interfaces_children,
                              namespace=IETF_INTERFACES_NAMESPACE),
    "interfaces-state": tf.YangElem("interfaces-state", tf.YangType.LIST,
                                    interfaces_state_children,
                                    namespace=IETF_INTERFACES_NAMESPACE),
}
handler = Handler("ietf-ip", children)
handler.p = clixon_beh.add_plugin("ietf-ip", IETF_INTERFACES_NAMESPACE, handler)

class AuthStatedata:
    def stateonly(self):
        rv = children["interfaces"].getonevalue()
        if rv and len(rv) > 0:
            rv = ("<interfaces xmlns=\"" + IETF_INTERFACES_NAMESPACE + "\">"
                  + rv + "</interfaces>")
            pass
        # Uncomment to print the return data
        #print("Return: " + str(rv))
        return (0, rv)

    pass

clixon_beh.add_stateonly("<interfaces xmlns=\"" + IETF_INTERFACES_NAMESPACE +
                         "\"></interfaces>",
                         AuthStatedata())

# I don't think the below is necessary.
# class AuthStatedata:
#     def stateonly(self):
#         rv = children["interfaces-state"].getonevalue()
#         if rv and len(rv) > 0:
#             rv = ("<interfaces-state xmlns=\"" +
#                   IETF_INTERFACES_NAMESPACE + "\">"
#                   + rv + "</interfaces-state>")
#             pass
#         # Uncomment to print the return data
#         #print("Return: " + str(rv))
#         return (0, rv)

#     pass

# clixon_beh.add_stateonly("<interfaces-state xmlns=\"" +
#                          IETF_INTERFACES_NAMESPACE +
#                          "\"></interfaces-state>",
#                          AuthStatedata())
