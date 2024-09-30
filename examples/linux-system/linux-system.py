
import os
import shlex
import clixon_beh
import clixon_beh.transaction_framework as tf

MY_NAMESPACE = "http://linux.org"
IETF_SYSTEM_NAMESPACE = "urn:ietf:params:xml:ns:yang:ietf-system"

# Enable various password operations
allow_user_add_del = True      # Add/delete users allowed?
allow_user_pw_change = True    # User password changes allowed?
allow_user_key_change = True   # SSH authorized key changes allowed?
enable_user_update = True      # Allow the password files to be chagned at all.
useradd = "/usr/sbin/useradd"
userdel = "/usr/sbin/userdel"
usermod = "/usr/sbin/usermod"
have_shadow = True
passwdfile = "/etc/passwd"
shadowfile = "/etc/shadow"

# NTP handling
using_ntp = True

# Various commands
cpcmd = "/bin/cp"
touchcmd = "/bin/touch"
lscmd = "/bin/ls"
lncmd = "/bin/ln"
mvcmd = "/bin/mv"
rmcmd = "/bin/rm"
catcmd = "/bin/cat"
datecmd = "/bin/date"
hostnamecmd = "/bin/hostname"
hostnamefile = "/etc/hostname"
localtimefile = "/etc/localtime"
timezonefile = "/etc/timezone"
zoneinfodir = "/usr/share/zoneinfo/"
resolvconffile = "/etc/resolv.conf"

# For testing, to store the files elsewhere to avoid updating the main
# system data
sysbase = ""

# Pull the feature value from the config.
old_dns_supported = clixon_beh.is_feature_set("linux-system", "old-dns")

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
        f = open(sysbase + hostnamefile, "w")
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
        if not os.path.exists(sysbase + zoneinfodir + value):
            raise tf.RPCError("application", "invalid-value", "error",
                              value + " not a valid timezone")
        data.add_op(self, None, value)
        return

    def commit(self, op):
        oldlocaltime = None
        try:
            lt = self.program_output([lscmd, "-l",
                                      sysbase + localtimefile])
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
                    self.program_output([lncmd, "-sf",
                                         sysbase + zoneinfodir + "GMT",
                                         sysbase + localtimefile])
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
            f = open(sysbase + timezonefile, "w")
            f.write(value + "\n")
            f.close()
            self.program_output([lncmd, "-sf",
                                 sysbase + zoneinfodir + value,
                                 sysbase + localtimefile])
            pass
        return

    def getvalue(self, vdata=None):
        if not self.is_name:
            return ""
        try:
            s = self.program_output([catcmd, sysbase + timezonefile]).strip()
        except:
            s = "GMT"
            pass
        return s

# /system/clock
system_clock_children = {
    "timezone-name": TimeZone("timezone-name", is_name=True),
    "timezone-utc-offset": TimeZone("timezone-utc-offset", is_name=False),
}

# DNS can be disabled in the linux-system yang file, but this is here
# for old-style DNS.  If you are using resolvconf, disable it in the
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

    def priv(self, op):
        ddata = op.userData
        if op.revert:
            os.remove(sysbase + resolvconffile + ".tmp")
        elif op.done:
            os.replace(sysbase + resolvconffile + ".tmp",
                       sysbase + resolvconffile)
        else:
            # Create a file to hold the data.  We move the file over when
            # done.
            # FIXME - no handling for port or certificate in the default
            # way of doing this.
            f = open(sysbase + resolvconffile + ".tmp", "w")
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
        self.certificate = None

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
        return

    pass

def dns_get_opdata(data):
    """If a DNS operation is already registered in the op queue, just
    return its data.  Otherwisse add a DNS operation and return its
    data.

    """
    if data.userDNSOp is None:
        data.userDNSOp = data.add_op(DNSHandler("dns"), "dns", None)
        data.userDNSOp.userData = DNSData()
    return data.userDNSOp.userData

# /system/dns-resolver/search
class DNSSearch(tf.YangElemValidateOnly):
    def validate_add(self, data, xml):
        ddata = dns_get_opdata(data)
        ddata.add_search.append(xml.get_body())

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
        ddata = dns_get_opdata(data)
        ddata.curr_server.certificate = xml.get_body()
        return

    def getvalue(self, vdata=None):
        # We have to add our own namespace, so set wrapxml to false for
        # this class and do it ourself.  However, we don't actually
        # return any data.
        return ("<certificate xmlns=\"" + tf.xmlescape(MY_NAMESPACE) + "\">" +
                "x" + "</certificate>")

    pass

# /system/dns-resolver/server
system_dns_server_children = {
    "name": DNSServerName("name", tf.YangType.LEAF),
    "udp-and-tcp": tf.YangElemValidateOnly("udp-and-tcp", tf.YangType.CONTAINER,
                                           children=system_dns_server_ip_children,
                                           validate_all=True),
    "certificate": DNSServerCertificate("certificate", tf.YangType.LEAF,
                                        wrapxml = False, xmlprocvalue = False),
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
        # We have to add our own namespace, so set wrapxml to false for
        # this class and do it ourself.
        return ("<use-vc xmlns=\"" + MY_NAMESPACE + "\">" +
                vdata["use-vc"] + "</use-vc>")

    pass

# /system/dns-resolver
class DNSResolver(tf.YangElem):
    def validate_add(self, data, xml):
        if not old_dns_supported:
            raise tf.RPCError("application", "invalid-value", "error",
                              "systemd DNS update not supported here")
        super().validate_add(data, xml)
        return

    def validate(self, data, origxml, newxml):
        if not old_dns_supported:
            raise tf.RPCError("application", "invalid-value", "error",
                              "systemd DNS update not supported here")
        super().validate(data, origxml, newxml)
        return

    def validate_del(self, data, xml):
        # FIXME - maybe delete /etc/resolv.conf?  or fix the YANG?
        raise tf.RPCError("application", "invalid-value", "error",
                          "Cannot delete main DNS data")

    def fetch_resolv_conf(self):
        vdata = None
        try:
            f = open(sysbase + resolvconffile, "r", encoding="utf-8")
        except:
            return ""
        try:
            # Construct a map of all the data and then pass it to super().
            srvnum = 1
            srvstr = str(srvnum)
            vdata = { "search": [],
                      "nameservers": [],
                      "timeout": "",
                      "attempts": "",
                      "use-vc": "false" }
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
            pass
        except:
            f.close()
            return ""
        f.close()
        return vdata

    def getxml(self, path, namespace=None, indexname=None, index=None,
               vdata=None):
        if not old_dns_supported:
            return ""

        vdata = self.fetch_resolv_conf()
        if vdata is None:
            return ""
        return super().getxml(path, namespace, indexname, index, vdata=vdata)

    def getvalue(self, vdata=None):
        """We fetch the resolv.conf file and process it here ourselves.  None
        of the children will need to handle it.

        """
        if not old_dns_supported:
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
    "use-vc": DNSUseVC("use-vc", tf.YangType.LEAF,
                       wrapxml=False, xmlprocvalue=False),
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
}

# The standard pwd methods for python don't have a way to override the
# base location.  Re-implement them with that capability.
def getpwentry(name):
    f = open(sysbase + passwdfile, "r")
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
        p[5] = sysbase + p[5]
        return p
    raise Exception("Password entry not found")

def getpwentryall():
    f = open(sysbase + passwdfile, "r")
    plist = []
    for i in f:
        p = i.split(":")
        if len(p) == 7:
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
    def __init(self):
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
                self.program_output([cpcmd, sysbase + passwdfile,
                                     sysbase + passwdfile + ".keep"])
                if have_shadow:
                    self.program_output([cpcmd, sysbase + shadowfile,
                                         sysbase + shadowfile + ".keep"])
                    pass
                pass
            pass
        return

    def savekeyfile(self):
        if not self.oldkeyfile:
            self.home = getpwentry(self.user_name)[5]
            self.keyfile = self.home + "/.ssh/authorized_keys";
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
                # Always delete the old key
                program_output(["sed", "-i", "/" + i.name + "/d",
                                self.keyfile])
                if i.op == "add":
                    f = open(self.keyfile, "a")
                    f.write(str(i.algorithm) + " "
                            + str(i.keydata) + " "
                            + str(i.name) + "\n")
                    f.close()
                    pass
                pass
            pass
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
        data.userCurrU.user_password = xml.get_body()
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
            data.userCurrU.user_password_op = "add" # Add and change are same
            data.userCurrU.user_password = xml.get_body()
            pass
        return

    def getvalue(self, vdata=None):
        return "x" # Never return actual password data.

# /system/authentication/user/authorized-key/name
class UserAuthkeyName(tf.YangElemValidateOnly):
    def validate_add(self, data, xml):
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
        data.userCurrU.user_curr_key.keydata = xml.get_body()
        return

    def validate(self, data, origxml, newxml):
        if newxml.get_flags(clixon_beh.XMLOBJ_FLAG_CHANGE):
            data.userCurrU.user_curr_key.keydata = xml.get_body()
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
        data.userCurrU.user_keys.append(data.userCurrU.user_curr_key)
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
        data.userCurrU = UserData("user", data)
        data.add_op(data.userCurrU, "user", None)
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
    "user": User("user", tf.YangType.LIST, children = system_user_children),
}

class NTPServerData:
    def __init__(self):
        self.op = None
        self.name = None
        self.address = None
        self.port = "123"
        self.port_set = False
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

    # FIXME - really implement this
    def commit(self, op):
        print("NTP")
        print("  enabled: " + str(self.enabled))
        for i in self.servers:
            print("  server(" + str(i.op) + "): " + str(i.name))
            print("    name: " + str(i.name))
            print("    is_udp: " + str(i.is_udp))
            print("    address: " + str(i.address))
            print("    port: " + str(i.port))
            print("    cert: " + str(i.certificate))
            print("    assoc_type: " + str(i.assoc_type))
            print("    iburst: " + str(i.iburst))
            print("    prefer: " + str(i.prefer))

    def revert(self, op):
        return

    pass

# /system/ntp/enabled
class NTPEnabled(tf.YangElemValidateOnly):
    def validate_add(self, data, xml):
        data.userNTP.enabled = xml.get_body()
        return

    pass

# /system/ntp/server/name
class NTPServerName(tf.YangElemValidateOnly):
    def validate_add(self, data, xml):
        data.userNTP.curr_server.name = xml.get_body()
        return

    pass

# /system/ntp/server/udp/address
class NTPServerUDPAddress(tf.YangElemValidateOnly):
    def validate_add(self, data, xml):
        data.userNTP.curr_server.address = xml.get_body()
        return

    pass

# /system/ntp/server/udp/port
class NTPServerUDPPort(tf.YangElemValidateOnly):
    def validate_add(self, data, xml):
        data.userNTP.curr_server.port = xml.get_body()
        data.userNTP.curr_server.port_set = True
        return

    pass

# /system/ntp/server/tcp/address
class NTPServerNTSAddress(tf.YangElemValidateOnly):
    def validate_add(self, data, xml):
        data.userNTP.curr_server.is_udp = False
        data.userNTP.curr_server.address = xml.get_body()
        if not data.userNTP.curr_server.port_set:
            data.userNTP.curr_server.port = 4460
            pass
        return

    pass

# /system/ntp/server/tcp/port
class NTPServerNTSPort(tf.YangElemValidateOnly):
    def validate_add(self, data, xml):
        data.userNTP.curr_server.is_udp = False
        data.userNTP.curr_server.port = xml.get_body()
        data.userNTP.curr_server.port_set = True
        return

    pass

# /system/ntp/server/tcp/certificate
class NTPServerNTSCertificate(tf.YangElemValidateOnly):
    def validate_add(self, data, xml):
        data.userNTP.curr_server.is_udp = False
        data.userNTP.curr_server.certificate = xml.get_body()
        return

    pass

# /system/ntp/server/association-type
class NTPServerAsocType(tf.YangElemValidateOnly):
    def validate_add(self, data, xml):
        data.userNTP.curr_server.asoc_type = xml.get_body()
        return

    pass

# /system/ntp/server/iburst
class NTPServerIBurst(tf.YangElemValidateOnly):
    def validate_add(self, data, xml):
        data.userNTP.curr_server.iburst = xml.get_body()
        return

    pass

# /system/ntp/server/prever
class NTPServerPrefer(tf.YangElemValidateOnly):
    def validate_add(self, data, xml):
        data.userNTP.curr_server.prefer = xml.get_body()
        return

    pass

# /system/ntp/server
class NTPServer(tf.YangElemValidateOnly):
    def start(self, data, op):
        data.userNTP.curr_server = NTPServerData()
        data.userNTP.curr_server.op = op
        data.userNTP.servers.append(data.userNTP.curr_server)
        return

    def validate_add(self, data, xml):
        self.start(data, "add")
        super().validate_add(data, xml)
        return

    def validate_del(self, data, xml):
        self.start(data, "del")
        super().validate_del(data, xml)
        return

    def validate(self, data, origxml, newxml):
        self.start(data, "change")
        super().validate(data, origxml, newxml)
        return

    pass

# /system/ntp/server/udp
system_ntp_server_udp_children = {
    "address": NTPServerUDPAddress("address", tf.YangType.LEAF),
    "port": NTPServerUDPPort("port", tf.YangType.LEAF),
}

# /system/ntp/server/nts
system_ntp_server_nts_children = {
    "address": NTPServerNTSAddress("address", tf.YangType.LEAF),
    "port": NTPServerNTSPort("port", tf.YangType.LEAF),
    "certificate": NTPServerNTSCertificate("certificate", tf.YangType.LEAF),
}

# /system/ntp/server
system_ntp_server_children = {
    "name": NTPServerName("name", tf.YangType.LEAF),
    "udp": tf.YangElemValidateOnly("udp", tf.YangType.CONTAINER,
                                   children = system_ntp_server_udp_children,
                                   validate_all = True),
    "nts": tf.YangElemValidateOnly("nts", tf.YangType.CONTAINER,
                                   children = system_ntp_server_nts_children,
                                   validate_all = True),
    "association-type": NTPServerAsocType("association-type", tf.YangType.LEAF),
    "iburst": NTPServerIBurst("iburst", tf.YangType.LEAF),
    "prefer": NTPServerPrefer("prefer", tf.YangType.LEAF),
}

# /system/ntp
class NTP(tf.YangElemValidateOnly):
    def start(self, data):
        data.userNTP = NTPData("ntp")
        data.add_op(data.userNTP, "ntp", None)
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

    # FIXME - implement this
    def getvalue(self, vdata=None):
        return ""

    pass

# /system/ntp
system_ntp_children = {
    "enabled": NTPEnabled("enabled", tf.YangType.LEAF),
    "server": NTPServer("server", tf.YangType.CONTAINER,
                        children = system_ntp_server_children,
                        validate_all = True)
}

# /system
system_children = {
    "contact": tf.YangElemConfigOnly("contact"),
    "hostname": Hostname("hostname", tf.YangType.LEAF),
    "location": tf.YangElemConfigOnly("location"),
    "clock": tf.YangElem("clock", tf.YangType.CONTAINER, system_clock_children),
    "ntp": NTP("ntp", tf.YangType.CONTAINER, children = system_ntp_children,
               validate_all = True),
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

    def end(self, t):
        data = t.get_userdata()
        if data.oldpwfile:
            self.program_output([rmcmd, "-f",
                                 sysbase + passwdfile + ".keep"])
            if have_shadow:
                self.program_output([rmcmd, "-f",
                                     sysbase + shadowfile + ".keep"])
        return 0

    def abort(self, t):
        data = t.get_userdata()
        if data.oldpwfile:
            self.program_output([mvcmd, "-f",
                                 sysbase + passwdfile + ".keep",
                                 sysbase + passwdfile])
            if have_shadow:
                self.program_output([rmcmd, "-f",
                                     sysbase + shadowfile + ".keep",
                                     sysbase + shadowfile])
        return 0

    def statedata(self, nsc, xpath):
        return super().statedata(nsc, xpath)

    pass

children = {
    "system": tf.YangElem("system", tf.YangType.CONTAINER, system_children),
    "system-state": tf.YangElem("system-state", tf.YangType.CONTAINER,
                                system_state_children),
}
handler = Handler("linux-system", IETF_SYSTEM_NAMESPACE,
                  children)
handler.p = clixon_beh.add_plugin("linux-system", handler.namespace, handler)

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

class AuthStatedata:
    def stateonly(self):
        rv = children["system"].getonevalue()
        if rv and len(rv) > 0:
            rv = ("<system xmlns=\"" + IETF_SYSTEM_NAMESPACE + "\">"
                  + rv + "</system>")
            pass
        # Uncomment to print the return data
        #print("Return: " + str(rv))
        return (0, rv)

    pass

clixon_beh.add_stateonly("<system xmlns=\"" + IETF_SYSTEM_NAMESPACE + "\"></system>",
                         AuthStatedata())
