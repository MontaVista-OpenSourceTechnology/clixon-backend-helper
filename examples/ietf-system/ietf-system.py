
import shlex
import clixon_beh
import clixon_beh.transaction_framework as tf

# /system/hostname
class Hostname(tf.OpBaseLeaf):
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
class TimeZone(tf.OpBaseLeaf):
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
clock_children = {
    "timezone-name": TimeZone("timezone-name", is_name=True),
    "timezone-utc-offset": TimeZone("timezone-utc-offset", is_name=False),
}

class DNSHandler(tf.OpBaseCommitOnly):
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
    def __init__(self):
        self.name = None
        self.address = None
        self.port = None

    def __str__(self):
        return f'({self.name}, {self.address}:{self.port})'

class DNSData:
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
class DNSSearch(tf.OpBaseValidateOnlyLeaf):
    def validate_add(self, data, xml):
        ddata = dns_get_opdata(data)
        ddata.add_search.append(xml.get_body())

# /system/dns-resolver/server/name
class DNSServerName(tf.OpBaseValidateOnlyLeaf):
    def validate_add(self, data, xml):
        ddata = dns_get_opdata(data)
        ddata.curr_server.name = xml.get_body()

# /system/dns-resolver/server/address
class DNSServerAddress(tf.OpBaseValidateOnlyLeaf):
    def validate_add(self, data, xml):
        ddata = dns_get_opdata(data)
        ddata.curr_server.address = xml.get_body()

# /system/dns-resolver/server/port
class DNSServerPort(tf.OpBaseValidateOnlyLeaf):
    def validate_add(self, data, xml):
        ddata = dns_get_opdata(data)
        ddata.curr_server.port = xml.get_body()

dns_server_ip_children = {
    "address": DNSServerAddress("timeout"),
    "port": DNSServerPort("port"),
}

dns_server_children = {
    "name": DNSServerName("timeout"),
    "udp-and-tcp": tf.OpBaseValidateOnly("upd-and-tcp", dns_server_ip_children),
    # FIXME - Add encrypted DNS support, and possibly DNSSEC.
}

# /system/dns-resolver/server
class DNSServer(tf.OpBaseValidateOnly):
    def __init__(self, name):
        super().__init__(name, children = dns_server_children)

    def validate_add(self, data, xml):
        ddata = dns_get_opdata(data)
        ddata.curr_server = DNSServerData()
        ddata.add_server.append(ddata.curr_server)
        super().validate_add(data, xml)

# /system/dns-resolver/options/timeout
class DNSTimeout(tf.OpBaseValidateOnlyLeaf):
    def validate_add(self, data, xml):
        ddata = dns_get_opdata(data)
        ddata.timeout = xml.get_body()

# /system/dns-resolver/options/attempts
class DNSAttempts(tf.OpBaseValidateOnlyLeaf):
    def validate_add(self, data, xml):
        ddata = dns_get_opdata(data)
        ddata.attempts = xml.get_body()

class DNSResolver(tf.OpBase):
    def __init__(self, name, children):
        super().__init__(name, children = children, validate_all = True,
                         xmlprocvalue = True)

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
dns_options_children = {
    "timeout": DNSTimeout("timeout"),
    "attempts": DNSAttempts("attempts"),
}

# /system/dns-resolver
dns_resolver_children = {
    "search": DNSSearch("search"),
    "server": DNSServer("server"),
    "options": tf.OpBase("options", dns_options_children),
}

# /system
system_children = {
    "contact": tf.OpBaseConfigOnly("contact"),
    "hostname": Hostname("hostname"),
    "location": tf.OpBaseConfigOnly("location"),
    "clock": tf.OpBase("clock", clock_children),
    "dns-resolver": DNSResolver("dns-resolver", dns_resolver_children),
}

# /system-state/platform/*
class SystemStatePlatform(tf.OpBaseValueOnly):
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
class SystemStateClock(tf.OpBaseValueOnly):
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
    "platform": tf.OpBase("platform", system_state_platform_children),
    "clock": tf.OpBase("clock", system_state_clock_children)
}

class Handler(tf.OpHandler):
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
        return 0

    def statedata(self, nsc, xpath):
        rv = super().statedata(nsc, xpath)
        return rv

children = {
    "system": tf.OpBase("system", system_children),
    "system-state": tf.OpBase("system-state", system_state_children),
}
handler = Handler("ietf-system", "urn:ietf:params:xml:ns:yang:ietf-system",
                  children)
handler.p = clixon_beh.add_plugin("ietf-system", handler.namespace, handler)
