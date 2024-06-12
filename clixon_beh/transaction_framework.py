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

import subprocess
import clixon_beh

"""This is a package that helps with clixon backends.  It provides a
frameowrk that allows users to provide just the low-level pieces they
need and describe the framework of their XML processing with simple
maps.

The idea is you describe your XML design with maps at each xml level
that contain the xml element that may be at that level.  At the leaf
level, or at any level where you need to stop and handle everything
together, you write a class that descends from OpBase to handle that
specific thing.

You class will be have validate calls to handle validating your data.
The validate calls should then add operations to the transaction data
to describe what they should do at commit time.  At commit time, each
operation's handler is then called to actually do the operation.  If a
commit fails for some reason, the revert calls for the operations will
be done in reverse order.

"""

class Op:
    """This is an operation.  Generally you add this in the validate calls
    when you discover things that need to be done.  and the handler's
    commit function get's called in the commit and revert calls.

    """
    def __init__(self, handler, opname, value):
        """The handler's commit and revert methods will be called during the
        commit and revert operations.  opname is a convenience name,
        and value may be anything the user desires.

        """

        self.handler = handler
        self.opname = opname
        self.value = value
        self.revert = False
        self.oldvalue = None

    def commit(self):
        """Commit the operation, basically apply it to the system.  If you
        handle revert, you should store the data to revert in the
        oldvalue member of this object.

        """
        self.handler.commit(self)

    def revert(self):
        """Revert the operation.  The "revert" member of this is set to True
        here for convenience for the user.

        """
        self.op.revert = True
        self.handler.revert(self)

class Data:
    """This is data about a transaction.  It holds the list of operations
    and does the full commit/revert operations.

    """
    def __init__(self):
        self.ops = []

    def add_op(self, handler, op, value):
        """Add an operation to the operation queue.  These will be done
        in the commit and revert phases."""
        self.ops.append(Op(handler, op, value))

    def commit(self):
        for op in self.ops:
            op.commit()

    def revert(self):
        for op in reversed(self.ops):
            op.revert()

class OpBase:
    """The base class for operation handler (what goes into an "Op" class
    handler).  Any operation should descend from this class.  For
    non-leaf objects, this can be used directly, too.  Leaf element
    should always override the validate methods and getvalue method.
    Non-leaf elements, if they process a bunch of data together, can
    override this, too, and also probably need to override getxml.

    """
    def __init__(self, name, children = {}):
        """name should be the xml tag name for this operations.  children, if
        set, should be a map of the xml elements that can occur in
        this xml element, and their handlers.

        """
        self.name = name
        self.children = children

    def validate_add(self, data, xml):
        """Validate add of an element list.  Leaf elements should override
        this."""
        for i in range(0, xml.nr_children_type(clixon_beh.XMLOBJ_TYPE_ELEMENT)):
            c = xml.child_i(i)
            name = c.get_name()
            if name in self.root.children:
                self.children[name].validate_add(data, c)
        return

    def validate_del(self, data, xml):
        """Validate delete of an element list.  Leaf elements should override
        this."""
        for i in range(0, xml.nr_children_type(clixon_beh.XMLOBJ_TYPE_ELEMENT)):
            c = xml.child_i(i)
            name = c.get_name()
            if name in self.root.children:
                self.children[name].validate_del(data, c)
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
            oxmlf = 0
            if oxml:
                oxmlf = oxml.get_flags(clixon_beh.XMLOBJ_FLAG_FULL_MASK)
            nxmlf = 0
            if nxml:
                nxmlf = nxml.get_flags(clixon_beh.XMLOBJ_FLAG_FULL_MASK)
            if oxmlf & clixon_beh.XMLOBJ_FLAG_DEL:
                c = oxml.get_name()
                if c in self.children:
                    self.children[c].validate_del(data, c)
                oi += 1
                oxml = origxml.child_i(oi)
                pass
            elif nxmlf & clixon_beh.XMLOBJ_FLAG_ADD:
                c = oxml.get_name()
                if c in self.children:
                    self.children[c].validate_add(data, c)
                ni += 1
                nxml = newxml.child_i(ni)
                pass
            else:
                if (oxmlf & clixon_beh.XMLOBJ_FLAG_CHANGE and
                        nxmlf & clixon_beh.XMLOBJ_FLAG_CHANGE):
                    c = oxml.get_name()
                    if c in self.children:
                        self.children[c].validate(data, oxml, nxml)
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
        if clixon_beh.restore_priv() < 0:
            raise Exception(self.name + ": Can't restore privileges.")
        try:
            self.priv(op)
        finally:
            if clixon_beh.drop_priv_temp(euid) < 0:
                raise Exception(self.name + ": Can't drop privileges.")

    def priv(self, op):
        """Subclasses must override this function for privileged operations."""
        return

    def getxml(self, path, namespace=None):
        """Process a get operation before the path has ended.  We are just
        parsing down the path until we hit then end."""
        xml = "<" + self.name
        if namespace is not None:
            xml += " xmlns=\"" + namespace + "\">"
        else:
            xml += ">"
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
            s = self.children[name].getvalue()
            if s and len(s) > 0:
                xml += "<" + name + ">" + s + "</" + name + ">"
        return xml

    def program_output(self, args):
        """Call a program with the given arguments and return the stdout.
        If it errors, generate an exception with stderr output."""
        p = subprocess.Popen(args, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        (out, err) = p.communicate(timeout=1000)
        rc = p.wait()
        if rc != 0:
            raise Exception(args[0] + " error: " + err)
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

    def getxml(self, path, namespace=None):
        return ""
    
class OpHandler:
    """Handler for Clixon backend.  This can be used directly.  Or a
    handler can descend from this if they need to add the pre_daemon,
    daemon, reset, etc. calls, which are not done in this code.  Note
    that if you override one of the calls below in your code, you
    should still call the method with super().method().

    """

    def __init__(self, namespace, name, children):
        """name is the top-level name of the yang/xml data.  children is a
        map of elements that may be in the top level, see OpBase for
        details.

        """
        self.name = name
        self.namespace = namespace
        self.xmlroot = OpBase(name, children)

    def begin(self, t):
        print("***begin**")
        t.set_userdata(Data())
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

    def statedata(self, nsc, xpath):
        print("***statedata**: "+ str(nsc) + " " + xpath)
        path = xpath.split("/")
        if len(path) < 2:
            return(-1, "")
        name = path[1].split(":")
        if len(name) == 1:
            name = name[0]
        else:
            name = name[1]
        if name != self.name:
            return(-1, "")
        return (0, self.xmlroot.getxml(path[2:], namespace=self.namespace))

