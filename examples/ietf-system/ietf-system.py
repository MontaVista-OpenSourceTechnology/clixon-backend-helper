
import clixon_beh
import clixon_beh.transaction_framework as tf

class IETFSystemHostname(tf.OpBase):
    def __init__(self, name):
        super().__init__(name)

    def validate_add(self, data, xml):
        self.validate(data, None, xml)

    def validate_del(self, data, xml):
        raise Exception("Delete of hostname not allowed")

    def validate(self, data, origxml, newxml):
        value = newxml.get_value()
        if len(value) > 64: # Linux only allow 64 characters
            raise Exception("Host name too long, 64-character max.")
        data.add_op(self, None, value)

    def commit(self, op):
        op.oldvalue = self.getvalue()
        self.do_priv(op, value)

    def revert(self, op):
        self.do_priv(op, value)

    def priv(self, op):
        if op.revert:
            if self.oldvalue is None:
                return # We didn't set it, nothing to do
            pass
        else:
            pass
        return

    def getvalue(self):
        return self.program_output(["/bin/hostname"])

class IETFHandler(tf.OpHandler):
    def exit(self):
        print("***exit**")
        self.p = None # Break circular dependency
        return 0;

# This is the set of items that may appear under the "system"
# level of ietf-system.
children = {
    "contact": tf.OpBaseConfigOnly("contact"),
    "hostname": IETFSystemHostname("hostname"),
    "location": tf.OpBaseConfigOnly("location"),
}
handler = tf.OpHandler("system", children)
handler.p = clixon_beh.add_plugin("ietf-system", handler.namespace, handler)
