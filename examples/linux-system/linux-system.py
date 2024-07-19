
import os
import pwd
import shlex
import clixon_beh
import clixon_beh.transaction_framework as tf

# This must match the commenting out or not of the dns-resolver deviation
# in linux-system.yang.
old_dns_supported = True

# Enable various password operations
allow_user_add_del = False      # Add/delete users allowed?
allow_user_pw_change = False    # User password changes allowed?
allow_user_key_change = False   # SSH authorized key changes allowed?

# NTP handling
using_ntp = True

# /system/hostname
class Hostname(tf.ElemOpBaseLeaf):
    def validate_add(self, data, xml):
        self.validate(data, None, xml)

    def validate_del(self, data, xml):
        raise Exception("Delete of hostname not allowed")

    def validate(self, data, origxml, newxml):
        value = newxml.get_body()
        if len(value) > 64: # Linux only allow 64 characters
            raise Exception("Host name too long, 64-character max.")
        data.add_op(self, None, value)

    def commit(self, op):
        op.oldvalue = self.getvalue()
        self.do_priv(op)

    def revert(self, op):
        self.do_priv(op)

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
        self.program_output(["/bin/hostname", value])
        f = open("/etc/hostname", "w")
        try:
            f.write(value + "\n")
        finally:
            f.close()

    def getvalue(self):
        return self.program_output(["/bin/hostname"]).strip()

# /system/clock/timezone-*
class TimeZone(tf.ElemOpBaseLeaf):
    def __init__(self, name, is_name=True):
        super().__init__(name)
        self.is_name = is_name

    def validate_add(self, data, xml):
        self.validate(data, None, xml)

    def validate_del(self, data, xml):
        # We just ignore this, it can happen when changing between
        # name and offset.
        return

    def validate(self, data, origxml, newxml):
        if not self.is_name:
            raise Exception("Only name timezones are accepted")
        value = newxml.get_body()
        if not os.path.exists("/usr/share/zoneinfo/" + value):
            raise Exception(value + " not a valid timezone")
        data.add_op(self, None, value)

    def commit(self, op):
        oldlocaltime = None
        try:
            lt = self.program_output(["/bin/ls", "-l", "/etc/localtime"])
            lt = lt.split("->")
            if len(lt) > 2:
                oldlocaltime = lt[1].strip()
        except:
            pass
        op.oldvalue = [oldlocaltime, self.getvalue()]
        self.do_priv(op)

    def revert(self, op):
        self.do_priv(op)

    def priv(self, op):
        if op.revert:
            if op.oldvalue is None:
                return # We didn't set it, nothing to do
            try:
                if op.oldvalue[0] is None:
                    # timedatectl will not add /etc/localtime if it
                    # does not exist or is not already a symlink.
                    # Make sure it points to something.
                    self.program_output(["/bin/ln", "-sf",
                                         "/usr/share/zoneinfo/GMT",
                                         "/etc/localtime"])
                self.setvalue(op.oldvalue[1])
            except:
                pass
        else:
            self.setvalue(op.value)
        return

    def setvalue(self, value):
        self.program_output(["/bin/timedatectl", "set-timezone", "--", value])

    def getvalue(self):
        if not self.is_name:
            return ""
        try:
            s = self.program_output(["/bin/cat", "/etc/timezone"]).strip() 
        except:
            s = "GMT"
        return s

# /system/clock
system_clock_children = {
    "timezone-name": TimeZone("timezone-name", is_name=True),
    "timezone-utc-offset": TimeZone("timezone-utc-offset", is_name=False),
}

# DNS can be disabled in the linux-system yang file, but this is here
# for old-style DNS.  If you are using resolvconf, disable it in the
# yang file and handle it in the IP address handling.

class DNSHandler(tf.ElemOpBaseCommitOnly):
    """This handles the full commit operation for DNS updates.
    """
    def commit(self, op):
        self.do_priv(op)

    def commit_done(self, op):
        self.do_priv(op)
        return

    def priv(self, op):
        ddata = op.userData
        if op.revert:
            os.remove("/etc/resolv.conf.tmp")
            pass
        elif op.done:
            os.replace("/etc/resolv.conf.tmp", "/etc/resolv.conf")
        else:
            # Create a file to hold the data.  We move the file over when
            # done.
            f = open("/etc/resolv.conf.tmp", "w")
            try:
                if len(ddata.add_search) > 0:
                    f.write("search")
                    for i in ddata.add_search:
                        f.write(" " + str(i))
                    f.write("\n")
                for i in ddata.add_server:
                    f.write("#name: " + str(i.name) + "\n")
                    f.write("nameserver " + str(i.address) + "\n")
                f.write("options timeout:" + ddata.timeout + " attempts:"
                        + ddata.attempts + "\n")
            finally:
                f.close()
        return

    def revert(self, op):
        self.do_priv(op)
        return

class DNSServerData:
    """Information about a single DNS server."""
    def __init__(self):
        self.name = None
        self.address = None
        self.port = None

    def __str__(self):
        return f'({self.name}, {self.address}:{self.port})'

class DNSData:
    """All DNS data will be parsed into this structure."""
    def __init__(self):
        self.curr_server = None
        self.add_search = []
        self.add_server = []
        self.timeout = None
        self.attempts = None

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
class DNSSearch(tf.ElemOpBaseValidateOnlyLeaf):
    def validate_add(self, data, xml):
        ddata = dns_get_opdata(data)
        ddata.add_search.append(xml.get_body())

# /system/dns-resolver/server/name
class DNSServerName(tf.ElemOpBaseValidateOnlyLeaf):
    def validate_add(self, data, xml):
        ddata = dns_get_opdata(data)
        ddata.curr_server.name = xml.get_body()

# /system/dns-resolver/server/address
class DNSServerAddress(tf.ElemOpBaseValidateOnlyLeaf):
    def validate_add(self, data, xml):
        ddata = dns_get_opdata(data)
        ddata.curr_server.address = xml.get_body()

# /system/dns-resolver/server/port
class DNSServerPort(tf.ElemOpBaseValidateOnlyLeaf):
    def validate_add(self, data, xml):
        ddata = dns_get_opdata(data)
        ddata.curr_server.port = xml.get_body()

# /system/dns-resolver/server/udp-and-tcp
system_dns_server_ip_children = {
    "address": DNSServerAddress("timeout"),
    "port": DNSServerPort("port"),
}

# /system/dns-resolver/server
system_dns_server_children = {
    "name": DNSServerName("timeout"),
    "udp-and-tcp": tf.ElemOpBaseValidateOnly("upd-and-tcp",
                                    children = system_dns_server_ip_children,
                                    validate_all = True),
    # FIXME - Add encrypted DNS support, and possibly DNSSEC.
}

# /system/dns-resolver/server
class DNSServer(tf.ElemOpBaseValidateOnly):
    def validate_add(self, data, xml):
        ddata = dns_get_opdata(data)
        ddata.curr_server = DNSServerData()
        ddata.add_server.append(ddata.curr_server)
        super().validate_add(data, xml)

# /system/dns-resolver/options/timeout
class DNSTimeout(tf.ElemOpBaseValidateOnlyLeaf):
    def validate_add(self, data, xml):
        ddata = dns_get_opdata(data)
        ddata.timeout = xml.get_body()

# /system/dns-resolver/options/attempts
class DNSAttempts(tf.ElemOpBaseValidateOnlyLeaf):
    def validate_add(self, data, xml):
        ddata = dns_get_opdata(data)
        ddata.attempts = xml.get_body()

# /system/dns-resolver
class DNSResolver(tf.ElemOpBase):
    def validate_del(self, data, xml):
        # FIXME - maybe delete /etc/resolv.conf?  or fix the YANG?
        raise Exception("Cannot delete main DNS data")

    def getvalue(self):
        """We fetch the resolv.conf file and process it here ourselves.  None
        of the children will need to handle it.

        """
        if not old_dns_supported:
            return ""

        try:
            f = open("/etc/resolv.conf", "r", encoding="utf-8")
        except:
            return ""
        try:
            s = ""
            srvnum = 1
            srvstr = str(srvnum)
            for l in f:
                if l.startswith("search "):
                    for i in l.split()[1:]:
                        s += "<search>" + tf.xmlescape(i) + "</search>"
                elif l.startswith("#name: "):
                    ts = l.split()
                    if len(ts) > 1:
                        srvstr = ts[1]
                elif l.startswith("nameserver "):
                    ts = l.split()
                    if len(ts) > 1:
                        s += "<server>"
                        s += "<name>" + tf.xmlescape(srvstr) + "</name>"
                        s += "<udp-and-tcp>"
                        s += "<address>" + tf.xmlescape(ts[1]) + "</address>"
                        s += "</udp-and-tcp>"
                        s += "</server>"
                        srvnum = srvnum + 1
                        srvstr = str(srvnum)
                elif l.startswith("options"):
                    s += "<options>"
                    for i in l.split()[1:]:
                        if i.startswith("timeout:"):
                            ts = i.split(":")
                            if len(ts) > 1:
                                to = tf.xmlescape(ts[1])
                                s += "<timeout>" + to + "</timeout>"
                        elif i.startswith("attempts:"):
                            ts = i.split(":")
                            if len(ts) > 1:
                                at = tf.xmlescape(ts[1])
                                s += "<attempts>" + at + "</attempts>"
                    s += "</options>"
        except:
            f.close()
            return ""
        f.close()
        return s

# /system/dns-resolver/options
system_dns_options_children = {
    "timeout": DNSTimeout("timeout"),
    "attempts": DNSAttempts("attempts"),
}

# /system/dns-resolver
system_dns_resolver_children = {
    "search": DNSSearch("search"),
    "server": DNSServer("server", children = system_dns_server_children,
                        validate_all = True),
    "options": tf.ElemOpBase("options", children = system_dns_options_children,
                             validate_all = True),
}

class UserKey:
    def __init(self):
        self.op = None
        self.name = None
        self.change_algorithm = False
        self.algorithm = None
        self.change_keydata = False
        self.keydata = None

class UserData(tf.ElemOpBaseCommitOnly):
    """This handles the user operation."""
    def __init__(self, name):
        super().__init__(name, data)
        self.data = data
        self.user_op = None
        self.user_name = None
        self.user_password_op = None
        self.user_password = None
        self.user_curr_key = None
        self.user_keys = []
        self.oldkeyfile = False
        self.oldkeyempty = False

    def savepwfile(self):
        if not self.data.oldpwfile:
            self.data.oldpwfile = True
            self.program_output(["/bin/cp", "/etc/passwd", "/etc/passwd.keep"])
            self.program_output(["/bin/cp", "/etc/shadow", "/etc/shadow.keep"])

    def savekeyfile(self):
        if not self.oldkeyfile:
            self.home = pwd.getpwname(self.user_name)[5]
            self.keyfile = self.home + "/.ssh/authorized_keys";
            try:
                self.program_output(["/bin/cp", self.keyfile,
                                     self.keyfile + ".keep"])
                self.oldkeyfile = True
            except:
                self.oldkeyempty = True
                self.program_output(["/bin/touch", self.keyfile])

    def commit(self, op):
        if self.user_name is None:
            raise Exception("User name not set") # Shouldn't be possible
        self.savepwfile()
        if self.user_op == "add":
            self.program_output(["/bin/useradd", "-m", self.user_name])
        elif self.user_op == "del":
            self.program_output(["/bin/userdel", self.user_name])
        else:
            if self.user_password_op == "add":
                self.program_output(["/bin/usermod", "-p", self.user_password,
                                     self.user_name])
            for i in self.user_keys:
                if i.op == "add":
                    self.savekeyfile()
                    f = open(self.keyfile, "a")
                    f.write(str(i.algorithm) + " "
                            + str(i.keydata) + " "
                            + str(i.name) + "\n")
                    f.close()
                else:
                    self.savekeyfile()
                    self.program_output(["sed", "-i", "/" + i.name + "/d",
                                         self.keyfile])

    def revert(self, op):
        if self.oldkeyfile:
            if self.oldkeyempty:
                self.program_output(["/bin/rm", self.keyfile])
            else:
                self.program_output(["/bin/mv", "-f", self.keyfile + ".keep",
                                     self.keyfile])

    def user_exists(self):
        try:
            pwd.getpwname(self.user_name)
        except:
            return False
        return True

# /system/authentication/user/name
class UserName(tf.ElemOpBaseValidateOnlyLeaf):
    def validate_add(self, data, xml):
        data.userCurrU.user_name = xml.get_body()
        if data.userCurrU.user_op == "add" and data.userCurrU.user_exists():
            raise Exception("User " + data.userCurrU.user_name
                            + " already exists")

    def validate_del(self, data, xml):
        data.userCurrU.user_name = xml.get_body()
        if not data.userCurrU.user_exists():
            raise Exception("User " + data.userCurrU.user_name + " not present")

    def validate(self, data, origxml, newxml):
        data.userCurrU.user_name = newxml.get_body()
        if not data.userCurrU.user_exists():
            raise Exception("User " + data.userCurrU.user_name + " not present")

# /system/authentication/user/password
class UserPassword(tf.ElemOpBaseValidateOnlyLeaf):
    def validate_add(self, data, xml):
        if not allow_user_key_change:
            raise Exception("User password change not allowed")
        data.userCurrU.user_password_op = "add"
        data.userCurrU.user_password = xml.get_body()

    def validate_del(self, data, xml):
        if data.userCurrU.user_op != "del":
            raise Exception("User password delete not allowed")
        data.userCurrU.user_password_op = "del"

    def validate(self, data, origxml, newxml):
        # Don't have to worry about the password on a delete.
        if newxml.get_flags(clixon_beh.XMLOBJ_FLAG_CHANGE):
            if not allow_user_key_change:
                raise Exception("User password change not allowed")
            data.userCurrU.user_password_op = "add" # Add and change are same
            data.userCurrU.user_password = xml.get_body()

# /system/authentication/user/authorized-key/name
class UserAuthkeyName(tf.ElemOpBaseValidateOnlyLeaf):
    def validate_add(self, data, xml):
        data.userCurrU.user_curr_key.name = xml.get_body()

# /system/authentication/user/authorized-key/algorithm
class UserAuthkeyAlgo(tf.ElemOpBaseValidateOnlyLeaf):
    def validate_add(self, data, xml):
        data.userCurrU.user_curr_key.algorithm = xml.get_body()

    def validate(self, data, origxml, newxml):
        if newxml.get_flags(clixon_beh.XMLOBJ_FLAG_CHANGE):
            data.userCurrU.user_curr_key.algorithm = xml.get_body()
            data.userCurrU.user_curr_key.change_algorithm = True

# /system/authentication/user/authorized-key/key-data
class UserAuthkeyKeyData(tf.ElemOpBaseValidateOnlyLeaf):
    def validate_add(self, data, xml):
        data.userCurrU.user_curr_key.keydata = xml.get_body()

    def validate(self, data, origxml, newxml):
        if newxml.get_flags(clixon_beh.XMLOBJ_FLAG_CHANGE):
            data.userCurrU.user_curr_key.keydata = xml.get_body()
            data.userCurrU.user_curr_key.change_keydata = True

# /system/authentication/user/authorized-key
class UserAuthkey(tf.ElemOpBaseValidateOnly):
    """This handles the user authorized key."""
    def validate_add(self, data, xml):
        if not allow_user_key_change:
            raise Exception("User key addition not allowed")
        data.userCurrU.user_curr_key = UserKey()
        data.userCurrU.user_keys.append(data.userCurrU.user_curr_key)
        data.userCurrU.user_curr_key.op = "add"
        super().validate_add(data, xml)

    def validate_del(self, data, xml):
        if not allow_user_key_change:
            raise Exception("User key deletion not allowed")
        data.userCurrU.user_curr_key = UserKey()
        data.userCurrU.user_keys.append(data.userCurrU.user_curr_key)
        data.userCurrU.user_curr_key.op = "del"
        data.userCurrU.user_keys.append(data.userCurrU.user_curr_key)

# /system/authentication/user/authorized-key
system_user_authkey_children = {
    "name": UserAuthkeyName("name"),
    "algorithm": UserAuthkeyAlgo("algorithm"),
    "key-data": UserAuthkeyKeyData("key-data"),
}

# /system/authentication/user
class User(tf.ElemOpBaseValidateOnly):
    def start(self, data, op):
        data.userCurrU = UserData("user", data)
        data.add_op(data.userCurrU, "user", None)
        data.userCurrU.user_op = op

    def validate_add(self, data, xml):
        if not allow_user_add_del:
            raise Exception("User addition not allowed")
        self.start(data, "add")
        super().validate_add(data, xml)

    def validate_del(self, data, xml):
        if not allow_user_add_del:
            raise Exception("User deletion not allowed")
        self.start(data, "del")
        super().validate_del(data, xml)

    def validate(self, data, origxml, newxml):
        self.start(data, None)
        super().validate(data, origxml, newxml)

    def getvalue(self):
        s = ""
        for i in pwd.getpwall():
            s += "<user><name>" + tf.xmlescape(i[0]) + "</name>"
            f = None
            try:
                f = open(i[5] + ".ssh/authorized_keys", "r")
                for j in f:
                    k = j.split()
                    if len(k) >= 3:
                        s += ("<authorized-key><name>" + k[2]
                              + "</name></authorized_key>")
            except:
                pass
            if f is not None:
                f.close()
            s += "</user>"
        return s

# /system/authentication/user
system_user_children = {
    "name": UserName("name"),
    "password": UserPassword("password"),
    "authorized-key": UserAuthkey("authorized-key",
                                  children = system_user_authkey_children,
                                  validate_all = True),
}

# /system/authentication
system_authentication_children = {
    "user-authentication-order": tf.ElemOpBaseConfigOnly("user-authentication-order"),
    "user": User("user", children = system_user_children, validate_all = True,
                 wrapxml = False),
}

class NTPServerData:
    def __init__(self):
        self.op = None
        self.name = None
        self.address = None
        self.port = "123"
        self.assoc_type = "server" # server, peer, or pool
        self.iburst = False
        self.prefer = False

class NTPData(tf.ElemOpBaseCommitOnly):
    def __init__(self, name):
        super().__init__(name)
        self.enabled = True
        self.servers = []

    # FIXME - really implement this
    def commit(self, op):
        print("NTP")
        print("  enabled: " + str(self.enabled))
        for i in self.servers:
            print("  server(" + str(i.op) + "): " + str(i.name))
            print("    name: " + str(i.name))
            print("    address: " + str(i.address))
            print("    port: " + str(i.port))
            print("    assoc_type: " + str(i.assoc_type))
            print("    iburst: " + str(i.iburst))
            print("    prefer: " + str(i.prefer))

    def revert(self, op):
        return

# /system/ntp/enabled
class NTPEnabled(tf.ElemOpBaseValidateOnlyLeaf):
    def validate_add(self, data, xml):
        data.userNTP.enabled = xml.get_body()

# /system/ntp/server/name
class NTPServerName(tf.ElemOpBaseValidateOnlyLeaf):
    def validate_add(self, data, xml):
        data.userNTP.curr_server.name = xml.get_body()

# /system/ntp/server/udp/address
class NTPServerUDPAddress(tf.ElemOpBaseValidateOnlyLeaf):
    def validate_add(self, data, xml):
        data.userNTP.curr_server.address = xml.get_body()

# /system/ntp/server/udp/port
class NTPServerUDPPort(tf.ElemOpBaseValidateOnlyLeaf):
    def validate_add(self, data, xml):
        data.userNTP.curr_server.port = xml.get_body()

# /system/ntp/server/association-type
class NTPServerAsocType(tf.ElemOpBaseValidateOnlyLeaf):
    def validate_add(self, data, xml):
        data.userNTP.curr_server.asoc_type = xml.get_body()

# /system/ntp/server/iburst
class NTPServerIBurst(tf.ElemOpBaseValidateOnlyLeaf):
    def validate_add(self, data, xml):
        data.userNTP.curr_server.iburst = xml.get_body()

# /system/ntp/server/prever
class NTPServerPrefer(tf.ElemOpBaseValidateOnlyLeaf):
    def validate_add(self, data, xml):
        data.userNTP.curr_server.prefer = xml.get_body()

# /system/ntp/server
class NTPServer(tf.ElemOpBaseValidateOnly):
    def start(self, data, op):
        data.userNTP.curr_server = NTPServerData()
        data.userNTP.curr_server.op = op
        data.userNTP.servers.append(data.userNTP.curr_server)

    def validate_add(self, data, xml):
        self.start(data, "add")
        super().validate_add(data, xml)

    def validate_del(self, data, xml):
        self.start(data, "del")
        super().validate_del(data, xml)

    def validate(self, data, origxml, newxml):
        self.start(data, "change")
        super().validate(data, origxml, newxml)

# /system/ntp/server/udp
system_ntp_server_udp_children = {
    "address": NTPServerUDPAddress("address"),
    "port": NTPServerUDPPort("port"),
}

# /system/ntp/server
system_ntp_server_children = {
    "name": NTPServerName("name"),
    "udp": tf.ElemOpBaseValidateOnly("udp",
                                     children = system_ntp_server_udp_children,
                                     validate_all = True),
    "association-type": NTPServerAsocType("association-type"),
    "iburst": NTPServerIBurst("iburst"),
    "prefer": NTPServerPrefer("prefer"),
}

# /system/ntp
class NTP(tf.ElemOpBaseValidateOnly):
    def start(self, data):
        data.userNTP = NTPData("ntp")
        data.add_op(data.userNTP, "ntp", None)

    def validate_add(self, data, xml):
        self.start(data)
        super().validate_add(data, xml)

    def validate_del(self, data, xml):
        raise Exception("Cannot delete NTP data.")

    def validate(self, data, origxml, newxml):
        self.start(data)
        super().validate(data, origxml, newxml)

    # FIXME - implement this
    def getvalue(self):
        return ""

# /system/ntp
system_ntp_children = {
    "enabled": NTPEnabled("enabled"),
    "server": NTPServer("server", children = system_ntp_server_children,
                        validate_all = True)
}

# /system
system_children = {
    "contact": tf.ElemOpBaseConfigOnly("contact"),
    "hostname": Hostname("hostname"),
    "location": tf.ElemOpBaseConfigOnly("location"),
    "clock": tf.ElemOpBase("clock", system_clock_children),
    "ntp": NTP("ntp", children = system_ntp_children, validate_all = True,
               xmlprocvalue = True),
    "dns-resolver": DNSResolver("dns-resolver",
                                children = system_dns_resolver_children,
                                validate_all = True, xmlprocvalue = False),
    "authentication": tf.ElemOpBase("authentication",
                                    children = system_authentication_children),
}

# /system-state/platform/*
class SystemStatePlatform(tf.ElemOpBaseValueOnly):
    def getvalue(self):
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

# /system-state/clock/*
class SystemStateClock(tf.ElemOpBaseValueOnly):
    def getvalue(self):
        date = self.program_output(["/bin/date","--rfc-3339=seconds"]).strip()
        date = date.split(" ")
        if len(date) < 2:
            raise Exception("Invalid date output: " + str(date))
        if "+" in date[1]:
            date[1] = date[1].replace("+", "Z+", 1)
        else:
            date[1] = date[1].replace("-", "Z-", 1)
        date = date[0] + "T" + date[1]

        if self.name == "boot-datetime":
            bdate = shlex.split(self.program_output(["/bin/who","-b"]))
            if len(bdate) < 4:
                raise Exception("Invalid who -b output: " + str(bdate))
            zone = date.split("Z")
            if len(zone) < 2:
                raise Exception("Invalid zone in date: " + date)
            date = bdate[2] + "T" + bdate[3] + "Z" + zone[1]

        return date

# /system-state/platform
system_state_platform_children = {
    "os-name": SystemStatePlatform("os-name"),
    "os-release": SystemStatePlatform("os-release"),
    "os-version": SystemStatePlatform("os-version"),
    "machine": SystemStatePlatform("machine")
}

# /system-state/clock
system_state_clock_children = {
    "current-datetime": SystemStateClock("current-datetime"),
    "boot-datetime": SystemStateClock("boot-datetime")
}

# /system-state
system_state_children = {
    "platform": tf.ElemOpBase("platform", system_state_platform_children),
    "clock": tf.ElemOpBase("clock", system_state_clock_children)
}

class Handler(tf.TopElemHandler):
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
            self.program_output(["/bin/rm", "-f", "/etc/passwd.keep"])
            self.program_output(["/bin/rm", "-f", "/etc/shadow.keep"])
        return 0

    def abort(self, t):
        data = t.get_userdata()
        if data.oldpwfile:
            self.program_output(["/bin/mv", "-f", "/etc/passwd.keep",
                                 "/etc/passwd"])
            self.program_output(["/bin/rm", "-f", "/etc/shadow.keep",
                                 "/etc/shadow"])
        return 0

    def statedata(self, nsc, xpath):
        return super().statedata(nsc, xpath)

children = {
    "system": tf.ElemOpBase("system", system_children),
    "system-state": tf.ElemOpBase("system-state", system_state_children),
}
handler = Handler("linux-system", "urn:ietf:params:xml:ns:yang:ietf-system",
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
        s += '</rpc-reply>'
        return (0, s)

    def priv(self, op):
        self.program_output(["/bin/date", "-s", op])

clixon_beh.add_rpc_callback("set-current-datetime",
                            "urn:ietf:params:xml:ns:yang:ietf-system",
                            SetTimeHandler())

class RestartHandler(tf.RPC):
    def rpc(self, x, username):
        self.do_priv("")
        s = '<rpc-reply xmlns="' + clixon_beh.NETCONF_BASE_NAMESPACE + '">'
        s += '</rpc-reply>'
        return (0, s)

    def priv(self, op):
        self.program_output(["/sbin/reboot"])

clixon_beh.add_rpc_callback("system-restart",
                            "urn:ietf:params:xml:ns:yang:ietf-system",
                            RestartHandler())


class ShutdownHandler(tf.RPC):
    def rpc(self, x, username):
        self.do_priv("")
        s = '<rpc-reply xmlns="' + clixon_beh.NETCONF_BASE_NAMESPACE + '">'
        s += '</rpc-reply>'
        return (0, s)

    def priv(self, op):
        self.program_output(["/sbin/shutdown", "now"])

clixon_beh.add_rpc_callback("system-shutdown",
                            "urn:ietf:params:xml:ns:yang:ietf-system",
                            ShutdownHandler())

class AuthStatedata:
    def stateonly(self):
        rv = children["system"].getvalue()
        if rv and len(rv) > 0:
            rv = ("<system xmlns=\"urn:ietf:params:xml:ns:yang:ietf-system\">"
                  + rv + "</system>")
        return (0, rv)

clixon_beh.add_stateonly("<system xmlns=\"urn:ietf:params:xml:ns:yang:ietf-system\"></system>",
                         AuthStatedata())
