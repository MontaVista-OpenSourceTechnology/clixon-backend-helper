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

# This is an implementation of ietf-system with some enhancements for
# Linux

import os
import shlex
import clixon_beh
import clixon_beh.transaction_framework as tf

MY_NAMESPACE = "http://linux.org"
IETF_SYSTEM_NAMESPACE = "urn:ietf:params:xml:ns:yang:ietf-system"

# For testing, to store the files elsewhere to avoid updating the main
# system data.
sysbase = "/home/cminyard/tmp/clixon"

# Enable various password operations
allow_user_add_del = True      # Add/delete users allowed?
allow_user_pw_change = True    # User password changes allowed?
allow_user_key_change = True   # SSH authorized key changes allowed?
enable_user_update = True      # Allow the password files to be chagned at all.
useradd = "/sbin/useradd"
userdel = "/sbin/userdel"
usermod = "/sbin/usermod"
have_shadow = True
passwdfile = sysbase + "/etc/passwd"
shadowfile = sysbase + "/etc/shadow"

# Various commands
cpcmd = "/bin/cp"
touchcmd = "/bin/touch"
lscmd = "/bin/ls"
lncmd = "/bin/ln"
mvcmd = "/bin/mv"
mkdircmd = "/bin/mkdir"
rmcmd = "/bin/rm"
catcmd = "/bin/cat"
datecmd = "/bin/date"
sedcmd = "/bin/sed"
systemctlcmd = "/bin/systemctl"

# Hostname management
hostnamecmd = "/bin/hostname"
hostnamefile = sysbase + "/etc/hostname"

# Time management
localtimefile = sysbase + "/etc/localtime"
timezonefile = sysbase + "/etc/timezone"
zoneinfodir = sysbase + "/usr/share/zoneinfo/"

chronyccmd = "/usr/bin/chronyc"
chronydir = sysbase + "/etc/chrony"

# end old-dns or dns-proxy is set, we have things to do to resolv.conf.
resolvconffile = sysbase + "/etc/resolv.conf"

# dnsproxy configuration depends on systemd setup.  We have a file in
# /etc/sysconfig in the form:
#   SSL_CERT_FILE=/etc/dnsproxy/dnsserv-up-54.crt
#   SERVER_one=-u tls://192.168.91.1:853
#   dnsconf=-l 127.0.0.1 -p 8054 -u tls://192.168.91.1:853
# where the name above is "one".  This allows us to store the name in
# the file.  Unfortunately, systemd won't let us use ${SERVER_one} :(.
#
# This particular configuration is a little strange, for this dnsmasq
# is running providing DNS services (along with DHCP and maybe TFTP),
# this is used to make a secure connection upstream that dnsmasq hooks
# to.  If you just wanted to use dnsproxy, you could modify the listen
# port and address as you needed.
dnsproxyconf = sysbase + "/etc/sysconfig/dnsproxy-client-54"
dnsproxycert = sysbase + "/etc/dnsproxy/dnsserv-up-54.crt"
dnsproxysystemd = "dnsproxy@client-54"
dnsproxylistenport = "8054"
dnsproxylistenaddr = "127.0.0.1"

# Pull the feature values from the config.
old_dns_supported = clixon_beh.is_feature_set("linux-system", "old-dns")
dnsproxy_supported = clixon_beh.is_feature_set("linux-system", "dnsproxy")
using_ntp = clixon_beh.is_feature_set("ietf-system", "ntp")

# If DNS isn't managed through this interface, just stub everything
# out.  In that case, it would be generally be managed through
# systemd's resolvectl and that's per-interface, mostly.  It would
# need its own control interface.
do_dns = old_dns_supported or dnsproxy_supported

# /system/hostname
class Hostname(tf.YangElem):
    def validate_add(self, data, xml):
        self.validate(data, None, xml)
        return

    def validate_del(self, data, xml):
        raise tf.RPCError("application", "invalid-value", "error",
                          "Delete of hostname not allowed")

    def validate(self, data, origxml, newxml):
        value = newxml.get_body()
        if len(value) > 64: # Linux only allow 64 characters
            raise tf.RPCError("application", "invalid-value", "error",
                              "Host name too long, 64-character max.")
        data.add_op(self, None, value)
        return

    def commit(self, op):
        op.oldvalue = self.getvalue()
        self.do_priv(op)
        return

    def revert(self, op):
        self.do_priv(op)
        return

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
        if sysbase == "":
            self.program_output([hostnamecmd, value])
            pass
        f = open(hostnamefile, "w")
        try:
            f.write(value + "\n")
        finally:
            f.close()
            pass
        return

    def getvalue(self, vdata=None):
        with open(hostnamefile, "r") as file:
            data = file.read().rstrip()
            pass
        return data

# /system/clock/timezone-*
class TimeZone(tf.YangElem):
    def __init__(self, name, is_name=True):
        super().__init__(name, tf.YangType.LEAF)
        self.is_name = is_name
        return

    def validate_add(self, data, xml):
        self.validate(data, None, xml)
        return

    def validate_del(self, data, xml):
        # We just ignore this, it can happen when changing between
        # name and offset.
        return

    def validate(self, data, origxml, newxml):
        if not self.is_name:
            raise tf.RPCError("application", "invalid-value", "error",
                              "Only name timezones are accepted")
        value = newxml.get_body()
        if not os.path.exists(zoneinfodir + value):
            raise tf.RPCError("application", "invalid-value", "error",
                              value + " not a valid timezone")
        data.add_op(self, None, value)
        return

    def commit(self, op):
        oldlocaltime = None
        try:
            lt = self.program_output([lscmd, "-l", localtimefile])
            lt = lt.split("->")
            if len(lt) > 2:
                oldlocaltime = lt[1].strip()
        except:
            pass
        op.oldvalue = [oldlocaltime, self.getvalue()]
        self.do_priv(op)
        return

    def revert(self, op):
        self.do_priv(op)
        return

    def priv(self, op):
        if op.revert:
            if op.oldvalue is None:
                return # We didn't set it, nothing to do
            try:
                if op.oldvalue[0] is None:
                    # timedatectl will not add /etc/localtime if it
                    # does not exist or is not already a symlink.
                    # Make sure it points to something.
                    self.program_output([lncmd, "-sf", zoneinfodir + "GMT",
                                         localtimefile])
                    pass
                self.setvalue(op.oldvalue[1])
            except:
                pass
        else:
            self.setvalue(op.value)
        return

    def setvalue(self, value):
        if sysbase == "":
            self.program_output(["/bin/timedatectl", "set-timezone",
                                 "--", value])
        else:
            f = open(timezonefile, "w")
            f.write(value + "\n")
            f.close()
            self.program_output([lncmd, "-sf", zoneinfodir + value,
                                 localtimefile])
            pass
        return

    def getvalue(self, vdata=None):
        if not self.is_name:
            return ""
        try:
            s = self.program_output([catcmd, timezonefile]).strip()
        except:
            s = "GMT"
            pass
        return s

# /system/clock
system_clock_children = {
    "timezone-name": TimeZone("timezone-name", is_name=True),
    "timezone-utc-offset": TimeZone("timezone-utc-offset", is_name=False),
}

# DNS is configured through features in the linux-system yang file.
# This file handles old-style resolv.conf DNS, and using dnsproxy for
# a secure connection.  If you are using resolvectl, disable it in the
# yang file and handle it in the IP address handling.

class DNSHandler(tf.YangElemCommitOnly):
    """This handles the full commit operation for DNS updates.
    """
    def commit(self, op):
        self.do_priv(op)
        return

    def commit_done(self, op):
        self.do_priv(op)
        return

    def priv_old_dns(self, op):
        ddata = op.value
        if op.revert:
            os.remove(resolvconffile + ".tmp")
        elif op.done:
            os.replace(resolvconffile + ".tmp", resolvconffile)
        else:
            # Create a file to hold the data.  We move the file over when
            # done.
            # FIXME - no handling for port or certificate in the default
            # way of doing this.
            f = open(resolvconffile + ".tmp", "w")
            try:
                if len(ddata.add_search) > 0:
                    f.write("search")
                    for i in ddata.add_search:
                        f.write(" " + str(i))
                        pass
                    f.write("\n")
                    pass
                for i in ddata.add_server:
                    f.write("#name: " + str(i.name) + "\n")
                    f.write("nameserver " + str(i.address) + "\n")
                    pass
                f.write("options timeout:" + ddata.timeout + " attempts:"
                        + ddata.attempts)
                if ddata.use_vc:
                    f.write(" use-vc")
                    pass
                f.write("\n")
            finally:
                f.close()
                pass
            pass
        return

    def priv_dnsproxy(self, op):
        """Set up the configuration for dnsproxy"""
        ddata = op.value
        if op.revert:
            os.remove(dnsproxyconf + ".tmp")
            try:
                os.remove(dnsproxycert + ".tmp")
            except:
                pass
            os.remove(resolvconffile + ".tmp")
            return

        if op.done:
            os.replace(dnsproxyconf + ".tmp", dnsproxyconf)
            if ddata.certificate is not None:
                os.replace(dnsproxycert + ".tmp", dnsproxycert)
            os.replace(resolvconffile + ".tmp", resolvconffile)
            return

        f = open(dnsproxyconf + ".tmp", "w")
        try:
            if ddata.certificate is not None:
                f.write("SSL_CERT_FILE=" + dnsproxycert + "\n")
                fcert = open(dnsproxycert + ".tmp", "w")
                try:
                    fcert.write(ddata.certificate + "\n")
                finally:
                    fcert.close()
                    pass
                pass
            servers=""
            for i in ddata.add_server:
                serverstr = "-u tls://" + i.address + ":" + i.port
                f.write("SERVER_" + str(i.name) + "=" + serverstr + "\n")
                # Stupid systemd doesn't let us reference ${SERVER_xxx}.
                servers += " " + serverstr
                pass
            f.write("dnsconf=-l " + dnsproxylistenaddr +
                    " -p " + dnsproxylistenport +
                    servers + "\n")
        finally:
            f.close()
            pass

        # Update options and search in the resolv.conf file
        fin = open(resolvconffile, "r")
        f = open(resolvconffile + ".tmp", "w")
        try:
            for i in fin:
                if i.startswith("search "):
                    continue
                if i.startswith("options "):
                    continue
                f.write(i)
                pass
            if len(ddata.add_search) > 0:
                f.write("search")
                for i in ddata.add_search:
                    f.write(" " + str(i))
                    pass
                f.write("\n")
                pass
            f.write("options timeout:" + ddata.timeout + " attempts:"
                    + ddata.attempts)
            if ddata.use_vc:
                f.write(" use-vc")
                pass
            f.write("\n")
        finally:
            fin.close()
            f.close()
            pass

        if sysbase == "":
            self.program_output([systemctlcmd, "restart", dnsproxysystemd])
        return

    def priv(self, op):
        if dnsproxy_supported:
            self.priv_dnsproxy(op)
        else:
            self.priv_old_dns(op)
            pass
        return

    def revert(self, op):
        self.do_priv(op)
        return

    pass

class DNSServerData:
    """Information about a single DNS server."""
    def __init__(self):
        self.name = None
        self.address = None
        self.port = None

    def __str__(self):
        return f'({self.name}, {self.address}:{self.port})'

    pass

class DNSData:
    """All DNS data will be parsed into this structure."""
    def __init__(self):
        self.curr_server = None
        self.add_search = []
        self.add_server = []
        self.timeout = None
        self.attempts = None
        self.use_vc = False
        self.certificate = None
        return

    pass

def dns_get_opdata(data):
    """If a DNS operation is already registered in the op queue, just
    return its data.  Otherwisse add a DNS operation and return its
    data.

    """
    if data.userDNSOp is None:
        data.userDNSOp = data.add_op(DNSHandler("dns"), "dns", DNSData())
    return data.userDNSOp.value

# /system/dns-resolver/search
class DNSSearch(tf.YangElemValidateOnly):
    def validate_add(self, data, xml):
        ddata = dns_get_opdata(data)
        ddata.add_search.append(xml.get_body())
        return

    def validate(self, data, origxml, newxml):
        self.validate_add(data, newxml)
        return

    def fetch_index(self, indexname, index, vdata):
        for i in vdata["search"]:
            if i == index:
                return i
            pass
        return None

    def getonevalue(self, vdata):
        return vdata

    def fetch_full_index(self, vdata):
        return vdata["search"]

    pass

# /system/dns-resolver/server/name
class DNSServerName(tf.YangElemValidateOnly):
    def validate_add(self, data, xml):
        ddata = dns_get_opdata(data)
        ddata.curr_server.name = xml.get_body()
        return

    def getvalue(self, vdata=None):
        return vdata["name"]

    pass

# /system/dns-resolver/server/address
class DNSServerAddress(tf.YangElemValidateOnly):
    def validate_add(self, data, xml):
        ddata = dns_get_opdata(data)
        ddata.curr_server.address = xml.get_body()
        return

    def getvalue(self, vdata=None):
        return vdata["address"]

    pass

# /system/dns-resolver/server/port
class DNSServerPort(tf.YangElemValidateOnly):
    def validate_add(self, data, xml):
        ddata = dns_get_opdata(data)
        ddata.curr_server.port = xml.get_body()
        return

    def getvalue(self, vdata=None):
        return vdata["port"]

    pass

# /system/dns-resolver/server/udp-and-tcp
system_dns_server_ip_children = {
    "address": DNSServerAddress("address", tf.YangType.LEAF),
    "port": DNSServerPort("port", tf.YangType.LEAF),
}

# /system/dns-resolver/server/certificate
class DNSServerCertificate(tf.YangElemValidateOnly):
    def validate_add(self, data, xml):
        v = xml.get_body()
        if v == "x":
            return
        ddata = dns_get_opdata(data)
        ddata.certificate = v
        return

    def getvalue(self, vdata=None):
        # Don't actually return any data
        return "x"

    pass

# /system/dns-resolver/server
system_dns_server_children = {
    "name": DNSServerName("name", tf.YangType.LEAF),
    "udp-and-tcp": tf.YangElemValidateOnly("udp-and-tcp", tf.YangType.CONTAINER,
                                           children=system_dns_server_ip_children,
                                           validate_all=True),
    # FIXME - Add encrypted DNS support, and possibly DNSSEC.
}

# /system/dns-resolver/server
class DNSServer(tf.YangElemValidateOnly):
    def validate_add(self, data, xml):
        ddata = dns_get_opdata(data)
        ddata.curr_server = DNSServerData()
        ddata.add_server.append(ddata.curr_server)
        super().validate_add(data, xml)
        return

    def validate(self, data, origxml, newxml):
        self.validate_add(data, newxml)
        return

    def fetch_index(self, indexname, index, vdata):
        for i in vdata["nameservers"]:
            if i["name"] == index:
                return i
            pass
        return None

    def fetch_full_index(self, vdata):
        return vdata["nameservers"]

    pass

# /system/dns-resolver/options/timeout
class DNSTimeout(tf.YangElemValidateOnly):
    def validate_add(self, data, xml):
        ddata = dns_get_opdata(data)
        ddata.timeout = xml.get_body()
        return

    def getvalue(self, vdata=None):
        return vdata["timeout"]

    pass

# /system/dns-resolver/options/attempts
class DNSAttempts(tf.YangElemValidateOnly):
    def validate_add(self, data, xml):
        ddata = dns_get_opdata(data)
        ddata.attempts = xml.get_body()
        return

    def getvalue(self, vdata=None):
        return vdata["attempts"]

    pass

# /system/dns-resolver/options/use-vc - augment in linux-system
class DNSUseVC(tf.YangElemValidateOnly):
    def validate_add(self, data, xml):
        ddata = dns_get_opdata(data)
        ddata.use_vc = xml.get_body().lower() == "true"
        return

    def getvalue(self, vdata=None):
        return vdata["use-vc"]

    pass

# /system/dns-resolver
class DNSResolver(tf.YangElem):
    def validate_add(self, data, xml):
        if not do_dns:
            raise tf.RPCError("application", "invalid-value", "error",
                              "systemd DNS update not supported here")
        super().validate_add(data, xml)
        return

    def validate(self, data, origxml, newxml):
        if not do_dns:
            raise tf.RPCError("application", "invalid-value", "error",
                              "systemd DNS update not supported here")
        super().validate(data, origxml, newxml)
        return

    def validate_del(self, data, xml):
        # FIXME - maybe delete /etc/resolv.conf?  or fix the YANG?
        raise tf.RPCError("application", "invalid-value", "error",
                          "Cannot delete main DNS data")

    def fetch_resolv_conf(self):
        try:
            f = open(resolvconffile, "r", encoding="utf-8")
        except:
            return None
        srvnum = 1
        srvstr = str(srvnum)
        vdata = { "search": [],
                  "nameservers": [],
                  "timeout": "",
                  "attempts": "",
                  "use-vc": "false" }
        try:
            # Construct a map of all the data and then pass it to super().
            for l in f:
                if l.startswith("search "):
                    vdata["search"] += l.split()[1:]
                elif l.startswith("#name: "):
                    ts = l.split()
                    if len(ts) > 1:
                        srvstr = ts[1]
                        pass
                    pass
                elif l.startswith("nameserver "):
                    ts = l.split()
                    if len(ts) > 1:
                        v = { "name": srvstr,
                              "address": ts[1],
                              "port": "53" }
                        vdata["nameservers"].append(v)
                        srvnum = srvnum + 1
                        srvstr = str(srvnum)
                        pass
                    pass
                elif l.startswith("options"):
                    use_vc_found = "false"
                    for i in l.split()[1:]:
                        if i.startswith("timeout:"):
                            ts = i.split(":")
                            if len(ts) > 1:
                                vdata["timeout"] = ts[1]
                                pass
                            pass
                        elif i.startswith("attempts:"):
                            ts = i.split(":")
                            if len(ts) > 1:
                                vdata["attempts"] = ts[1]
                                pass
                            pass
                        elif i == "use-vc":
                            vdata["use-vc"] = "true"
                            pass
                        pass
                    pass
                pass

            if dnsproxy_supported:
                vdata["nameservers"] = []
                fdnsp = open(dnsproxyconf, "r")
                try:
                    for i in fdnsp:
                        if i.startswith("SERVER_"):
                            s = i.split("=")
                            if len(s) != 2:
                                continue
                            name = s[0][7:]
                            s = s[1].split()
                            if len(s) != 2:
                                continue
                            s = s[1].split(":")
                            if len(s) != 3:
                                continue
                            if len(s[1]) < 3:
                                continue
                            vdata["nameservers"].append({"name": name,
                                                         "address": s[1][2:],
                                                         "port": s[2]})
                            pass
                        pass
                    pass
                finally:
                    fdnsp.close()
                    pass
                pass
            pass
        except Exception as e:
            f.close()
            return None
        f.close()
        return vdata

    def getxml(self, path, indexname=None, index=None, vdata=None):
        if not do_dns:
            return ""

        vdata = self.fetch_resolv_conf()
        if vdata is None:
            return ""
        return super().getxml(path, indexname, index, vdata=vdata)

    def getvalue(self, vdata=None):
        """We fetch the resolv.conf file and process it here ourselves.  None
        of the children will need to handle it.

        """
        if not do_dns:
            return ""

        vdata = self.fetch_resolv_conf()
        if vdata is None:
            return ""
        return super().getvalue(vdata=vdata)

    pass

# /system/dns-resolver/options
system_dns_options_children = {
    "timeout": DNSTimeout("timeout", tf.YangType.LEAF),
    "attempts": DNSAttempts("attempts", tf.YangType.LEAF),
    "use-vc": DNSUseVC("use-vc", tf.YangType.LEAF, namespace=MY_NAMESPACE)
}

# /system/dns-resolver
system_dns_resolver_children = {
    "search": DNSSearch("search", tf.YangType.LEAFLIST, validate_all=True),
    "server": DNSServer("server", tf.YangType.LIST,
                        children=system_dns_server_children,
                        validate_all=True),
    "options": tf.YangElem("options", tf.YangType.CONTAINER,
                           children=system_dns_options_children,
                           validate_all=True),
    "certificate": DNSServerCertificate("certificate", tf.YangType.LEAF,
                                        namespace=MY_NAMESPACE),
}

# The standard pwd methods for python don't have a way to override the
# base location.  Re-implement them with that capability.
def getpwentry(name):
    f = open(passwdfile, "r")
    found = False
    for i in f:
        p = i.split(":")
        if p[0] == name:
            found = True
            break
        pass
    if found:
        if len(p) != 7:
            raise Exception("Password entry doesn't have 6 values")
        # Put sysbase into the home directory
        p[5] = sysbase + p[5]
        return p
    raise Exception("Password entry not found")

def getpwentryall():
    f = open(passwdfile, "r")
    plist = []
    for i in f:
        p = i.split(":")
        if len(p) == 7:
            # Put sysbase into the home directory
            p[5] = sysbase + p[5]
            plist.append(p)
            pass
        pass
    return plist

if sysbase == "":
    useropts = []
else:
    useropts = ["-P", sysbase]
    pass

class UserKey:
    def __init__(self):
        self.op = None
        self.name = None
        self.change_algorithm = False
        self.algorithm = None
        self.change_keydata = False
        self.keydata = None
        return

class UserData(tf.YangElemCommitOnly):
    """This handles the user operation."""
    def __init__(self, name, data):
        super().__init__(name)
        self.data = data
        self.user_op = None
        self.user_name = None
        self.user_password_op = None
        self.user_password = None
        self.user_curr_key = None
        self.user_keys = []
        self.oldkeyfile = False
        self.oldkeyempty = False
        return

    def savepwfile(self):
        if not self.data.oldpwfile:
            if enable_user_update:
                self.data.oldpwfile = True
                self.program_output([cpcmd, passwdfile,
                                     passwdfile + ".keep"])
                if have_shadow:
                    self.program_output([cpcmd, shadowfile,
                                         shadowfile + ".keep"])
                    pass
                pass
            pass
        return

    def savekeyfile(self):
        if not self.oldkeyfile:
            self.home = getpwentry(self.user_name)[5]
            self.keyfile = self.home + "/.ssh/authorized_keys";
            self.program_output([mkdircmd, "-p", self.home + "/.ssh"])
            try:
                self.program_output([cpcmd, self.keyfile,
                                     self.keyfile + ".keep"])
                self.oldkeyfile = True
            except:
                self.oldkeyempty = True
                self.program_output([touchcmd, self.keyfile])
                pass
            pass
        return

    def commit(self, op):
        if self.user_name is None:
            raise Exception("User name not set") # Shouldn't be possible
        self.savepwfile()
        if self.user_op == "del":
            self.program_output([userdel, self.user_name])
        else:
            if self.user_op == "add":
                self.program_output([useradd, "-m"] + useropts +
                                    [self.user_name])
                pass
            if self.user_password_op == "add":
                self.program_output([usermod, "-p", self.user_password]
                                    + useropts + [self.user_name])
                pass
            for i in self.user_keys:
                self.savekeyfile()
                if i.op == "del":
                    self.program_output([sedcmd, "-i", "/" + i.name + "/d",
                                         self.keyfile])
                elif i.op == "add":
                    # keydata will be none on a change that's not
                    # changing anything.
                    if i.keydata is not None:
                        # First delete the old one.
                        self.program_output([sedcmd, "-i", "/" + i.name + "/d",
                                             self.keyfile])
                        f = open(self.keyfile, "a")
                        f.write(str(i.algorithm) + " "
                                + str(i.keydata) + " "
                                + str(i.name) + "\n")
                        f.close()
                        pass
                    pass
                pass
            pass
        return

    def commit_done(self, op):
        if self.oldkeyfile:
            self.program_output([rmcmd, "-f", self.keyfile + ".keep"])
        return

    def revert(self, op):
        if self.oldkeyfile:
            if self.oldkeyempty:
                self.program_output([rmcmd, self.keyfile])
            else:
                self.program_output([mvcmd, "-f", self.keyfile + ".keep",
                                     self.keyfile])
                pass
            pass
        return

    def user_exists(self):
        try:
            getpwentry(self.user_name)
        except:
            return False
        return True

# /system/authentication/user/name
class UserName(tf.YangElemValidateOnly):
    def validate_add(self, data, xml):
        data.userCurrU.user_name = xml.get_body()
        if data.userCurrU.user_op == "add" and data.userCurrU.user_exists():
            raise tf.RPCError("application", "invalid-value", "error",
                              "User " + data.userCurrU.user_name +
                              " already exists")
        return

    def validate_del(self, data, xml):
        data.userCurrU.user_name = xml.get_body()
        if not data.userCurrU.user_exists():
            raise tf.RPCError("application", "invalid-value", "error",
                              "User " + data.userCurrU.user_name +
                              " not present")
        return

    def validate(self, data, origxml, newxml):
        data.userCurrU.user_name = newxml.get_body()
        if not data.userCurrU.user_exists():
            raise tf.RPCError("application", "invalid-value", "error",
                              "User " + data.userCurrU.user_name +
                              " not present")
        return

    def getvalue(self, vdata=None):
        return vdata[0]

# /system/authentication/user/password
class UserPassword(tf.YangElemValidateOnly):
    def validate_add(self, data, xml):
        if not allow_user_key_change:
            raise tf.RPCError("application", "invalid-value", "error",
                              "User password change not allowed")
        data.userCurrU.user_password_op = "add"
        v = xml.get_body()
        if v == "x":
            return
        data.userCurrU.user_password = v
        return

    def validate_del(self, data, xml):
        if data.userCurrU.user_op != "del":
            raise tf.RPCError("application", "invalid-value", "error",
                              "User password delete not allowed")
        data.userCurrU.user_password_op = "del"
        return

    def validate(self, data, origxml, newxml):
        # Don't have to worry about the password on a delete.
        if newxml.get_flags(clixon_beh.XMLOBJ_FLAG_CHANGE):
            if not allow_user_key_change:
                raise tf.RPCError("application", "invalid-value", "error",
                                  "User password change not allowed")
            v = xml.get_body()
            if v == "x":
                return
            data.userCurrU.user_password_op = "add" # Add and change are same
            data.userCurrU.user_password = v
            pass
        return

    def getvalue(self, vdata=None):
        return "x" # Never return actual password data.

# /system/authentication/user/authorized-key/name
class UserAuthkeyName(tf.YangElemValidateOnly):
    def validate_add(self, data, xml):
        data.userCurrU.user_curr_key.name = xml.get_body()
        return

    # We need the name for deletion.
    def validate_del(self, data, xml):
        data.userCurrU.user_curr_key.name = xml.get_body()
        return

    def getvalue(self, vdata=None):
        return vdata[2]

# /system/authentication/user/authorized-key/algorithm
class UserAuthkeyAlgo(tf.YangElemValidateOnly):
    def validate_add(self, data, xml):
        data.userCurrU.user_curr_key.algorithm = xml.get_body()
        return

    def validate(self, data, origxml, newxml):
        if newxml.get_flags(clixon_beh.XMLOBJ_FLAG_CHANGE):
            data.userCurrU.user_curr_key.algorithm = xml.get_body()
            data.userCurrU.user_curr_key.change_algorithm = True
            pass
        return

    def getvalue(self, vdata=None):
        return vdata[0]

# /system/authentication/user/authorized-key/key-data
class UserAuthkeyKeyData(tf.YangElemValidateOnly):
    def validate_add(self, data, xml):
        v = xml.get_body()
        if v == "x":
            return
        data.userCurrU.user_curr_key.keydata = v
        return

    def validate(self, data, origxml, newxml):
        if newxml.get_flags(clixon_beh.XMLOBJ_FLAG_CHANGE):
            v = xml.get_body()
            if v == "x":
                return
            data.userCurrU.user_curr_key.keydata = v
            data.userCurrU.user_curr_key.change_keydata = True
            pass
        return

    def getvalue(self, vdata=None):
        return "x" # Never return actual key data.

# /system/authentication/user/authorized-key
class UserAuthkey(tf.YangElem):
    """This handles the user authorized key."""
    def validate_add(self, data, xml):
        if not allow_user_key_change:
            raise tf.RPCError("application", "invalid-value", "error",
                              "User key addition not allowed")
        data.userCurrU.user_curr_key = UserKey()
        data.userCurrU.user_keys.append(data.userCurrU.user_curr_key)
        data.userCurrU.user_curr_key.op = "add"
        super().validate_add(data, xml)
        return

    def validate_del(self, data, xml):
        if not allow_user_key_change:
            raise tf.RPCError("application", "invalid-value", "error",
                              "User key deletion not allowed")
        data.userCurrU.user_curr_key = UserKey()
        data.userCurrU.user_keys.append(data.userCurrU.user_curr_key)
        data.userCurrU.user_curr_key.op = "del"
        super().validate_del(data, xml)
        return

    def validate(self, data, origxml, newxml):
        self.validate_add(data, newxml)
        return

    def fetch_index(self, indexname, index, vdata):
        for i in self.fetch_full_index(vdata):
            if i[2] == index:
                return i
            pass
        return None

    def fetch_full_index(self, vdata):
        try:
            f = open(vdata[5] + "/.ssh/authorized_keys", "r")
        except:
            return []
        idx = []
        for i in f:
            i = i.split()
            if len(i) >= 3:
                idx.append(i)
                pass
            pass
        f.close()
        return idx

    pass

# /system/authentication/user/authorized-key
system_user_authkey_children = {
    "name": UserAuthkeyName("name", tf.YangType.LEAF),
    "algorithm": UserAuthkeyAlgo("algorithm", tf.YangType.LEAF),
    "key-data": UserAuthkeyKeyData("key-data", tf.YangType.LEAF),
}

# /system/authentication/user
class User(tf.YangElem):
    def start(self, data, op):
        v = UserData("user", data)
        new_op = data.add_op(v, "user", v)
        data.userCurrU = new_op.value
        data.userCurrU.user_op = op
        return

    def validate_add(self, data, xml):
        if not allow_user_add_del:
            raise tf.RPCError("application", "invalid-value", "error",
                              "User addition not allowed")
        self.start(data, "add")
        super().validate_add(data, xml)
        return

    def validate_del(self, data, xml):
        if not allow_user_add_del:
            raise tf.RPCError("application", "invalid-value", "error",
                              "User deletion not allowed")
        self.start(data, "del")
        super().validate_del(data, xml)
        return

    def validate(self, data, origxml, newxml):
        self.start(data, None)
        super().validate(data, origxml, newxml)
        return

    def fetch_index(self, indexname, index, vdata):
        return getpwentry(index)

    def fetch_full_index(self, vdata):
        return getpwentryall()

    pass

# /system/authentication/user
system_user_children = {
    "name": UserName("name", tf.YangType.LEAF),
    "password": UserPassword("password", tf.YangType.LEAF),
    "authorized-key": UserAuthkey("authorized-key", tf.YangType.LIST,
                                  children = system_user_authkey_children,
                                  validate_all=True),
}

# /system/authentication
system_authentication_children = {
    "user-authentication-order": tf.YangElemConfigOnly("user-authentication-order"),
    "user": User("user", tf.YangType.LIST, children = system_user_children,
                 validate_all=True),
}

class NTPServerData:
    def __init__(self):
        self.op = None
        self.name = None
        self.address = None
        self.port = "123"
        self.ntsport = "4460"
        self.assoc_type = "server" # server, peer, or pool
        self.iburst = False
        self.prefer = False
        self.is_udp = True
        self.certificate = None
        return

    pass

class NTPData(tf.YangElemCommitOnly):
    def __init__(self, name):
        super().__init__(name)
        self.enabled = True
        self.servers = []
        return

    def commit(self, op):
        if False:
            print("NTP")
            print("  enabled: " + str(self.enabled))
            for i in self.servers:
                print("  server(" + str(i.op) + "): " + str(i.name))
                print("    name: " + str(i.name))
                print("    is_udp: " + str(i.is_udp))
                print("    address: " + str(i.address))
                print("    port: " + str(i.port))
                print("    ntsport: " + str(i.ntsport))
                print("    cert: " + str(i.certificate))
                print("    assoc_type: " + str(i.assoc_type))
                print("    iburst: " + str(i.iburst))
                print("    prefer: " + str(i.prefer))
                pass
            pass
        for i in self.servers:
            if i.op == "add" or i.op == "change":
                f = open(chronydir + "/sources.d/" + i.name + ".sources", "w")
                try:
                    f.write(i.assoc_type + " " + i.address + " port " + i.port)
                    if not i.is_udp:
                        f.write(" nts ntsport " + i.ntsport)
                        pass
                    if i.iburst:
                        f.write(" iburst")
                    if i.prefer:
                        f.write(" prefer")
                    f.write("\n")
                finally:
                    f.close()
                    pass
                if i.certificate is None:
                    # No certificate, delete it.
                    self.program_output([rmcmd, "-f",
                                         (chronydir + "/ntstrustedcerts/" +
                                          i.name + ".crt")])
                elif i.certificate != "x":
                    # A certificate with contents "x" is invalid, we use that
                    # to mark that the certificate was just fetched and then
                    # re-written, so we don't change it.
                    f = open(chronydir + "/ntstrustedcerts/" + i.name + ".crt",
                             "w")
                    try:
                        f.write(i.certificate)
                        f.write("\n")
                    finally:
                        f.close()
                        pass
                    pass
                pass
            else:
                self.program_output([rmcmd, "-f",
                                     (chronydir + "/sources.d/" + i.name +
                                      ".sources")])
                self.program_output([rmcmd, "-f",
                                     (chronydir + "/ntstrustedcerts/" +
                                      i.name + ".crt")])
                pass
            pass
        return

    def revert(self, op):
        self.program_output([rmcmd, "-rf", chronydir])
        self.program_output([mvcmd, chronydir + ".old", chronydir])
        return

    def commit_done(self, op):
        self.program_output([rmcmd, "-rf", chronydir + ".old"])
        if sysbase == "":
            self.program_output([chronyccmd, "reload", "sources"])
            pass
        return

    pass

# /system/ntp/enabled
class NTPEnabled(tf.YangElem):
    def validate_add(self, data, xml):
        data.userNTP.enabled = xml.get_body()
        return

    def validate(self, data, origxml, newxml):
        return self.validate_add(data, newxml)

    def getvalue(self, vdata):
        # FIXME = do enable/disable?
        return "true"

    pass

# /system/ntp/server/name
class NTPServerName(tf.YangElem):
    def validate_add(self, data, xml):
        data.userNTP.curr_server.name = xml.get_body()
        return

    def validate_del(self, data, xml):
        # Need the name when deleting
        return self.validate_add(data, xml)

    def validate(self, data, origxml, newxml):
        return self.validate_add(data, newxml)

    def getvalue(self, vdata):
        return vdata.name

    pass

# /system/ntp/server/udp/address
class NTPServerUDPAddress(tf.YangElem):
    def validate_add(self, data, xml):
        data.userNTP.curr_server.address = xml.get_body()
        return

    def validate_del(self, data, xml):
        # Nothing to do on delete
        return

    def validate(self, data, origxml, newxml):
        return self.validate_add(data, newxml)

    def getvalue(self, vdata):
        return vdata.address

    pass

# /system/ntp/server/udp/port
class NTPServerUDPPort(tf.YangElem):
    def validate_add(self, data, xml):
        data.userNTP.curr_server.port = xml.get_body()
        return

    def validate_del(self, data, xml):
        # Nothing to do on delete
        return

    def validate(self, data, origxml, newxml):
        return self.validate_add(data, newxml)

    def getvalue(self, vdata):
        return vdata.port

    pass

# /system/ntp/server/tcp/address
class NTPServerNTSAddress(tf.YangElem):
    def validate_add(self, data, xml):
        data.userNTP.curr_server.address = xml.get_body()
        return

    def validate_del(self, data, xml):
        # Nothing to do on delete
        return

    def validate(self, data, origxml, newxml):
        return self.validate_add(data, newxml)

    def getvalue(self, vdata):
        return vdata.address

    pass

# /system/ntp/server/tcp/port
class NTPServerNTSPort(tf.YangElem):
    def validate_add(self, data, xml):
        data.userNTP.curr_server.ntsport = xml.get_body()
        return

    def validate_del(self, data, xml):
        # Nothing to do on delete
        return

    def validate(self, data, origxml, newxml):
        return self.validate_add(data, newxml)

    def getvalue(self, vdata):
        return vdata.ntsport

    pass

# /system/ntp/server/tcp/certificate
class NTPServerNTSCertificate(tf.YangElem):
    def validate_add(self, data, xml):
        data.userNTP.curr_server.certificate = xml.get_body()
        return

    def validate_del(self, data, xml):
        # Nothing to do on delete
        return

    def validate(self, data, origxml, newxml):
        return self.validate_add(data, newxml)

    def getvalue(self, vdata):
        return "x"

    pass

# /system/ntp/server/association-type
class NTPServerAsocType(tf.YangElem):
    def validate_add(self, data, xml):
        data.userNTP.curr_server.asoc_type = xml.get_body()
        return

    def validate_del(self, data, xml):
        # Nothing to do on delete
        return

    def validate(self, data, origxml, newxml):
        return self.validate_add(data, newxml)

    def getvalue(self, vdata):
        return vdata.assoc_type

    pass

# /system/ntp/server/iburst
class NTPServerIBurst(tf.YangElem):
    def validate_add(self, data, xml):
        v = xml.get_body()
        data.userNTP.curr_server.iburst = v == "true"
        return

    def validate_del(self, data, xml):
        # Nothing to do on delete
        return

    def validate(self, data, origxml, newxml):
        return self.validate_add(data, newxml)

    def getvalue(self, vdata):
        if vdata.iburst:
            return "true"
        return "false"

    pass

# /system/ntp/server/prefer
class NTPServerPrefer(tf.YangElem):
    def validate_add(self, data, xml):
        v = xml.get_body()
        data.userNTP.curr_server.prefer = v == "true"
        return

    def validate_del(self, data, xml):
        # Nothing to do on delete
        return

    def validate(self, data, origxml, newxml):
        return self.validate_add(data, newxml)

    def getvalue(self, vdata):
        if vdata.prefer:
            return "true"
        return "false"

    pass

# /system/ntp/server/udp
class NTPUDPServer(tf.YangElem):
    # is_udp is true by default, use the default validation.

    def getvalue(self, vdata):
        if not vdata.is_udp:
            return ""
        return super().getvalue(vdata)

    pass

# /system/ntp/server/ntp
class NTPNTSServer(tf.YangElem):
   # Set is_udp False for NTS

    def validate_add(self, data, xml):
        data.userNTP.curr_server.is_udp = False
        super().validate_add(data, xml)
        return

    def validate(self, data, origxml, newxml):
        data.userNTP.curr_server.is_udp = False
        super().validate(data, origxml, newxml)
        return

    def getvalue(self, vdata):
        if vdata.is_udp:
            return ""
        return super().getvalue(vdata)

    pass

# /system/ntp/server
class NTPServer(tf.YangElem):
    def start(self, data, op):
        data.userNTP.curr_server = NTPServerData()
        data.userNTP.curr_server.op = op
        data.userNTP.servers.append(data.userNTP.curr_server)
        return

    def validate_data(self, data):
        s = data.userNTP.curr_server
        if not s.is_udp:
            if s.assoc_type != "server":
                raise tf.RPCError("application", "invalid-value", "error",
                                  "NTP with NTS must be a server assoc_type.")
            pass
        return

    def validate_add(self, data, xml):
        self.start(data, "add")
        super().validate_add(data, xml)
        self.validate_data(data)
        return

    def validate_del(self, data, xml):
        self.start(data, "del")
        super().validate_del(data, xml)
        return

    def validate(self, data, origxml, newxml):
        self.start(data, "change")
        super().validate(data, origxml, newxml)
        self.validate_data(data)
        return

    valid_assoc_types = ["server", "peer", "pool"]

    def read_chrony_data(self):
        servers = []
        for i in os.listdir(chronydir + "/sources.d"):
            if not i.endswith(".sources"):
                continue
            f = open(chronydir + "/sources.d/" + i)
            try:
                s = NTPServerData()
                s.name = i[:len(i) - 8]
                for l in f:
                    l = l.split()
                    if l[0] not in self.valid_assoc_types:
                        raise Exception() # bail
                    s.assoc_type = l[0]
                    s.address = l[1]
                    i = 2
                    while i < len(l):
                        if l[i] == "port":
                            i += 1
                            s.port = l[i]
                        elif l[i] == "ntsport":
                            i += 1
                            s.ntsport = l[i]
                        elif l[i] == "iburst":
                            s.iburst = True
                        elif l[i] == "nts":
                            s.is_udp = False
                        elif l[i] == "prefer":
                            s.prefer = True
                            pass
                        i += 1
                        pass
                    break # Only process the first line.
                servers.append(s)
                pass
            except:
                pass # Nothing to do
            finally:
                f.close()
            pass
        return servers

    def fetch_index(self, indexname, index, vdata):
        servers = self.read_chrony_data()
        for i in servers:
            if i.name == index:
                return i
            pass
        return None

    def fetch_full_index(self, vdata):
        return self.read_chrony_data()

    pass

# /system/ntp/server/udp
system_ntp_server_udp_children = {
    "address": NTPServerUDPAddress("address", tf.YangType.LEAF),
    "port": NTPServerUDPPort("port", tf.YangType.LEAF),
}

# /system/ntp/server/nts
system_ntp_server_nts_children = {
    "address": NTPServerNTSAddress("address", tf.YangType.LEAF),
    "port": NTPServerUDPPort("port", tf.YangType.LEAF),
    "ntsport": NTPServerNTSPort("ntsport", tf.YangType.LEAF),
    "certificate": NTPServerNTSCertificate("certificate", tf.YangType.LEAF),
}

# /system/ntp/server
system_ntp_server_children = {
    "name": NTPServerName("name", tf.YangType.LEAF),
    "udp": NTPUDPServer("udp", tf.YangType.CONTAINER,
                                   children = system_ntp_server_udp_children,
                                   validate_all = True),
    "nts": NTPNTSServer("nts", tf.YangType.CONTAINER,
                        children = system_ntp_server_nts_children,
                        validate_all = True, namespace = MY_NAMESPACE),
    "association-type": NTPServerAsocType("association-type", tf.YangType.LEAF),
    "iburst": NTPServerIBurst("iburst", tf.YangType.LEAF),
    "prefer": NTPServerPrefer("prefer", tf.YangType.LEAF),
}

# /system/ntp
class NTP(tf.YangElem):
    def start(self, data):
        self.program_output([rmcmd, "-rf", chronydir + ".old"])
        self.program_output([cpcmd, "-a", chronydir, chronydir + ".old"])
        v = NTPData("ntp")
        new_op = data.add_op(v, "ntp", v)
        data.userNTP = v
        return

    def validate_add(self, data, xml):
        self.start(data)
        super().validate_add(data, xml)
        return

    def validate_del(self, data, xml):
        raise tf.RPCError("application", "invalid-value", "error",
                          "Cannot delete NTP data.")

    def validate(self, data, origxml, newxml):
        self.start(data)
        super().validate(data, origxml, newxml)
        return

    pass

# /system/ntp
system_ntp_children = {
    "enabled": NTPEnabled("enabled", tf.YangType.LEAF),
    "server": NTPServer("server", tf.YangType.LIST,
                        children = system_ntp_server_children,
                        validate_all = True)
}

# /system
system_children = {
    "contact": tf.YangElemConfigOnly("contact"),
    "hostname": Hostname("hostname", tf.YangType.LEAF),
    "location": tf.YangElemConfigOnly("location"),
    "clock": tf.YangElem("clock", tf.YangType.CONTAINER, system_clock_children),
    "ntp": NTP("ntp", tf.YangType.CONTAINER, children = system_ntp_children),
    "dns-resolver": DNSResolver("dns-resolver", tf.YangType.CONTAINER,
                                children = system_dns_resolver_children,
                                validate_all = True),
    "authentication": tf.YangElem("authentication", tf.YangType.CONTAINER,
                                  children = system_authentication_children),
}

# /system-state/platform/*
class SystemStatePlatform(tf.YangElemValueOnly):
    def getvalue(self, vdata=None):
        if self.name == "os-name":
            opt = "-s"
        elif self.name == "os-release":
            opt = "-r"
        elif self.name == "os-version":
            opt = "-v"
        elif self.name == "machine":
            opt = "-m"
        else:
            raise Exception("Internal error getting uname")
        return self.program_output(["/bin/uname", opt]).strip()

    pass

# /system-state/clock/*
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

# /system-state/platform
system_state_platform_children = {
    "os-name": SystemStatePlatform("os-name", tf.YangType.LEAF),
    "os-release": SystemStatePlatform("os-release", tf.YangType.LEAF),
    "os-version": SystemStatePlatform("os-version", tf.YangType.LEAF),
    "machine": SystemStatePlatform("machine", tf.YangType.LEAF)
}

# /system-state/clock
system_state_clock_children = {
    "current-datetime": SystemStateClock("current-datetime", tf.YangType.LEAF),
    "boot-datetime": SystemStateClock("boot-datetime", tf.YangType.LEAF)
}

# /system-state
system_state_children = {
    "platform": tf.YangElem("platform", tf.YangType.CONTAINER,
                            system_state_platform_children),
    "clock": tf.YangElem("clock", tf.YangType.CONTAINER,
                         system_state_clock_children)
}

class Handler(tf.TopElemHandler, tf.ProgOut):
    # FIXME - this is a hack for now
    first_call_done = False

    def exit(self):
        self.p = None # Break circular dependency
        return 0;

    def begin(self, t):
        rv = super().begin(t)
        if rv < 0:
            return rv
        data = t.get_userdata()
        data.userDNSOp = None # Replaced when DNS operations are done.
        data.userCurrU = None # Replaced by user operations
        data.oldpwfile = False # Are the old pw/shadow files set
        data.userNTP = None # Replaced by NTP operations
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

    # The password file is saved if a user modification is done.  This is
    # done once for all users, so we have to wait until the very end to
    # delete the backup password file.
    def end(self, t):
        data = t.get_userdata()
        if data.oldpwfile:
            self.program_output([rmcmd, "-f", passwdfile + ".keep"])
            if have_shadow:
                self.program_output([rmcmd, "-f", shadowfile + ".keep"])
        return 0

    # If we failed, revert the password file from the backup.
    def abort(self, t):
        data = t.get_userdata()
        if data.oldpwfile:
            self.program_output([mvcmd, "-f", passwdfile + ".keep",
                                 passwdfile])
            if have_shadow:
                self.program_output([mvcmd, "-f", shadowfile + ".keep",
                                     shadowfile])
        return 0

    def statedata(self, nsc, xpath):
        rv = super().statedata(nsc, xpath)
        if False:
            print("X: " + str(rv))
            pass
        return rv

    def system_only(self, nsc, xpath):
        if xpath == "/":
            rv = super().statedata(nsc, "/system")
            print("Y: " + str(rv))
            return rv
        return super().statedata(nsc, xpath)

    pass

children = {
    "system": tf.YangElem("system", tf.YangType.CONTAINER, system_children,
                          namespace = IETF_SYSTEM_NAMESPACE),
    "system-state": tf.YangElem("system-state", tf.YangType.CONTAINER,
                                system_state_children,
                                namespace = IETF_SYSTEM_NAMESPACE),
}
handler = Handler("linux-system", children)
handler.p = clixon_beh.add_plugin(handler.name, IETF_SYSTEM_NAMESPACE, handler)

class SetTimeHandler(tf.RPC):
    def rpc(self, x, username):
        s = '<rpc-reply xmlns="' + clixon_beh.NETCONF_BASE_NAMESPACE + '">'
        if using_ntp:
            s += ("<rpc-error>"
                  + "<error-type>application</error-type>"
                  + "<error-tag>ntp-active</error-tag>"
                  + "<error-severity>error</error-severity>"
                  + "</rpc-error>")
        else:
            d = x.find("current-datetime")
            if d is None:
                raise Exception("current-datetime not in set time rpc")
            self.do_priv(d.get_body())
            pass
        s += '</rpc-reply>'
        return (0, s)

    def priv(self, op):
        self.program_output([datecmd, "-s", op])
        return

    pass

clixon_beh.add_rpc_callback("set-current-datetime", IETF_SYSTEM_NAMESPACE,
                            SetTimeHandler())

class RestartHandler(tf.RPC):
    def rpc(self, x, username):
        self.do_priv("")
        s = '<rpc-reply xmlns="' + clixon_beh.NETCONF_BASE_NAMESPACE + '">'
        s += '</rpc-reply>'
        return (0, s)

    def priv(self, op):
        self.program_output(["/sbin/reboot"])
        return

    pass

clixon_beh.add_rpc_callback("system-restart", IETF_SYSTEM_NAMESPACE,
                            RestartHandler())


class ShutdownHandler(tf.RPC):
    def rpc(self, x, username):
        self.do_priv("")
        s = '<rpc-reply xmlns="' + clixon_beh.NETCONF_BASE_NAMESPACE + '">'
        s += '</rpc-reply>'
        return (0, s)

    def priv(self, op):
        self.program_output(["/sbin/shutdown", "now"])
        return

    pass

clixon_beh.add_rpc_callback("system-shutdown", IETF_SYSTEM_NAMESPACE,
                            ShutdownHandler())
