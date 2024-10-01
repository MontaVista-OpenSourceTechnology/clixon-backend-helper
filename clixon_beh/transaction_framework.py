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
import io
import traceback
import clixon_beh
from enum import Enum

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
        return

    def commit(self):
        """Commit the operation, basically apply it to the system.  If you
        handle revert, you should store the data to revert in the
        oldvalue member of this object.

        """
        self.handler.commit(self)
        return

    def commit_done(self):
        """Commit the operation, basically apply it to the system.  If you
        handle revert, you should store the data to revert in the
        oldvalue member of this object.

        """
        self.done = True
        self.handler.commit_done(self)
        return

    def revert(self):
        """Revert the operation.  The "revert" member of this is set to True
        here for convenience for the user.

        """
        self.revert = True
        self.handler.revert(self)
        return

    pass

class Data:
    """This is data about a transaction.  It holds the list of operations
    and does the full commit/revert operations.  The users can add
    their own data members to this object, if so their names should
    begin with "user".

    """
    def __init__(self):
        self.ops = []
        return

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
            pass
        return

    def commit_done(self):
        for op in self.ops:
            op.commit_done()
            pass
        return

    def revert(self):
        for op in reversed(self.ops):
            op.revert()
            pass
        return

    pass

class PrivOp:
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
            pass
        return

    def priv(self, op):
        """Subclasses must override this function for privileged operations."""
        return

    pass

class ProgOut:
    def program_output(self, args, timeout=1000,
                       decoder = lambda x : x.decode("utf-8")):
        """Call a program with the given arguments and return the stdout.
        If it errors, generate an exception with stderr output."""
        p = subprocess.Popen(args, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        (out, err) = p.communicate(timeout)
        rc = p.wait()
        if rc != 0:
            raise Exception(args[0] + " error(" + str(rc) + "): " + err.decode("utf-8"))
        return decoder(out)

    pass

class YangType(Enum):
    # Types of elements, etype in the init method
    NOTYPE = 0
    CONTAINER = 1
    LEAF = 2
    LIST = 3
    LEAFLIST = 4

    pass

class YangElem(PrivOp, ProgOut):
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
    def __init__(self, name, etype, children = {}, validate_all = False,
                 xmlprocvalue = None, wrapxml = None, namespace = None):
        """name should be the xml tag name for this operations.  children, if
        set, should be a map of the xml elements that can occur in
        this xml element, and their handlers.  If validate_all is set,
        then the clixon flags for add/del/change are ignored and all
        children are handled.  Otherwise handlers are only called for
        children whose XML has the clixon flags set.

        The namespace value sets the namespace for the XML node.  If
        None, no namespace will be added.  Otherwise the namespace
        will be added to the node when generated.

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
        self.etype = etype
        self.wrapgvxml = True
        self.xmlgvprocvalue = False
        self.namespace = namespace
        if etype == YangType.CONTAINER:
            self.indexed = False
            self.xmlprocvalue = False
            self.wrapxml = False
        elif etype == YangType.LEAF:
            self.indexed = False
            self.xmlprocvalue = True
            self.wrapxml = True
        elif etype == YangType.LIST:
            self.indexed = True
            self.xmlprocvalue = False
            self.wrapxml = False
        elif etype == YangType.LEAFLIST:
            self.indexed = True
            self.xmlprocvalue = True
            self.wrapxml = True
        else:
            raise Exception("Invalid etype: " + str(etype))

        self.name = name
        self.children = children
        self.validate_all = validate_all
        if xmlprocvalue is not None:
            self.xmlprocvalue = xmlprocvalue
            pass
        if wrapxml is not None:
            self.wrapxml = wrapxml
            pass
        if etype == YangType.LEAFLIST:
            # Leaf lists work a little different, we use the xml wrapping
            # in getvalue(), not the one in getonevalue().
            self.wrapgvxml = self.wrapxml
            self.wrapxml = False
            self.xmlgvprocvalue = self.xmlprocvalue
            self.xmlprocvalue = False
            pass
        return

    def validate_add(self, data, xml):
        """Validate add of an element list.  Leaf elements should override
        this."""
        for i in range(0, xml.nr_children_type(clixon_beh.XMLOBJ_TYPE_ELEMENT)):
            c = xml.child_i(i)
            name = c.get_name()
            if name in self.children:
                self.children[name].validate_add(data, c)
                pass
            pass
        return

    def validate_del(self, data, xml):
        """Validate delete of an element list.  Leaf elements should override
        this."""
        for i in range(0, xml.nr_children_type(clixon_beh.XMLOBJ_TYPE_ELEMENT)):
            c = xml.child_i(i)
            name = c.get_name()
            if name in self.children:
                self.children[name].validate_del(data, c)
                pass
            pass
        return

    def validate(self, data, origxml, newxml):
        """Validate an element list.  Leaf elements should override this."""
        oi = 0
        if origxml:
            oxml = origxml.child_i(oi)
        else:
            oxml = None
            pass
        ni = 0
        if newxml:
            nxml = newxml.child_i(ni)
        else:
            nxml = None
            pass
        while oxml or nxml:
            oxmlf = 0
            if oxml:
                oxmlf = oxml.get_flags(clixon_beh.XMLOBJ_FLAG_FULL_MASK)
                pass
            nxmlf = 0
            if nxml:
                nxmlf = nxml.get_flags(clixon_beh.XMLOBJ_FLAG_FULL_MASK)
                pass
            if oxmlf & clixon_beh.XMLOBJ_FLAG_DEL:
                c = oxml.get_name()
                if c in self.children:
                    self.children[c].validate_del(data, oxml)
                    pass
                oi += 1
                oxml = origxml.child_i(oi)
            elif nxmlf & clixon_beh.XMLOBJ_FLAG_ADD:
                c = nxml.get_name()
                if c in self.children:
                    self.children[c].validate_add(data, nxml)
                    pass
                ni += 1
                nxml = newxml.child_i(ni)
            else:
                if (self.validate_all or
                    nxmlf & clixon_beh.XMLOBJ_FLAG_CHANGE or
                    oxmlf & clixon_beh.XMLOBJ_FLAG_CHANGE):
                    c = nxml.get_name()
                    if c in self.children:
                        self.children[c].validate(data, oxml, nxml)
                        pass
                    pass
                if oxml:
                    oi += 1
                    oxml = origxml.child_i(oi)
                    pass
                if nxml:
                    ni += 1
                    nxml = newxml.child_i(ni)
                    pass
                pass
            pass
        return

    def commit(self, op):
        return

    def commit_done(self, op):
        return

    def revert(self, op):
        return

    def parsepathentry(self, e):
        """Parse value in the form "[pfx:]name[\\[[pfx:]indexname='value'\\]]"
        Ignore the prefixes, get the name, indexname, and value.
        """
        name = e.split(":", 1)
        indexname = None
        index = None
        if len(name) == 1:
            name = name[0]
        elif "[" in name[1]:
            (name, index) = name[1].split("[", 1)
            index = index[:-1] # Remove the ']' at the end
            if ':' in name:
                name = name.split(":")[1]
                pass
            (indexname, index) = index.split("=", 1)
            if ':' in indexname:
                indexname = indexname.split(":")[1]
                pass
            index = index[1:-1] # remove the quotes
        else:
            name = name[1]
            pass
        return (name, indexname, index)

    def fetch_index(self, indexname, index, vdata):
        """Fetch the value data (vdata) for the given index.  You must
        override this method if you are a list.

        """
        raise Exception("No index function for " + self.name)

    def fetch_full_index(self, vdata):
        """Fetch all values for this list.  You must override this method
        if you are a list.

        """
        raise Exception("No full index function for " + self.name)

    def xmlheader(self, name, namespace):
        if namespace is not None:
            return "<" + name + " xmlns=\"" + namespace + "\">"
        else:
            return "<" + name + ">"
        return

    def getxml(self, path, indexname=None, index=None, vdata=None):
        """Process a get operation before the path has ended.  We are
        just parsing down the path until we hit then end.  indexname
        and index are for lists, they provide the index name and the
        index for a list entry.  In that case this must be a list and
        it will call the fetch_index() method on this class to get the
        vdata.

        """
        if self.indexed:
            if index is None:
                raise Exception("No index is set for " + self.name)
            vdata = self.fetch_index(indexname, index, vdata)
            if vdata is None:
                return ""
            pass
        elif indexname is not None:
            raise Exception("Index is set for " + self.name +
                            " which doesn't support indexes")

        xml = self.xmlheader(self.name, self.namespace)
        if len(path) == 0:
            value = self.getonevalue(vdata=vdata)
            if self.xmlprocvalue:
                value = xmlescape(value)
                pass
            xml += value
        else:
            (name, index, indexname) = self.parsepathentry(path[0])
            if name in self.children:
                xml += self.children[name].getxml(path[1:],
                                                  indexname=indexname,
                                                  index=index,
                                                  vdata=vdata)
            else:
                raise Exception("Unknown name " + name + " in " + self.name)
            pass
        xml += "</" + self.name + ">"
        return xml

    def getonevalue(self, vdata=None):
        xml = ""
        for name in self.children:
            s = self.children[name].getvalue(vdata)
            if len(s) > 0:
                if self.children[name].xmlprocvalue:
                    s = xmlescape(s)
                    pass
                if self.children[name].wrapxml:
                    namespace = self.children[name].namespace
                    xml += (self.xmlheader(name, namespace) +
                            s + "</" + name + ">")
                else:
                    xml += s
                    pass
                pass
            pass
        return xml

    def getvalue(self, vdata=None):
        """Return the xml strings for this node.  Leaf nodes should override
        this and return the value."""
        xml = ""
        if self.indexed:
            for i in self.fetch_full_index(vdata):
                if self.wrapgvxml:
                    xml += self.xmlheader(self.name, self.namespace)
                    pass
                if self.xmlgvprocvalue:
                    xml += xmlescape(self.getonevalue(vdata=i))
                else:
                    xml += self.getonevalue(vdata=i)
                    pass
                if self.wrapgvxml:
                    xml += "</" + self.name + ">"
                    pass
                pass
            pass
        else:
            xml = self.getonevalue(vdata=vdata)
            if len(xml) > 0 and self.wrapgvxml:
                xml = (self.xmlheader(self.name, self.namespace) +
                       xml + "</" + self.name + ">")
            pass
        return xml

    pass

class YangElemConfigOnly(YangElem):
    """If a leaf element is config only, there's no need to do much, it's
    stored in the main database only.

    """

    def __init__(self, name):
        super().__init__(name, YangType.LEAF)
        return

    def validate_add(self, data, xml):
        return

    def validate_del(self, data, xml):
        return

    def validate(self, data, origxml, newxml):
        return

    def getxml(self, path, indexname=None, index=None, value=None):
        return ""

    def getonevalue(self, vdata=None):
        return ""

    def getvalue(self, vdata=None):
        return ""

    pass

class YangElemCommitOnly(YangElem):
    """This is used for operations that just are added to the op queue and
    not registered as a child.  Thus they need no validation or getvalue.
    User should override commit and revert.

    """
    def __init__(self, name):
        self.name = name
        self.etype = YangType.NOTYPE
        return

    def validate_add(self, data, xml):
        raise Exception("abort")

    def validate_del(self, data, xml):
        raise Exception("abort")

    def validate(self, data, origxml, newxml):
        raise Exception("abort")

    def getonevalue(self, vdata=None):
        raise Exception("abort")

    def getvalue(self, vdata=None):
        raise Exception("abort")

    pass

class YangElemValidateOnly(YangElem):
    """This is used for operations that are only registered as
    children and never added to a commit queue.  Thus they need no
    commit or revert.  User should override the validate call.

    This also assumes that the user will rebuild the whole thing they
    are working on, so it ignores deletes and translates validate to
    validate_add by default.  So the user only needs to provide
    validate_add.  This can be overriden, of course.

    """

    def validate_del(self, data, xml):
        if self.etype == YangType.LEAF:
            # We assume in this case that the user is doing a full rebuild of
            # the data, so deletes can just be ignored.  If not, the user
            # should override this.
            return
        return super().validate_del(data, xml)

    def validate(self, data, origxml, newxml):
        if self.etype == YangType.LEAF:
            # Again, assuming a full rebuild of the data, so a validate
            # is the same as an add.  Override if not so.
            self.validate_add(data, newxml)
            return
        return super().validate(data, origxml, newxml)

    def commit(self, op):
        raise Exception("abort")

    def revert(self, xml):
        raise Exception("abort")

    pass

class YangElemValueOnly(YangElem):
    """This is used for operations that are only registered as
    leaf system state values, no validate, no commit.  The user should
    override getvalue.

    """

    def validate_add(self, data, xml):
        raise tf.RPCError("application", "invalid-value", "error",
                          "Could not modify state for " + self.name)

    def validate_del(self, data, xml):
        raise tf.RPCError("application", "invalid-value", "error",
                          "Could not modify state for " + self.name)

    def validate(self, data, origxml, newxml):
        raise tf.RPCError("application", "invalid-value", "error",
                          "Could not modify state for " + self.name)

    def commit(self, op):
        raise Exception("abort")

    def revert(self, data, xml):
        raise Exception("abort")

    def getxml(self, path, indexname=None, index=None, value=None):
        return ""

    def getvalue(self, vdata=None):
        return ""

    pass

class TopElemHandler:
    """Handler for Clixon backend.  This can be used directly.  Or a
    handler can descend from this if they need to add the pre_daemon,
    daemon, reset, etc. calls, which are not done in this code.  Note
    that if you override one of the calls below in your code, you
    should still call the method with super().method().

    """

    def __init__(self, name, children):
        """children is a map of elements that may be in the top level, see
        YangElem for details.

        """
        self.name = name
        self.xmlroot = YangElem("TopLevel", YangType.CONTAINER, children)
        return

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
            pass

        data = t.get_userdata()

        # Handle the top-level name.  There can only be one, and it has to
        # match one of the entries.
        origxml = t.orig_xml()
        newxml = t.new_xml()
        if origxml:
            name = origxml.get_name()
        else:
            name = newxml.get_name()
            pass
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
            pass
        if name in self.xmlroot.children:
            xml = self.xmlroot.children[name].getxml(path[2:])
        else:
            raise Exception("Unknown name " + name + " in " + self.name)
        return (0, xml)

    pass

class RPC(PrivOp, ProgOut):
    def rpc(self, x, username):
        return (0, "")

    pass

class RPCError(Exception):
    def __init__(self, rtype, tag, severity, message = None,
                 ns = None, info = None):
        self.rtype = rtype
        self.tag = tag
        self.severity = severity
        self.message = message
        self.ns = ns
        self.info = info
        return

    pass

def handle_err(exc):
    if exc.__class__ == RPCError:
        clixon_beh.rpc_err(exc.ns, exc.rtype, exc.tag, exc.info, exc.severity,
                           exc.message)
    else:
        f = io.StringIO()
        traceback.print_exception(exc, file=f)
        clixon_beh.err(clixon_beh.OE_PLUGIN, 0, f.getvalue())
        pass
    return

clixon_beh.set_err_handler(handle_err)
