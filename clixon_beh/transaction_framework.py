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
v
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

class Op(PrivOp):
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
    def __init__(self, handler, opname, value, priv=False):
        """The handler's commit and revert methods will be called during the
        commit and revert operations.  opname is a convenience name,
        and value may be anything the user desires.

        If priv is True, then all the operation will be done with
        privileges raised.

        """

        self.handler = handler
        self.opname = opname
        self.value = value
        self.revert = False
        self.finish = False
        self.done = False
        self.end = False
        self.oldvalue = None
        self.priveleged = priv
        return

    def priv(self, op):
        if self.end:
            self.handler.end(self)
        elif self.revert:
            self.handler.revert(self)
        elif self.done:
            self.handler.commit_done(self)
        elif self.finish:
            self.handler.commit(self)
            pass
        pass

    def commit(self):
        """Commit the operation, basically apply it to the system.  If you
        handle revert, you should store the data to revert in the
        oldvalue member of this object.  This sets the "finish" member
        of this object to "True".

        """
        self.finish = True
        if self.priveleged:
            self.do_priv(self)
        else:
            self.handler.commit(self)
            pass
        return

    def commit_done(self):
        """Commit the operation, basically apply it to the system.  If
        you handle revert, you should store the data to revert in the
        oldvalue member of this object.  This sets the "done" member
        of this object to "True".

        """
        self.done = True
        if self.priveleged:
            self.do_priv(self)
        else:
            self.handler.commit_done(self)
            pass
        return

    def do_revert(self):
        """Revert the operation.  The "revert" member of this is set to True
        here for convenience for the user.

        """
        self.revert = True
        if self.priveleged:
            self.do_priv(self)
        else:
            self.handler.revert(self)
            pass
        return

    def do_end(self):
        """End the operation.  Useful for cleanup.  This sets the
        "end" member of this operation to True.

        """
        self.end = True
        if self.priveleged:
            self.do_priv(self)
        else:
            self.handler.end(self)
            pass
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

    def add_op(self, handler, opname, value, priv=False):
        """Add an operation to the operation queue.  These will be done
        in the commit and revert phases.  Returns the Op object that
        was created, the user can add to it if they like."""
        opdata = Op(handler, opname, value, priv=priv)
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
            op.do_revert()
            pass
        return

    def end(self):
        for op in self.ops:
            op.do_end()
            pass
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
            raise RPCError("application", "operation-failed", "error",
                           args[0] + " error(" + str(rc) + "): " + err.decode("utf-8"))
        return decoder(out)

    pass

class YangType(Enum):
    # Types of elements, etype in the init method
    NOTYPE = 0
    CONTAINER = 1
    LEAF = 2
    LIST = 3
    LEAFLIST = 4
    CHOICE = 5

    pass

def parsepathentry(e):
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

class GetData:
    """This is the base class to pass into the getvalue, getonevalue,
    and getxml methods below.  It contains getnonconfig, which sets
    whether to return nonconfig data along with the config data.  You
    may add your own data into it.  More items may be added in the
    future.

    """
    def __init__(self, getnonconfig=True):
        self.getnonconfig = getnonconfig
        return

    pass

def xml_full_index(o, data, vdata):
    xml = ""
    for i in o.fetch_full_index(vdata):
        if o.xmlgvprocvalue:
            s = xmlescape(o.getonevalue(data, vdata=i))
        else:
            s = str(o.getonevalue(data, vdata=i))
            pass
        if o.wrapgvxml:
            s = o.xmlwrap(s)
            pass
        xml += s
        pass
    return xml

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
    def __init__(self, name, etype, children = None, validate_all = False,
                 xmlprocvalue = None, wrapxml = None, namespace = None,
                 isconfig = True, parent = None):
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

        The allocater should set isconfig to False for items that are
        "config false" in the YANG.  In that case, getvalue() or
        getxml() will not be called for the object if
        data.getnonconfig is False.

        """
        self.etype = etype
        self.wrapgvxml = True
        self.xmlgvprocvalue = False
        self.namespace = namespace
        self.parent = parent
        self.isconfig = isconfig
        if etype == YangType.CONTAINER or etype == YangType.CHOICE:
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

    def xmlheader(self):
        if self.namespace is not None:
            return "<" + self.name + " xmlns=\"" + self.namespace + "\">"
        else:
            return "<" + self.name + ">"
        return

    def xmlwrap(self, xml):
        if len(xml) == 0:
            return ""
        return self.xmlheader() + xml + "</" + self.name + ">"

    def validate_add(self, data, xml):
        """Validate add of an element list.  Leaf elements should override
        this."""
        for i in range(0, xml.nr_children_type(clixon_beh.XMLOBJ_TYPE_ELEMENT)):
            x = xml.child_i(i)
            if x.get_type() != clixon_beh.XMLOBJ_TYPE_ELEMENT:
                continue
            self.children.validate_add(data, x)
            pass
        return

    def validate_del(self, data, xml):
        """Validate delete of an element list.  Leaf elements should override
        this."""
        for i in range(0, xml.nr_children_type(clixon_beh.XMLOBJ_TYPE_ELEMENT)):
            x = xml.child_i(i)
            if x.get_type() != clixon_beh.XMLOBJ_TYPE_ELEMENT:
                continue
            self.children.validate_del(data, x)
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
                self.children.validate_del(data, oxml)
                oi += 1
                oxml = origxml.child_i(oi)
            elif nxmlf & clixon_beh.XMLOBJ_FLAG_ADD:
                self.children.validate_add(data, nxml)
                ni += 1
                nxml = newxml.child_i(ni)
            else:
                if (self.validate_all or
                        nxmlf & clixon_beh.XMLOBJ_FLAG_CHANGE or
                        oxmlf & clixon_beh.XMLOBJ_FLAG_CHANGE):
                    self.children.validate(data, oxml, nxml)
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

    def end(self, op):
        return

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

    def getxml(self, data, path, indexname=None, index=None, vdata=None):
        """Process a get operation before the path has ended.  We are
        just parsing down the path until we hit then end.  indexname
        and index are for lists, they provide the index name and the
        index for a list entry.  In that case this must be a list and
        it will call the fetch_index() method on this class to get the
        vdata.

        The data parm sets carries information about the transaction.
        The getnonconfig element is used to know if the requester
        wants nonconfig data in addition to config data.

        """
        if not data.getnonconfig and not self.isconfig:
            return ""
        if self.indexed:
            if index is None:
                # Return the whole list.
                return xml_full_index(self, data, vdata)
            vdata = self.fetch_index(indexname, index, vdata)
            if vdata is None:
                return ""
            pass
        elif indexname is not None:
            raise Exception("Index is set for " + self.name +
                            " which doesn't support indexes")

        if len(path) == 0:
            if self.children is None:
                xml = self.getvalue(data, vdata=vdata)
            else:
                xml = self.children.getonevalue(data, vdata=vdata)
        else:
            xml = self.children.getxml(data, path, vdata=vdata)
            pass
        xml = self.xmlwrap(xml)
        return xml

    def getonevalue(self, data, vdata=None):
        if not data.getnonconfig and not self.isconfig:
            return ""
        return self.children.getonevalue(data, vdata=vdata)

    def getvalue(self, data, vdata=None):
        """Return the xml strings for this node.  Leaf nodes should
        override this and return the value.

        """
        if not data and not self.isconfig:
            return ""
        if self.indexed:
            xml = xml_full_index(self, data, vdata)
        else:
            xml = str(self.getonevalue(data, vdata=vdata))
            if self.wrapgvxml:
                xml = self.xmlwrap(xml)
            pass
        return xml

    def find_path(self):
        """Return the full path for the element by getting the parents
        path and appending our name.

        """
        if not self.parent:
            return ""
        return self.parent.find_path() + "/" + self.name

    def find_namespace(self):
        """Return the namespace for the element.  If this element's
        namespace isn't set, return the parent's.

        """
        e = self
        while e.namespace is None:
            if e.parent is None:
                break;
            e = e.parent
            pass
        return e.namespace

    def get_etype_str(self):
        """"Return a string name for the etype.  Matches the names
        that clixon gives for the YANG statements.

        """
        if self.etype == YangType.CONTAINER:
            return "container"
        elif self.etype == YangType.LEAF:
            return "leaf"
        elif self.etype == YangType.LIST:
            return "list"
        elif self.etype == YangType.LEAFLIST:
            return "leaf-list"
        elif self.etype == YangType.CHOICE:
            return "choice"
        return None # Shouldn't be possible

    pass

class YangElemChoice(YangElem):
    """This is for "choice" elements, which are kind of invisible in
    the XML.

    """

    def __init__(self, name, children = None, parent = None):
        super().__init__(name, YangType.CHOICE, children = children,
                         parent = parent)
        return

    pass

class YangElemConfigOnly(YangElem):
    """If a leaf element is config only, there's no need to do much, it's
    stored in the main database only.

    """

    def __init__(self, name, etype = YangType.LEAF):
        super().__init__(name, etype)
        return

    def validate_add(self, data, xml):
        return

    def validate_del(self, data, xml):
        return

    def validate(self, data, origxml, newxml):
        return

    def getxml(self, data, path, indexname=None, index=None, value=None):
        return ""

    def getonevalue(self, data, vdata=None):
        return ""

    def getvalue(self, data, vdata=None):
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

    def getonevalue(self, data, vdata=None):
        raise Exception("abort")

    def getvalue(self, data, vdata=None):
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
        if self.etype == YangType.LEAF or self.etype == YangType.LEAFLIST:
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

class YangElemValidateOnlyLeafList(YangElemValidateOnly):
    """This is like ValidateOnly, but has helper functions for leaf
    lists.  Leaf lists should generally use this.

    This code assumes that the data items in the list from
    fetch_full_index() and validate_fetch_full_index() are simply the
    string items in the leaf list.  That's going to be the most common
    case.  If that's not the case, these methods can be overridden.

    """
    def validate_add(self, data, xml):
        """We fetch the full list and add the string if it's not
        already there.

        """
        v = xml.get_body()
        l = self.validate_fetch_full_index(data)
        if v not in l:
            l.append(v)
            pass
        return

    def validate_del(self, data, xml):
        """We fetch the full list and delete the string if it's there.

        """
        v = xml.get_body()
        l = self.validate_fetch_full_index(data)
        if v in l:
            l.remove(v)
            pass
        return

    # In parent class, validate() calls validate_add() on a leaf list,
    # which is what we want.

    # Since this is a list (leaf-list), we don't use getvalue()
    # because we have to deal with indexes.  Instead, we have three
    # functions, on to fetch the value of a specific index (if it
    # exists), on to return the value from a single index (which is
    # simple, because it's just a value) and one to fetch all values
    # in the index.

    def fetch_index(self, indexname, index, vdata):
        l = self.fetch_full_index(vdata)
        if index in l:
            return index
        return None

    def getonevalue(self, data, vdata):
        return vdata

    def validate_fetch_full_index(self, data):
        """Fetch all values for this list, in the validate case.  You
        must override this method to use this class.  This must return
        a mutable tuple.

        """
        raise Exception("No validate full index function for " + self.name)

    pass

class YangElemValueOnly(YangElem):
    """This is used for operations that are only registered as
    system state values, no validate, no commit.  The leaf users should
    override getvalue.

    """

    def validate_add(self, data, xml):
        raise RPCError("application", "invalid-value", "error",
                       "Could not modify state for " + self.name)

    def validate_del(self, data, xml):
        raise RPCError("application", "invalid-value", "error",
                       "Could not modify state for " + self.name)

    def validate(self, data, origxml, newxml):
        raise RPCError("application", "invalid-value", "error",
                       "Could not modify state for " + self.name)

    def commit(self, op):
        raise Exception("abort")

    def revert(self, data, xml):
        raise Exception("abort")

    pass

class YangElemValueOnlyUnimpl(YangElemValueOnly):
    """This is a value only that always returns an empty string.  This
    can be used for optional things that aren't implemented.

    """

    def getvalue(self, data, vdata=None):
        return ""

class YangElemMap:
    """This is for a non-leaf that contains other elements.  You can
    use this directly if you do not need to do any processing, or you
    can descend from this class if yu need your own handling.  You
    will create one of these for any container, list, etc. that has
    other nodes in it.  Then you will call the add method to add those
    nodes into this object.

    """

    def __init__(self, parent, path):
        self.mapv = {}
        self.parent = parent
        self.path = path
        return

    def add(self, elem):
        self.mapv[elem.name] = elem
        return

    def lookup_elem(self, path):
        """Return the YangElemMap object for the given path.  Returns
        a tuple with three elements, the first is an error (None if no
        error) and the second if the map object (None if an
        error). and the third is the element (None if a error or if the
        path is "/".

        """

        if path == "/":
            spath = []
        else:
            spath = path.split("/")
            if spath[0] != "":
                return ("Path " + path + " does not begin with '/'", None)
            pass
        m = self
        e = None
        for p in spath[1:]:
            if p in m.mapv:
                e = m.mapv[p]
                m = e.children
                if not m:
                    return ("Element " + p + " in path " + path +
                            " is a leaf", None)
                pass
            else:
                return ("Element " + p + " not set in path " + path, None)
            pass
        return (None, m, e)

    def add_elem(self, path, elem):
        """Add an element for the full path, adding intermediate elements
        as necessary.  Return the last map where the element was added.
        """
        (err, m, e) = self.lookup_elem(path)
        if err is not None:
            raise Exception(err)
        if elem.name in m.mapv:
            raise Exception("Duplicate element " + elem.name + " in " + path)
        m.mapv[elem.name] = elem
        elem.parent = e
        return m

    def add_map(self, path, elem):
        if (elem.etype != YangType.CONTAINER and
            elem.etype != YangType.LIST and
            elem.etype != YangType.CHOICE):
            raise Exception("Added map element " + elem.name +
                            " is not container or list")
        m = self.add_elem(path, elem)
        elem.children = YangElemMap(m, path + "/" + elem.name)
        return

    def add_leaf(self, path, elem):
        if elem.etype != YangType.LEAF and elem.etype != YangType.LEAFLIST:
            raise Exception("Added leaf element " + elem.name +
                            " is not a leaf")
        self.add_elem(path, elem)
        return

    def find_child_in_map(self, name):
        if name in self.mapv:
            return self.mapv[name]
        # Choice elements have special handling, we just skip them.
        for c in self.mapv:
            if c.etype == YangType.CHOICE:
                if c.children and name in c.children.mapv:
                    return c.children.mapv[name]
                pass
            pass
        return None

    def validate_add(self, data, xml):
        name = xml.get_name()
        c = self.find_child_in_map(name)
        if c is None:
            raise RPCError("application", "invalid-value", "error",
                           "No element %s in %s " % (name, self.path))
        c.validate_add(data, xml)
        return

    def validate_del(self, data, xml):
        name = xml.get_name()
        c = self.find_child_in_map(name)
        if c is None:
            raise RPCError("application", "invalid-value", "error",
                           "No element %s in %s " % (name, self.path))
        c.validate_del(data, xml)
        return

    def validate(self, data, origxml, newxml):
        if origxml:
            name = origxml.get_name()
        else:
            name = newxml.get_name()
        c = self.find_child_in_map(name)
        if c is None:
            raise RPCError("application", "invalid-value", "error",
                           "No element %s in %s " % (name, self.path))
        c.validate(data, origxml, newxml)
        return

    def getxml(self, data, path, vdata=None):
        (name, indexname, index) = parsepathentry(path[0])
        c = self.find_child_in_map(name)
        if c is None:
            raise RPCError("application", "invalid-value", "error",
                           "No element %s in %s " % (name, self.path))
        x = self.mapv[name]
        if data.getnonconfig or x.isconfig:
            xml = x.getxml(data,
                           path[1:],
                           indexname=indexname,
                           index=index,
                           vdata=vdata)
        else:
            xml = ""
            pass
        return xml

    def getonevalue(self, data, vdata=None):
        xml = ""
        for name in self.mapv:
            if self.mapv[name].etype == YangType.CHOICE:
                s = self.mapv[name].children.getonevalue(data, vdata)
            else:
                x = self.mapv[name]
                if data.getnonconfig or x.isconfig:
                    s = str(x.getvalue(data, vdata=vdata))
                    if x.xmlprocvalue:
                        s = xmlescape(s)
                        pass
                    if x.wrapxml:
                        s = x.xmlwrap(s)
                        pass
                    pass
                else:
                    s = ""
                    pass
                pass
            xml += s
            pass
        return xml

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
        self.children = children
        return

    # Not implemented, will just default to doing nothing:
    # def pre_daemon(self):
    # def daemon(self):
    # def reset(self, cb):
    # def lockdb(self, db, lock, id):
    # def exit(self):
    # def complete(self, t):
    # def abort(self, t):
    # You should provide methods for these if you need them.

    def begin(self, t):
        d = Data()
        d.tf_username = clixon_beh.username_get()
        t.set_userdata(d)
        return 0

    def validate(self, t):
        if False: # For debugging
            print("orig: " + str(t.orig_str()))
            print("new: " + str(t.new_str()))
            pass

        data = t.get_userdata()

        # Handle the top-level name.  There can only be one, and it has to
        # match one of the entries.
        self.children.validate(data, t.orig_xml(), t.new_xml())
        return 0

    def commit(self, t):
        try:
            data = t.get_userdata()
            data.commit()
        except:
            # clixon will not call revert on this plugin if we fail,
            # it's our resposibility to clean up this plugin if we
            # fail.
            self.revert(t)
            raise
        return 0

    def commit_done(self, t):
        data = t.get_userdata()
        data.commit_done()
        return 0

    def revert(self, t):
        data = t.get_userdata()
        data.revert()
        return 0

    def end(self, t):
        data = t.get_userdata()
        data.end()
        return 0

    def statedata(self, nsc, xpath, data = None):
        #print("***Statedata: %s %s" % (xpath, str(nsc)))
        if data is None:
            data = GetData()
        if xpath == "/":
            # Get statedata for all top-level elements.
            xmlt = []
            for name in self.children.mapv:
                rv = self.statedata(nsc, "/" + name, data = data)
                if rv[0] < 0:
                    return rv;
                if len(rv[1]) > 0:
                    xmlt.append(rv[1])
                    pass
                pass
            xmlt = tuple(xmlt)
            pass
        else:
            path = xpath.split("/")
            if len(path) < 2:
                return(-1, "")
            path = path[1:] # Get rid of the empty thing before the first /

            # Handle the top-level name.  There can only be one, and
            # it has to match one of the entries.
            xmlt = self.children.getxml(data, path)
            pass
        return (0, xmlt)

    def system_only(self, nsc, xpath):
        return (0, "")

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

def handle_err(exc, value, tb):
    if exc == RPCError:
        # Pre-python 3.12, value and traceback should be set.
        traceback.print_exception(exc, value, tb)
        clixon_beh.rpc_err(value.ns, value.rtype, value.tag, value.info,
                           value.severity, value.message)
    elif exc.__class__ == RPCError:
        traceback.print_exception(exc)
        clixon_beh.rpc_err(exc.ns, exc.rtype, exc.tag, exc.info, exc.severity,
                           exc.message)
    else:
        f = io.StringIO()
        if exc.__class__ == type:
            traceback.print_exception(exc, value, tb, file=f)
        else:
            traceback.print_exception(exc, file=f)
            pass

        # Flip the order of the traceback, the most important info is
        # last, but it will get truncated so put the most important
        # info first.
        v = []
        for l in f.getvalue().split("\n"):
            if len(l) == 0:
                pass
            elif l.startswith("Traceback"):
                # Remove "Traceback (most recent call last):"
                pass
            elif l.startswith("    "):
                # Lines starting with four spaces are code lines and go
                # after the line location.
                v.insert(1, l)
            else:
                v.insert(0, l)
                pass
            pass
        v.insert(1, "Traceback (most recent call first):")
        v.append("")
        v.insert(0, "")
        clixon_beh.err(clixon_beh.OE_PLUGIN, 0, "\n".join(v))
        pass
    return

clixon_beh.set_err_handler(handle_err)

#
# The code below is for validating the build tree against the YANG specification
# it should implement.
#

def lookup_yang_mount(mount):
    y = clixon_beh.get_yang_base()
    y = y.child_i(0)
    for i in range(0, y.nr_children()):
        c = y.child_i(i)
        if c.keyword_get() == "yang-specification" and c.argument_get() == mount:
            return c
        pass
    return None

def lookup_yang_module(mount, module):
    y = lookup_yang_mount(mount)
    if y is None:
        return None
    for i in range(0, y.nr_children()):
        c = y.child_i(i)
        if c.keyword_get() == "module" and c.argument_get() == module:
            return c
        pass
    return None

yang_valid_children = [
    "container",
    "list",
    "leaf",
    "leaf-list",
    "choice",
    ]
def yang_valid_child(y):
    """Validate if the child is valid.  First make sure it is actually
    enabled if there is a if-feature statement.

    """
    for i in range(0, y.nr_children()):
        c = y.child_i(i)
        if not c.keyword_get() == "feature":
            continue
        if not c.cv_get_feature_enabled():
            return False
        pass
    key = y.keyword_get()
    return key in yang_valid_children

def check_elem_against_yang(mount, path, e, y):
    rv = True
    ykey = y.keyword_get()
    ekey = e.get_etype_str()
    if ykey != ekey:
        clixon_beh.log(clixon_beh.LOG_TYPE_ERR,
                       "yangcheck %s:%s: type mismatch, yang is %s elem is %s"
                       % (mount, path, ykey, ekey))
        rv = False
        pass
    ens = e.find_namespace()
    yns = y.find_mynamespace()
    if yns != ens:
        clixon_beh.log(clixon_beh.LOG_TYPE_ERR,
                       "yangcheck %s:%s: namespace mismatch, yang is %s elem is %s"
                       % (mount, path, yns, ens))
        rv = False
        pass
    if not yang_check_children(mount, path, e.children, y):
        rv = False
        pass
    return rv

def yang_add_children(ychildren, y):
    for i in range(0, y.nr_children()):
        c = y.child_i(i)
        key = c.keyword_get()
        if key == "case":
            # We just pass through case elements.
            yang_add_children(ychildren, c)
        elif yang_valid_child(c):
            ychildren[c.argument_get()] = c
            pass
        pass
    return ychildren

def yang_check_children(mount, path, m, y):
    rv = True
    if m is None:
        m = {}
    else:
        m = m.mapv
        pass
    ychildren = {}
    yang_add_children(ychildren, y)
    for i in m:
        if i not in ychildren:
            clixon_beh.log(clixon_beh.LOG_TYPE_ERR,
                           "yangcheck %s:%s: %s in elem, not in yang"
                           % (mount, path, i))
            rv = False
        else:
            if not check_elem_against_yang(mount, path + "/" + i,
                                           m[i], ychildren[i]):
                rv = False
                pass
            del ychildren[i]
            pass
        pass
    for i in ychildren:
        clixon_beh.log(clixon_beh.LOG_TYPE_ERR,
                       "yangcheck %s:%s: %s in yang, not in elem"
                       % (mount, path, i))
        rv = False
        pass
    return rv

def check_topmap_against_yang(tophandler, mount):
    """This is the main function, call it with the top-level handler
    for your implementation, the mount (usually "data") and the
    top-level name of the specification you are implementing.

    """

    y = lookup_yang_module(mount, tophandler.name)
    if y is None:
        clixon_beh.log(clixon_beh.LOG_TYPE_ERR,
                       "yangcheck %s:%s: Unable to find module" %
                       (mount, tophandler.name))
        return False
    return yang_check_children(mount, "/" + tophandler.name,
                               tophandler.children, y)
