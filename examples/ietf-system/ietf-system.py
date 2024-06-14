
import os
import pwd
import shlex
import clixon_beh
import clixon_beh.transaction_framework as tf

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
        self.do_priv(op, value)

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
        self.do_priv(op, value)

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
        return self.program_output(["/bin/cat", "/etc/timezone"]).strip()

# /system/clock
system_clock_children = {
    "timezone-name": TimeZone("timezone-name", is_name=True),
    "timezone-utc-offset": TimeZone("timezone-utc-offset", is_name=False),
}

class DNSHandler(tf.ElemOpBaseCommitOnly):
    """This handles the full commit operation for DNS updates.
    """
    # FIXME - really implement this
    def commit(self, op):
        ddata = op.userData
        print("DNS")
        print("  Search: " + str(ddata.add_search))
        s = []
        for i in ddata.add_server:
            s.append(str(i))
        print("  Servers: " + str(s))
        print("  timeout: " + str(ddata.timeout))
        print("  attempts: " + str(ddata.attempts))

    def revert(self, op):
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
        # FIXME
        return ""

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
        super().__init__(name)
        self.user_op = None
        self.user_name = None
        self.user_password_op = None
        self.user_password = None
        self.user_curr_key = None
        self.user_keys = []

    # FIXME - really implement this
    def commit(self, op):
        print("User " + str(self.user_op))
        print("  name: " + str(self.user_name))
        print("  password(" + str(self.user_password_op) + "): " +
              str(self.user_password))
        for i in self.user_keys:
            print("  key(" + str(i.op) + "): " + str(i.name))
            print("    algorithm: " + str(i.algorithm))
            print("    keydata: " + str(i.keydata))

    def revert(self, op):
        return

    def user_exists(self, name):
        try:
            pwd.getpwname(name)
        except:
            return False
        return True

# /system/authentication/user/name
class UserName(tf.ElemOpBaseValidateOnlyLeaf):
    def validate_add(self, data, xml):
        data.userCurrU.user_name = xml.get_body()

    def validate_del(self, data, xml):
        data.userCurrU.user_name = xml.get_body()

    def validate(self, data, origxml, newxml):
        data.userCurrU.user_name = newxml.get_body()
        if not data.user_exists(data.userCurrU.user_name):
            raise Exception("User " + data.userCurrU.user_name + "not present")

# /system/authentication/user/password
class UserPassword(tf.ElemOpBaseValidateOnlyLeaf):
    def validate_add(self, data, xml):
        data.userCurrU.user_password_op = "add"
        data.userCurrU.user_password = xml.get_body()

    def validate_del(self, data, xml):
        data.userCurrU.user_password_op = "del"

    def validate(self, data, origxml, newxml):
        if newxml.get_flags(clixon_beh.XMLOBJ_FLAG_CHANGE):
            data.userCurrU.user_password_op = "change"
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
        data.userCurrU.user_curr_key = UserKey()
        data.userCurrU.user_keys.append(data.userCurrU.user_curr_key)
        data.userCurrU.user_curr_key.op = "add"
        super().validate_add(data, xml)

    def validate_del(self, data, xml):
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
        data.userCurrU = UserData("user")
        data.add_op(data.userCurrU, "user", None)
        data.userCurrU.user_op = op

    def validate_add(self, data, xml):
        self.start(data, "add")
        super().validate_add(data, xml)

    def validate_del(self, data, xml):
        self.start(data, "del")
        super().validate_del(data, xml)

    def validate(self, data, origxml, newxml):
        self.start(data, None)
        super().validate(data, origxml, new)

    def getvalue(self):
        return ""

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
    "user": User("user", children = system_user_children, validate_all = True),
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
                                validate_all = True, xmlprocvalue = True),
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
        print("***exit**")
        self.p = None # Break circular dependency
        return 0;

    def begin(self, t):
        rv = super().begin(t)
        if rv < 0:
            return rv
        data = t.get_userdata()
        data.userDNSOp = None # Replaced when DNS operations are done.
        data.userCurrU = None # Replaced by user operations
        data.userNTP = None # Replaced by NTP operations
        return 0

    def statedata(self, nsc, xpath):
        rv = super().statedata(nsc, xpath)
        return rv

children = {
    "system": tf.ElemOpBase("system", system_children),
    "system-state": tf.ElemOpBase("system-state", system_state_children),
}
handler = Handler("ietf-system", "urn:ietf:params:xml:ns:yang:ietf-system",
                  children)
handler.p = clixon_beh.add_plugin("ietf-system", handler.namespace, handler)
