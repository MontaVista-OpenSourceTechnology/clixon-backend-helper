
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
        return self.program_output(["/bin/cat", "/etc/timezone"]).strip()

class Handler(tf.OpHandler):
    def exit(self):
        print("***exit**")
        self.p = None # Break circular dependency
        return 0;

clock_children = {
    "timezone-name": TimeZone("timezone-name", is_name=True),
    "timezone-utc-offset": TimeZone("timezone-utc-offset", is_name=False),
}

# This is the set of items that may appear under the "system"
# level of ietf-system.
children = {
    "contact": tf.OpBaseConfigOnly("contact"),
    "hostname": Hostname("hostname"),
    "location": tf.OpBaseConfigOnly("location"),
    "clock": tf.OpBase("clock", clock_children),
}
handler = Handler("urn:ietf:params:xml:ns:yang:ietf-system", "system", children)
handler.p = clixon_beh.add_plugin("ietf-system", handler.namespace, handler)
