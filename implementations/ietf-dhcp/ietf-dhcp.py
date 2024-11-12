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

MY_NAMESPACE = "http://linux.org"
IETF_SYSTEM_NAMESPACE = "urn:ietf:params:xml:ns:yang:ietf-system"

# We create the main map first because it's used by everything else.
ietfdhcp = tf.YangElemMap(None, "/")


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

class DHCPRelay:
        def __init__(self):
            return

        pass

class DHCPRelayServerGroupData:
    def __init__(self):
        self.name = None
        self.interface = None
        self.gateway_address = None
        self.server_address = None # This is a list TBD
        return

    pass

class DHCPRelayServerGroupName(tf.YangElem):
    def validate_add(self, data, xml):
        data.userNTP.curr_server.certificate = xml.get_body()
        return

    def validate_del(self, data, xml):
        # Nothing to do on delete
        return

    def validate(self, data, origxml, newxml):
        return self.validate_add(data, newxml)

    def getvalue(self, data, vdata):
        return "x"

    pass

