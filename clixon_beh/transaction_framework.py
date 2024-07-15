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
together, you write a class that descends from ElemOpBase to handle
that specific thing.

You class will be have validate calls to handle validating your data.
The validate calls should then add operations to the transaction data
to describe what they should do at commit time.  At commit time, each
operation's handler is then called to actually do the operation.  If a
commit fails for some reason, the revert calls for the operations will
be done in reverse order.

The escaping of XML body data is important.  If your getvalue() call
returns text for a body, you need to escape it properly for XML.  If
you set xmlprocvalue to true on your Op, then it will do this for you
automatically.  If that's not possible for some reason, then you will
need to process your data with xmlescape."""

def xmlescape(xmlstr):
    """This is called automatically for leaf-level getvalue() calls, onces
    that have xmlprocvalue set to true, but if you are handling your
    own XML generation, you will need to call this on body text.

    """
    xmlstr = xmlstr.replace("&", "&amp;")
    xmlstr = xmlstr.replace("<", "&lt;")
    xmlstr = xmlstr.replace(">", "&gt;")
    xmlstr = xmlstr.replace("\"", "&quot;")
    xmlstr = xmlstr.replace("'", "&apos;")
    return xmlstr

class Op:
    """This is an operation.  Generally you add this in the validate calls
    when you discover things that need to be done.  and the handler's
    commit function get's called in the commit and revert calls.

    The user can add their own items to this.  For instance, the user
    could have a global object representing everything to be done for
    a specific thing, create it and store it in the transaction data
    under their own name.  Then when new data items come in that are
    related, the user can look in the data, reuse the existing item if
    present, or create one if not present.  User-added items should
    begin with "user".

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
        self.done = False
        self.oldvalue = None

    def commit(self):
        """Commit the operation, basically apply it to the system.  If you
        handle revert, you should store the data to revert in the
        oldvalue member of this object.

        """
        self.handler.commit(self)

    def commit_done(self):
        """Commit the operation, basically apply it to the system.  If you
        handle revert, you should store the data to revert in the
        oldvalue member of this object.

        """
        self.done = True
        self.handler.commit_done(self)

    def revert(self):
        """Revert the operation.  The "revert" member of this is set to True
        here for convenience for the user.

        """
        self.revert = True
        self.handler.revert(self)

class Data:
    """This is data about a transaction.  It holds the list of operations
    and does the full commit/revert operations.  The users can add
    their own data members to this object, if so their names should
    begin with "user".

    """
    def __init__(self):
        self.ops = []

    def add_op(self, handler, opname, value):
        """Add an operation to the operation queue.  These will be done
        in the commit and revert phases.  Returns the Op object that
        was created, the user can add to it if they like."""
        opdata = Op(handler, opname, value)
        self.ops.append(opdata)
        return opdata

    def commit(self):
        for op in self.ops:
            op.commit()

    def commit_done(self):
        for op in self.ops:
            op.commit_done()

    def revert(self):
        for op in reversed(self.ops):
            op.revert()

class ElemOpBase:
    """The base class for operation handler (what goes into an "Op" class
    handler) and an element handler (what gets called from the clixon
    validate call for handling XML elments).  Any operation should
    descend from this class; the commit and revert operations are used
    for operation handling.  Element handling uses the validate,
    getxml, and getvalue calls.  For non-leaf objects, this class can
    be used directly, too.  Leaf element should always override the
    validate methods and getvalue method.  Non-leaf elements, if they
    process a bunch of data together, can override this, too, and also
    probably need to override getxml.

    """
    def __init__(self, name, children = {}, validate_all = False,
                 xmlprocvalue = False, wrapxml = True):
        """name should be the xml tag name for this operations.  children, if
        set, should be a map of the xml elements that can occur in
        this xml element, and their handlers.  If validate_all is set,
        then the clixon flags for add/del/change are ignored and all
        children are handled.  Otherwise handlers are only called for
        children whose XML has the clixon flags set.

        If xmlprocvalue is true, calls to getvalue() will be run
        through the xml escaping code.  Generally leaf classes would
        do this, though any class that just returns raw strings should
        set this, too.

        If wrapxml is True, the return of getvalue() will be wrapped
        with the given name.  If not, the getvalue() call will need to
        wrap the call with the given name.  This is useful for
        returning lists where the getvalue() will return a number of
        the same item.  Those should set wrapxml to False.  Default is
        True.

        """
        self.name = name
        self.children = children
        self.validate_all = validate_all
        self.xmlprocvalue = xmlprocvalue
        self.wrapxml = wrapxml

    def validate_add(self, data, xml):
        """Validate add of an element list.  Leaf elements should override
        this."""
        for i in range(0, xml.nr_children_type(clixon_beh.XMLOBJ_TYPE_ELEMENT)):
            c = xml.child_i(i)
            name = c.get_name()
            if name in self.children:
                self.children[name].validate_add(data, c)
        return

    def validate_del(self, data, xml):
        """Validate delete of an element list.  Leaf elements should override
        this."""
        for i in range(0, xml.nr_children_type(clixon_beh.XMLOBJ_TYPE_ELEMENT)):
            c = xml.child_i(i)
            name = c.get_name()
            if name in self.children:
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
        while oxml or nxml:
            oxmlf = 0
            if oxml:
                oxmlf = oxml.get_flags(clixon_beh.XMLOBJ_FLAG_FULL_MASK)
            nxmlf = 0
            if nxml:
                nxmlf = nxml.get_flags(clixon_beh.XMLOBJ_FLAG_FULL_MASK)
            if oxmlf & clixon_beh.XMLOBJ_FLAG_DEL:
                c = oxml.get_name()
                if c in self.children:
                    self.children[c].validate_del(data, oxml)
                oi += 1
                oxml = origxml.child_i(oi)
                pass
            elif nxmlf & clixon_beh.XMLOBJ_FLAG_ADD:
                c = nxml.get_name()
                if c in self.children:
                    self.children[c].validate_add(data, nxml)
                ni += 1
                nxml = newxml.child_i(ni)
                pass
            else:
                if (self.validate_all or
                         nxmlf & clixon_beh.XMLOBJ_FLAG_CHANGE or
                         oxmlf & clixon_beh.XMLOBJ_FLAG_CHANGE):
                    c = nxml.get_name()
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

    def commit_done(self, op):
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
            value = self.getvalue()
            if self.xmlprocvalue:
                value = xmlescape(value)
            xml += value
        else:
            name = path[0].split(":")
            if len(name) == 1:
                name = name[0]
            else:
                name = name[1]
            if name in self.children:
                xml += self.children[name].getxml(path[1:])
            else:
                raise Exception("Unknown name " + name + " in " + self.name)
        xml += "</" + self.name + ">"
        return xml

    def getvalue(self):
        """Return the xml strings for this node.  Leaf nodes should override
        this and return the value."""
        xml = ""
        for name in self.children:
            s = self.children[name].getvalue()
            if self.children[name].xmlprocvalue:
                s = xmlescape(s)
            if self.children[name].wrapxml and s and len(s) > 0:
                xml += "<" + name + ">" + s + "</" + name + ">"
            else:
                xml += s
        return xml

    def program_output(self, args, timeout=1000):
        """Call a program with the given arguments and return the stdout.
        If it errors, generate an exception with stderr output."""
        p = subprocess.Popen(args, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        (out, err) = p.communicate(timeout)
        rc = p.wait()
        if rc != 0:
            raise Exception(args[0] + " error(" + str(rc) + "): " + err.decode("utf-8"))
        return out.decode("utf-8")

class ElemOpBaseLeaf(ElemOpBase):
    """An Op that is a leaf, set up for such.  Just sets the XML processing
    flag for now.

    """
    def __init__(self, name, validate_all = False, xmlprocvalue = True,
                 wrapxml = True):
        super().__init__(name, validate_all = validate_all,
                         xmlprocvalue = xmlprocvalue, wrapxml = wrapxml)

class ElemOpBaseConfigOnly(ElemOpBaseLeaf):
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

    def getvalue(self):
        return ""

class ElemOpBaseCommitOnly(ElemOpBase):
    """This is used for operations that just are added to the op queue and
    not registered as a child.  Thus they need no validation or getvalue.
    User should override commit and revert.

    """
    def __init__(self, name):
        super().__init__(name)

    def validate_add(self, data, xml):
        raise Exception("abort")

    def validate_del(self, data, xml):
        raise Exception("abort")

    def validate(self, data, origxml, newxml):
        raise Exception("abort")

    def getvalue(self):
        raise Exception("abort")

class ElemOpBaseValidateOnly(ElemOpBase):
    """This is used for operations that are only registered as
    children and never added to a commit queue.  Thus they need no
    commit or revert.  User should override validate and getvalue
    calls.

    This also assumes that the user will rebuild the whole thing they
    are working on, so it ignores deletes and translates validate to
    validate_add by default.  So the user only needs to provide
    validate_add.  This can be overriden, of course.

    """
    def __init__(self, name, children = {}, validate_all = True,
                 xmlprocvalue = False, wrapxml = True):
        super().__init__(name, children, validate_all = validate_all,
                         xmlprocvalue = xmlprocvalue, wrapxml = wrapxml)

    def getvalue(self):
        # We assume a higher-level handler builds the entire value, so
        # this should never get hit.  Override if not so.
        raise Exception("abort")

    def commit(self, op):
        raise Exception("abort")

    def revert(self, xml):
        raise Exception("abort")

class ElemOpBaseValidateOnlyLeaf(ElemOpBaseValidateOnly):
    """This is used for operations that just are only registered as
    children and never added to a commit queue.  Thus they need no
    commit or revert.  User should override validate and getvalue
    calls.

    This also assumes that the user will rebuild the whole thing they
    are working on, so it ignores deletes and translates validate to
    validate_add by default.  So the user only needs to provide
    validate_add.  This can be overriden, of course.

    """
    def __init__(self, name, children = {}, validate_all = True,
                 wrapxml = True):
        super().__init__(name, children, validate_all = validate_all,
                         xmlprocvalue = True, wrapxml = wrapxml)

    def validate_del(self, data, xml):
        # We assume in this case that the user is doing a full rebuild of
        # the data, so deletes can just be ignored.  If not, the user
        # should override this.
        return

    def validate(self, data, origxml, newxml):
        # Again, assuming a full rebuild of the data, so a validate
        # is the same as an add.  Override if not so.
        self.validate_add(data, newxml)

class ElemOpBaseValueOnly(ElemOpBaseLeaf):
    """This is used for operations that are only registered as
    leaf system state values, no validate, no commit.  The user should
    override getvalue.

    """
    def __init__(self, name, validate_all = True, wrapxml = True):
        super().__init__(name, validate_all = validate_all, xmlprocvalue = True,
                         wrapxml = wrapxml)

    def validate_add(self, data, xml):
        raise Exception("Cannot modify system state")

    def validate_del(self, data, xml):
        raise Exception("Cannot modify system state")

    def validate(self, data, origxml, newxml):
        raise Exception("Cannot modify system state")

    def commit(self, op):
        raise Exception("abort")

    def revert(self, data, xml):
        raise Exception("abort")

    def getxml(self, path, namespace=None):
        return ""

    def getvalue(self):
        return ""

class TopElemHandler:
    """Handler for Clixon backend.  This can be used directly.  Or a
    handler can descend from this if they need to add the pre_daemon,
    daemon, reset, etc. calls, which are not done in this code.  Note
    that if you override one of the calls below in your code, you
    should still call the method with super().method().

    """

    def __init__(self, name, namespace, children):
        """children is a map of elements that may be in the top level, see
        ElemOpBase for details.

        """
        self.name = name
        self.namespace = namespace
        self.xmlroot = ElemOpBase("TopLevel", children)

    # Not implemented, will just default to doing nothing:
    # def pre_daemon(self):
    # def daemon(self):
    # def reset(self, cb):
    # def lockdb(self, db, lock, id):
    # def exit(self):
    # def complete(self, t):
    # def end(self, t):
    # def abort(self, t):
    # You should provide methods for these if you need them.

    def begin(self, t):
        t.set_userdata(Data())
        return 0

    def validate(self, t):
        if False: # For debugging
            print(str(t.orig_str()))
            print(str(t.new_str()))
        data = t.get_userdata()

        # Handle the top-level name.  There can only be one, and it has to
        # match one of the entries.
        origxml = t.orig_xml()
        newxml = t.new_xml()
        if origxml:
            name = origxml.get_name()
        else:
            name = newxml.get_name()
        if name in self.xmlroot.children:
            self.xmlroot.children[name].validate(data, origxml, newxml)
        else:
            raise Exception("Unknown name " + name + " in " + self.name)
        return 0

    def commit(self, t):
        data = t.get_userdata()
        data.commit()
        return 0

    def commit_done(self, t):
        data = t.get_userdata()
        data.commit_done()
        return 0

    def revert(self, t):
        data = t.get_userdata()
        data.revert()
        return 0

    def statedata(self, nsc, xpath):
        path = xpath.split("/")
        if len(path) < 2:
            return(-1, "")

        # Handle the top-level name.  There can only be one, and it has to
        # match one of the entries.
        name = path[1].split(":")
        if len(name) == 1:
            name = name[0]
        else:
            name = name[1]
        if name in self.xmlroot.children:
            xml = self.xmlroot.children[name].getxml(path[2:],
                                                     namespace = self.namespace)
        else:
            raise Exception("Unknown name " + name + " in " + self.name)
        return (0, xml)

