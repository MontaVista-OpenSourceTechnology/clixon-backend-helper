
import clixon_beh

class TransactionOp:
    def __init__(self, handler, opname, value):
        self.handler = handler
        self.opname = opname
        self.value = value
        self.revert = False
        self.oldvalue = None

    def commit(self):
        self.handler.commit(self)

    def revert(self):
        self.op.revert = True
        self.handler.revert(self)

class TransactionData:
    def __init__(self):
        self.ops = []

    def add_op(self, handler, op, value):
        self.ops.append(TransactionOp(handler, op, value))

    def commit(self):
        for op in self.ops:
            op.commit()

    def revert(self):
        for op in reversed(self.ops):
            op.revert()

class OpBase:
    def __init__(self, name, children = {}):
        self.name = name
        self.children = children

    def validate_add(self, data, xml):
        """Validate add of an element list.  Leaf elements should override
        this."""
        for i in range(0, xml.nr_children_type(clixon_beh.XMLOBJ_TYPE_ELEMENT)):
            c = xml.child_i(i)
            name = c.get_name()
            if name in self.root.children:
                self.root.children[name].validate_add(data, c)
        return

    def validate_del(self, data, xml):
        """Validate delete of an element list.  Leaf elements should override
        this."""
        for i in range(0, xml.nr_children_type(clixon_beh.XMLOBJ_TYPE_ELEMENT)):
            c = xml.child_i(i)
            name = c.get_name()
            if name in self.root.children:
                self.root.children[name].validate_del(data, c)
        return

    def validate(self, data, origxml, newxml):
        """Validate an element list.  Leaf elements should override this."""
        oi = 0
        if origxml:
            oxml = origxml.child_i(oi)
        else:
            oxml = None
        ni = 0
        if newxml:
            nxml = newxml.child_i(ni)
        else:
            nxml = None
        while oxml and nxml:
            if oxml and "del" in oxml.get_flags_strs().split(","):
                c = oxml.get_name()
                if c in self.children:
                    self.root.children[c].validate_del(data, c)
                oi += 1
                oxml = origxml.child_i(oi)
                pass
            elif nxml and "add" in nxml.get_flags_strs().split(","):
                c = oxml.get_name()
                if c in self.children:
                    self.root.children[c].validate_add(data, c)
                ni += 1
                nxml = newxml.child_i(ni)
                pass
            else:
                if (oxml and "change" in oxml.get_flags_strs().split(",") and
                        nxml and "change" in nxml.get_flags_strs().split(",")):
                    c = oxml.get_name()
                    if c in self.children:
                        self.root.children[c].validate(data, oxml, nxml)
                if oxml:
                    oi += 1
                    oxml = origxml.child_i(oi)
                if nxml:
                    ni += 1
                    nxml = newxml.child_i(ni)
        return

    def commit(self, op):
        return

    def revert(self, op):
        return

    def do_priv(self, op):
        """Perform an operation at the initial privilege level."""
        euid = clixon_beh.geteuid()
        if restore_priv() < 0:
            raise Exception(self.name + ": Can't restore privileges.")
        try:
            self.priv(op)
        finally:
            if clixon_beh.drop_priv_temp(euid) < 0:
                raise Exception(self.name + ": Can't drop privileges.")

    def priv(self, op):
        """Subclasses must override this function for privileged operations."""
        return

    def getxml(self, path):
        """Process a get operation before the path has ended.  We are just
        parsing down the path until we hit then end."""
        xml = "<" + self.name + ">"
        if len(path) == 0:
            xml += self.getvalue()
        elif path[0] in self.children:
            name = path[0].split(":")
            if len(name) == 1:
                name = name[0]
            else:
                name = name[1]
            xml += self.children[path[0]].getxml(path[1:])
        else:
            raise Exception("Unknown name " + path[0] + " in " + self.name)
        xml += "</" + self.name + ">"
        return xml

    def getvalue(self):
        """Return the xml strings for this node.  Leaf nodes should override
        this and return the value."""
        xml = ""
        for name in self.children:
            xml += "<" + self.name + ">"
            xml += self.children[c].getvalue()
            xml += "</" + self.name + ">"
        return xml;

    def program_output(self, args):
        """Call a program with the given arguments and return the stdout.
        If it errors, generate an exception with stderr output."""
        p = subprocess.Popen(args, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        (out, err) = p.communicate(timeout=1000)
        rc = p.wait()
        if rc != 0:
            raise Exception(args[0] + " error: " + err);
        return out.decode("utf-8").strip()

class OpBaseConfigOnly(OpBase):
    """If a leaf element is config only, there's no need to do much, it's
    stored in the main database only.

    """

    def __init__(self, name):
        super().__init__(name)

    def validate_add(self, data, xml):
        return

    def validate_del(self, data, xml):
        return

    def validate(self, data, origxml, newxml):
        return

    def getxml(self, path):
        return ""
    
class OpHandler:
    """Handler for Clixon backend."""

    def __init__(self, name, children):
        """
        name is the top-level name of the yang/xml data.
        children is a map of elements that may be in the top level.
        """
        self.name = name
        self.namespace = "urn:ietf:params:xml:ns:yang:ietf-system"
        self.xmlroot = OpBase(name, children)

    def pre_daemon(self):
        print("***pre_daemon***")
        return 0;

    def daemon(self):
        print("***daemon***")
        return 0

    def reset(self, cb):
        print("***reset** " + cb)
        return 0

    def begin(self, t):
        print("***begin**")
        t.set_userdata(TransactionData())
        return 0

    def validate(self, t):
        print("***validate**")
        data = t.get_userdata()
        self.xmlroot.validate(data, t.orig_xml(), t.new_xml())
        return 0

    def commit(self, t):
        print("***commit**")
        data = t.get_userdata()
        data.commit()
        return 0

    def revert(self, t):
        print("***revert**")
        data = t.get_userdata()
        data.revert()
        return 0

    def abort(self, t):
        print("***abort**")
        return 0

    def statedata(self, nsc, xpath):
        print("***statedata**: "+ str(nsc) + " " + xpath)
        path = xpath.split("/")
        if len(path) < 1:
            return(-1, "")
        name = path[0].split(":")
        if len(name) == 1:
            name = name[0]
        else:
            name = name[1]
        if name != self.name:
            return(-1, "")
        return (0, self.xmlroot.getxml(path[1:]))

    def exit(self):
        print("***exit**")
        self.p = None # Break circular dependency
        return 0;

class IETFSystemHostname(OpBase):
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

# This is the set of items that may appear under the "system"
# level of ietf-system.
children = {
    "contact": OpBaseConfigOnly("contact"),
    "hostname": IETFSystemHostname("hostname"),
    "location": OpBaseConfigOnly("location"),
}
handler = OpHandler("system", children)
handler.p = clixon_beh.add_plugin("ietf-system", handler.namespace, handler)
