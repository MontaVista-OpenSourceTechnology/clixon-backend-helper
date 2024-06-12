
import shlex
import clixon_beh
import clixon_beh.transaction_framework as tf

class Hostname(tf.OpBase):
    def __init__(self, name):
        super().__init__(name)

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

class TimeZone(tf.OpBase):
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

clock_children = {
    "timezone-name": TimeZone("timezone-name", is_name=True),
    "timezone-utc-offset": TimeZone("timezone-utc-offset", is_name=False),
}

# This is the set of items that may appear under the "system"
# level of ietf-system.
system_children = {
    "contact": tf.OpBaseConfigOnly("contact"),
    "hostname": Hostname("hostname"),
    "location": tf.OpBaseConfigOnly("location"),
    "clock": tf.OpBase("clock", clock_children),
}

class SystemStatePlatform(tf.OpBase):
    def __init__(self, name):
        super().__init__(name)

    def validate_add(self, data, xml):
        raise Exception("Cannot modify system state")

    def validate_del(self, data, xml):
        raise Exception("Cannot modify system state")

    def validate(self, data, origxml, newxml):
        raise Exception("Cannot modify system state")

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

class SystemStateClock(tf.OpBase):
    def __init__(self, name):
        super().__init__(name)

    def validate_add(self, data, xml):
        raise Exception("Cannot modify system state")

    def validate_del(self, data, xml):
        raise Exception("Cannot modify system state")

    def validate(self, data, origxml, newxml):
        raise Exception("Cannot modify system state")

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

system_state_platform_children = {
    "os-name": SystemStatePlatform("os-name"),
    "os-release": SystemStatePlatform("os-release"),
    "os-version": SystemStatePlatform("os-version"),
    "machine": SystemStatePlatform("machine")
}

system_state_clock_children = {
    "current-datetime": SystemStateClock("current-datetime"),
    "boot-datetime": SystemStateClock("boot-datetime")
}

system_state_children = {
    "platform": tf.OpBase("platform", system_state_platform_children),
    "clock": tf.OpBase("clock", system_state_clock_children)
}

class Handler(tf.OpHandler):
    def exit(self):
        print("***exit**")
        self.p = None # Break circular dependency
        return 0;

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
