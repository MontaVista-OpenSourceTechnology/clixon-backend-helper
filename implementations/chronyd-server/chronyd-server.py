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

# This configures a chronyd server.  The file is in
# /etc/chrony/conf.c/server.conf and the format is.
# 
#   allow address/subnet
#   allow....
#   deny address/subnet
#   deny...
#   port <port>
#   ntsport <port>
#   ntsdumpdir /var/lib/chrony
#   ntsserverkey /crypto/keys/nts.key
#   ntsservercert /crypto/keys/nts.crt
#
# In addition, a key and a certificate are configured in the above files.

import os
import clixon_beh
import clixon_beh.transaction_framework as tf

MY_NAMESPACE = "http://mvista.com/chronyd"

# For testing, to store the files elsewhere to avoid updating the main
# system data.
sysbase = os.getenv("CHRONYD_SERVER_SYSBASE")
if sysbase is None:
    sysbase = os.getenv("CLIXON_BEH_SERVER_SYSBASE")
    if sysbase is None:
        sysbase = ""
        pass
    pass

chronyccmd = "/usr/bin/chronyc"
chronydir = sysbase + "/etc/chrony"
chronyd_server_file = chronydir + "/conf.d/server.conf"

cpcmd = "/bin/cp"
mvcmd = "/bin/mv"
rmcmd = "/bin/rm"
systemctlcmd = "/bin/systemctl"

ntsdumpdir = sysbase + "/var/lib/chrony"
ntsserverkey = sysbase + "/crypto/keys/nts.key"
ntsservercert = sysbase + "/crypto/keys/nts.crt"

default_port = 123
default_ntsport = 4460

class ServerFile:
    def __init__(self, fname = chronyd_server_file,
                 keyfname = ntsserverkey, certfname = ntsservercert):
        self.fname = fname
        self.keyfname = keyfname
        self.certfname = certfname
        self.allows = []
        self.denies = []
        self.port = default_port
        self.ntsport = default_ntsport
        self.serverkey = None
        self.servercert = None
        self.oldserverfile = False
        self.oldserverkey = False
        self.oldservercert = False
        self.read()
        return

    def read(self):
        try:
            with open(self.fname, "r") as f:
                for i in f:
                    if i.startswith("allow"):
                        self.allows.append(i.split()[1])
                    elif i.startswith("deny"):
                        self.denies.append(i.split()[1])
                    elif i.startswith("port"):
                        self.port = int(i.split()[1])
                    elif i.startswith("ntsport"):
                        self.ntsport = int(i.split()[1])
                        pass
                    pass
                pass
        except:
            pass # File doesn't exist or is wrong, just use an empty one.
        return

    def write(self):
        with open(self.fname, "w") as f:
            for i in self.allows:
                f.write("allow " + i + "\n")
                pass
            for i in self.denies:
                f.write("deny " + i + "\n")
                pass
            if self.port != default_port:
                f.write("port " + str(self.port) + "\n")
                pass
            if self.ntsport != default_ntsport:
                f.write("ntsport " + str(self.ntsport) + "\n")
                pass
            f.write("ntsdumpdir /var/lib/chrony\n")
            f.write("ntsserverkey /crypto/keys/nts.key\n")
            f.write("ntsservercert /crypto/keys/nts.crt\n")
            pass
        return

    # For each file we write, back it up and then write the new file.
    def commit(self):
        if self.serverkey:
            try:
                self.program_output([cpcmd, "-f", self.keyfname,
                                     self.keyfname + ".keep"])
                self.oldserverkey = True
            except:
                pass
            with open(self.keyfname, "w") as f:
                f.write(self.serverkey)
                pass
            pass
        if self.servercert:
            try:
                self.program_output([cpcmd, "-f", self.certfname,
                                 self.certfname + ".keep"])
                self.oldservercert = True
            except:
                pass
            with open(self.certfname, "w") as f:
                f.write(self.servercert)
                pass
            pass
        try:
            self.program_output([cpcmd, "-f", self.fname,
                                 self.fname + ".keep"])
            self.oldserverfile = True
        except:
            pass
        self.write()

        # Restart chronyd, but only in the non-debug case.
        if sysbase == "":
            self.program_output([systemctlcmd, "restart", "chronyd"])
        return

    # At completion, remove the backup files.
    def end(self):
        if self.oldserverfile:
            self.program_output([rmcmd, "-f", self.fname + ".keep"])
        if self.oldserverkey:
            self.program_output([rmcmd, "-f", self.keyfname + ".keep"])
        if self.oldservercert:
            self.program_output([rmcmd, "-f", self.certfname + ".keep"])
        return 0

    # If we failed, revert the server file from the backup.
    def revert(self):
        if self.oldserverfile:
            self.program_output([mvcmd, "-f", self.fname + ".keep",
                                 self.fname])
        if self.oldserverkey:
            self.program_output([mvcmd, "-f", self.keyfname + ".keep",
                                 self.keyfname])
        if self.oldservercert:
            self.program_output([mvcmd, "-f", self.certfname + ".keep",
                                 self.certfname])
        return 0

    pass

class Server(tf.YangElem):
    # When a transaction starts on this part, save a backup copy of the
    # server file.
    def validate(self, data, origxml, newxml):
        # Get the current file data for processing.
        data.uservdata = ServerFile()
        # We will process this for a commit.  Run as privileged.
        data.add_op(self, "chronyd-server", data.uservdata, priv=True)
        super().validate(data, origxml, newxml)
        return

    def commit(self, op):
        op.value.commit()
        return

    def revert(self, op):
        op.value.revert()
        return

    def end(self, op):
        op.value.end()
        return

    # Get our file data and pass it down the chain.
    def getxml(self, data, path, indexname = None, index = None, vdata = None):
        vdata = ServerFile()
        return super().getxml(data, path, indexname=indexname, index=index,
                              vdata=vdata);

    pass

class Allow(tf.YangElemValidateOnly):
    def validate_add(self, data, xml):
        # Add it to the list if it's not already there.
        v = xml.get_body()
        if v not in data.uservdata.allows:
            data.uservdata.allows.append(v)
            pass
        return

    def validate_del(self, data, xml):
        # Delete it from the list if it's there.
        v = xml.get_body()
        if v in data.uservdata.allows:
            data.uservdata.allows.remove(v)
            pass
        return

    def validate(self, data, origxml, newxml):
        # Really shouldn't happen, as you can only add and delete from
        # leaf-lists, but just add it if it does.
        self.validate_add(data, newxml)
        return

    # Since this is a list (leaf-list), we don't use getvalue()
    # because we have to deal with indexes.  Instead, we have three
    # functions, on to fetch the value of a specific index (if it
    # exists), on to return the value from a single index (which is
    # simple, because it's just a value) and one to fetch all values
    # in the index.

    def fetch_index(self, indexname, index, vdata):
        if index in v.allows:
            return index
        return None

    def getonevalue(self, data, vdata):
        return vdata

    def fetch_full_index(self, vdata):
        return vdata.allows

    pass
        
class Deny(tf.YangElemValidateOnly):
    def validate_add(self, data, xml):
        # Add it to the list if it's not already there.
        v = xml.get_body()
        if v not in data.uservdata.denies:
            data.uservdata.denies.append(v)
            pass
        return

    def validate_del(self, data, xml):
        # Delete it from the list if it's there.
        v = xml.get_body()
        if v in data.uservdata.denies:
            data.uservdata.denies.remove(v)
            pass
        return

    def validate(self, data, origxml, newxml):
        # Really shouldn't happen, as you can only add and delete from
        # leaf-lists, but just add it if it does.
        self.validate_add(data, newxml)
        return

    def fetch_index(self, indexname, index, vdata):
        if index in v.denies:
            return index
        return None

    def getonevalue(self, data, vdata):
        return vdata

    def fetch_full_index(self, vdata):
        return vdata.denies

    pass
        
class Port(tf.YangElemValidateOnly):
    def validate_add(self, data, xml):
        data.uservdata.port = int(xml.get_body())
        return

    def validate_del(self, data, xml):
        # Go back to the default.
        data.uservdata.port = default_port
        return

    def validate(self, data, origxml, newxml):
        # Same as add
        self.validate_add(data, newxml)
        return

    def getvalue(self, data, vdata):
        return str(vdata.port)

    pass
        
class NTSPort(tf.YangElemValidateOnly):
    def validate_add(self, data, xml):
        data.uservdata.ntsport = int(xml.get_body())
        return

    def validate_del(self, data, xml):
        # Go back to the default.
        data.uservdata.ntsport = default_ntsport
        return

    def validate(self, data, origxml, newxml):
        # Same as add
        self.validate_add(data, newxml)
        return

    def getvalue(self, data, vdata):
        return str(vdata.ntsport)

    pass

class ServerKey(tf.YangElemValidateOnly):
    def validate_add(self, data, xml):
        v = xml.get_body()
        # Ignore our dummy data if it comes down to us.
        if v != "x":
            data.uservdata.serverkey = v
        return

    def validate_del(self, data, xml):
        raise tf.RPCError("application", "invalid-value", "error",
                          "Delete of server key not allowed")

    def validate(self, data, origxml, newxml):
        # Same as add
        self.validate_add(data, newxml)
        return

    def getvalue(self, data, vdata):
        # Don't return security-sensitive data
        return "x"

    pass

class ServerCert(tf.YangElemValidateOnly):
    def validate_add(self, data, xml):
        v = xml.get_body()
        # Ignore our dummy data if it comes down to us.
        if v != "x":
            data.uservdata.servercert = v
        return

    def validate_del(self, data, xml):
        raise tf.RPCError("application", "invalid-value", "error",
                          "Delete of server certificate not allowed")

    def validate(self, data, origxml, newxml):
        # Same as add
        self.validate_add(data, newxml)
        return

    def getvalue(self, data, vdata):
        # Don't return security-sensitive data
        return "x"

    pass

# Top-level entry
chronydserver = tf.YangElemMap(None, "/")

server = tf.YangElemMap(chronydserver, "/server")

m = server
m.add(Allow("allows", tf.YangType.LEAFLIST))
m.add(Deny("denys", tf.YangType.LEAFLIST))
m.add(Port("port", tf.YangType.LEAF))
m.add(NTSPort("ntsport", tf.YangType.LEAF))
m.add(ServerKey("serverkey", tf.YangType.LEAF))
m.add(ServerCert("servercert", tf.YangType.LEAF))

class Stratum(tf.YangElemValueOnly):
    def getvalue(self, data, vdata):
        s = self.program_output([chronyccmd, "tracking"])
        for i in s.split("\n"):
            if i.startswith("Stratum"):
                return i.split()[2]
            pass
        return None

    pass

month_to_num = {
    "Jan": "01",
    "Feb": "02",
    "Mar": "03",
    "Apr": "04",
    "May": "05",
    "Jun": "06",
    "Jul": "07",
    "Aug": "08",
    "Sep": "09",
    "Oct": "10",
    "Nov": "11",
    "Dec": "12"
}

class Time(tf.YangElemValueOnly):
    def getvalue(self, data, vdata):
        s = self.program_output([chronyccmd, "tracking"])
        for i in s.split("\n"):
            if i.startswith("Ref time"):
                j = i.split(":", 1)[1].split()
                # Convert from wierd chronyd format into YANG type, which
                # is mostly ISO 8601.  The format from chronyd is:
                #   <dayofweek> <monthname> <day> <time> <year>
                # and we convert to:
                #   <year>-<monthnumber>-<day>T<time>Z
                return "%s-%s-%sT%sZ" % (j[4], month_to_num[j[1]], j[2], j[3])
            pass
        return None

    pass

statistics = tf.YangElemMap(chronydserver, "/statistics")

m = statistics
m.add(Stratum("stratum", tf.YangType.LEAF))
m.add(Time("time", tf.YangType.LEAF))

m = chronydserver
# We have to add the namespace to the ones at the top level so the
# namespace is set in the query responses.  Don't forget to do this.
m.add(Server("server", tf.YangType.CONTAINER, server,
             namespace=MY_NAMESPACE))
m.add(tf.YangElem("statistics", tf.YangType.CONTAINER, statistics,
                  namespace=MY_NAMESPACE,
                  isconfig=False))

class Handler(tf.TopElemHandler, tf.ProgOut):
    def exit(self):
        self.p = None # Break circular dependency
        return 0;

    def system_only(self, nsc, xpath):
        if xpath == "/":
            # There is no state data in /statistics, so no need to fetch it.
            xpath = "/server"
            pass
        return self.statedata(nsc, xpath, data = tf.GetData(False))

    pass

handler = Handler("chronyd-server", chronydserver)
handler.p = clixon_beh.add_plugin(handler.name, MY_NAMESPACE, handler)
