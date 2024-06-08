import clixon_beh
from lxml import etree

class ClixonHelloOp:
    def __init__(self):
        self.op = None
        self.value = ""

valid_places = {
    "city": True,
    "state": True,
    "country": True,
    "world": True
}

class ClixonHelloHandler:
    def __init__(self):
        self.world = None;
        self.namespace = "urn:example:pyhello_beh"

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
        t.set_userdata(ClixonHelloOp())
        return 0

    def validate(self, t):
        print("***validate**")
        origxml = t.orig_str()
        newxml = t.new_str()
        data = t.get_userdata()
        print(str(origxml))
        print(str(newxml))
        val = None
        op = None
        if origxml is not None:
            xn = etree.fromstring(origxml)
            flags = xn.get("clixonflags")
            if flags:
                flags = flags.split(",");
            if flags and "del" in flags:
                op = "del"
                x = etree.QName(xn.tag)
                if x.localname == "hello" and x.namespace == self.namespace:
                    xn = xn[0]
                    x = etree.QName(xn.tag)
                    if x.localname == "to":
                        val = xn.text

        if newxml is not None:
            xn = etree.fromstring(newxml)
            flags = xn.get("clixonflags")
            if flags:
                flags = flags.split(",");
            if flags and ("add" in flags or "change" in flags):
                op = "add"
                x = etree.QName(xn.tag)
                if x.localname == "hello" and x.namespace == self.namespace:
                    xn = xn[0]
                    x = etree.QName(xn.tag)
                    if x.localname == "to":
                        val = xn.text

        print("op = " + str(op) + "   val = " + str(val))
        if op is None:
            return 0
        if val is None:
            return -1
        if val not in valid_places:
            return -1
        data.op = op
        data.val = val
        return 0

    def commit(self, t):
        print("***commit**")
        data = t.get_userdata()
        if data.op is None:
            return 0
        if data.op == "add":
            self.world = data.val
        else:
            self.world = None
        return 0

    def statedata(self, nsc, xpath):
        print("***statedata**")
        if self.world is None:
            return(-1, "")
        s = ("<hello xmlns=\"" + self.namespace + "\"><to>" + self.world +
             "</to></hello>")
        return (0, s);

    def exit(self):
        print("***exit**")
        try:
            del(self.p)
        except:
            None
        return 0;

handler = ClixonHelloHandler()
# You must store the returned plugin someplace.  Otherwise it will be
# deleted by the python GC, and that will delete the handler, and all
# this will be for nought.
handler.p = clixon_beh.add_plugin_strxml("pyhello",
                                         handler.namespace, None, handler)
