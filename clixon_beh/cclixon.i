/*
 *
  ***** BEGIN LICENSE BLOCK *****

  Copyright (C) 2024 MontaVista Software, LLC <source@mvista.com>

  Licensed under the Apache License, Version 2.0 (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

  Unless required by applicable law or agreed to in writing, software
  distributed under the License is distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  See the License for the specific language governing permissions and
  limitations under the License.

  Alternatively, the contents of this file may be used under the terms of
  the GNU General Public License Version 3 or later (the "GPL"),
  in which case the provisions of the GPL are applicable instead
  of those above. If you wish to allow use of your version of this file only
  under the terms of the GPL, and not to allow others to
  use your version of this file under the terms of Apache License version 2,
  indicate your decision by deleting the provisions above and replace them with
  the  notice and other provisions required by the GPL. If you do not delete
  the provisions above, a recipient may use your version of this file under
  the terms of any one of the Apache License version 2 or the GPL.

  ***** END LICENSE BLOCK *****

 *
 * Back end helper swig module
 */

%module cclixon

%{

#include <stdbool.h>
#include <clixon_beh.h>
#include <cligen/cligen_buf.h>
#include <clixon/clixon_xml_io.h>

struct xmlobj {
    /*
     * orig_ref points to the top level of the whole XML tree, and
     * refcount counts the number of references to it.  This way we
     * can track all the users of the tree and free the entire thing
     * when we are done.
     */
    unsigned int refcount;
    struct xmlobj *orig_ref;
    cxobj *xml;
};

static struct xmlobj *
xmlobj_new(struct xmlobj *orig_ref, cxobj *xml)
{
    struct xmlobj *rv;

    if (!xml)
	return NULL;
    rv = calloc(1, sizeof(*rv));
    if (!orig_ref)
	orig_ref = rv;
    orig_ref->refcount++;
    rv->orig_ref = orig_ref;
    rv->xml = xml;
    return rv;
}

static void
free_xmlobj(struct xmlobj *x)
{
    x->orig_ref->refcount--;
    if (x->orig_ref->refcount == 0) {
	xml_free(x->orig_ref->xml);
	if (x != x->orig_ref)
	    free(x->orig_ref);
	free(x);
    } else {
	if (x != x->orig_ref)
	    free(x);
    }
}

struct yangobj {
    struct yang_stmt *yang;
};

static struct yangobj *
yangobj_new(yang_stmt *yang)
{
    struct yangobj *rv;

    if (!yang)
	return NULL;
    rv = calloc(1, sizeof(*rv));
    rv->yang = yang;
    return rv;
}

static void
free_yangobj(struct yangobj *y)
{
    free(y);
}

struct yangobj *
get_yang_base()
{
    struct clixon_beh *beh = clixon_beh_get_global_beh();
    struct clixon_handle *h = clixon_beh_get_handle(beh);
    yang_stmt *yang;

    yang = clixon_yang_mounts_get(h);
    if (!yang)
	return NULL;
    return yangobj_new(yang);
}

struct plugin {
    struct clixon_beh_plugin *p;
    PyObject *handler;
};

static PyObject *err_handler;

#if PY_VERSION_HEX < 0x030a0000
static PyObject *
Py_NewRef(PyObject *o)
{
    Py_INCREF(o);
    return o;
}
#endif

static int
pyclixon_call_rv(PyObject *cb, const char *method, PyObject *args,
		 bool optional, PyObject **rv)
{
    int retval = 0;
    PyObject *p, *o = NULL;

    if (PyObject_HasAttrString(cb, method)) {
	p = PyObject_GetAttrString(cb, method);
	o = PyObject_CallObject(p, args);
	Py_DECREF(p);
	if (PyErr_Occurred()) {
	    if (err_handler) {
		PyObject *eargs = PyTuple_New(3);
		PyObject *oret;
#if PY_VERSION_HEX >= 0x030c0000
		PyObject *exc = PyErr_GetRaisedException();

		PyTuple_SET_ITEM(eargs, 0, exc);
		PyTuple_SET_ITEM(eargs, 1, Py_NewRef(Py_None));
		PyTuple_SET_ITEM(eargs, 2, Py_NewRef(Py_None));
#else
		PyObject *type, *value, *traceback;

		PyErr_Fetch(&type, &value, &traceback);
		if (value == NULL)
		    value = Py_NewRef(Py_None);
		if (traceback == NULL)
		    traceback = Py_NewRef(Py_None);
		PyTuple_SET_ITEM(eargs, 0, type);
		PyTuple_SET_ITEM(eargs, 1, value);
		PyTuple_SET_ITEM(eargs, 2, traceback);
#endif
		PyErr_Clear();
		oret = PyObject_CallObject(err_handler, eargs);
		if (oret)
		    Py_DECREF(oret);
		/* Freeing eargs will decrememnt the refcount of all entries. */
		Py_DECREF(eargs);
		if (PyErr_Occurred())
		    goto nohandler;
	    } else {
	    nohandler:
		PyErr_Print();
	    }
	    if (o)
		Py_DECREF(o);
	    retval = -1;
	} else {
	    *rv = o;
	}
    } else if (!optional) {
	PyObject *t = PyObject_GetAttrString(cb, "__class__");
	PyObject *c = PyObject_GetAttrString(t, "__name__");
	const char *class = PyUnicode_AsUTF8(c);

	fprintf(stderr, "clixon_beh:callback: Class '%s' has no method '%s'\n",
		class, method);
    }
    if (args)
	Py_DECREF(args);
    return retval;
}

static int
pyclixon_call_rv_int(PyObject *cb, const char *method,
		     PyObject *args, bool optional)
{
    PyObject *o = NULL;
    int rv = 0;

    rv = pyclixon_call_rv(cb, method, args, optional, &o);
    if (rv)
	return rv;

    if (o) {
	if (!PyLong_Check(o)) {
	    PyObject *t = PyObject_GetAttrString(cb, "__class__");
	    PyObject *c = PyObject_GetAttrString(t, "__name__");
	    const char *classt = PyUnicode_AsUTF8(c);

	    clixon_err(OE_PLUGIN, 0, "pyclixon_beh:callback: "
		    "Class '%s' method '%s' did not return "
		    "an integer\n", classt, method);
	    rv = -1;
	} else {
	    rv = PyLong_AsUnsignedLong(o);
	}
	Py_DECREF(o);
    }

    return rv;
}

static int
pyclixon_beh_pre_daemon(struct clixon_beh_plugin *p)
{
    struct plugin *bp = clixon_beh_plugin_get_cb_data(p);

    return pyclixon_call_rv_int(bp->handler, "pre_daemon", NULL, true);
}

static int
pyclixon_beh_daemon(struct clixon_beh_plugin *p)
{
    struct plugin *bp = clixon_beh_plugin_get_cb_data(p);

    return pyclixon_call_rv_int(bp->handler, "daemon", NULL, true);
}

static int
pyclixon_beh_reset(struct clixon_beh_plugin *p, const char *cb)
{
    struct plugin *bp = clixon_beh_plugin_get_cb_data(p);
    PyObject *args = PyTuple_New(1);

    PyTuple_SET_ITEM(args, 0, PyUnicode_FromString(cb));
    return pyclixon_call_rv_int(bp->handler, "reset", args, true);
}

static int
process_state_return(struct plugin *bp, const char *name,
		     PyObject *o, cxobj *xtop)
{
    PyObject *o1, *o2;
    const char *xmlstr;
    int rv = -1;
    unsigned int i;

    if (!PyTuple_Check(o) || PyTuple_GET_SIZE(o) != 2) {
	PyObject *t = PyObject_GetAttrString(bp->handler, "__class__");
	PyObject *c = PyObject_GetAttrString(t, "__name__");
	const char *classt = PyUnicode_AsUTF8(c);

	clixon_err(OE_PLUGIN, 0, "pyclixon_beh:callback: method %s of "
		   "class %s didn't return a tuple of size 2.",
		   name, classt);
	goto out_err;
    }
    o1 = PyTuple_GET_ITEM(o, 0);
    o2 = PyTuple_GET_ITEM(o, 1);
    if (!PyLong_Check(o1)) {
	PyObject *t = PyObject_GetAttrString(bp->handler, "__class__");
	PyObject *c = PyObject_GetAttrString(t, "__name__");
	const char *classt = PyUnicode_AsUTF8(c);

	clixon_err(OE_PLUGIN, 0, "pyclixon_beh:callback: method %s of "
		   "class %s first element not an int.",
		   name, classt);
	goto out_err;
    }
    if (!(PyUnicode_Check(o2) || PyTuple_Check(o2))) {
	PyObject *t = PyObject_GetAttrString(bp->handler, "__class__");
	PyObject *c = PyObject_GetAttrString(t, "__name__");
	const char *classt = PyUnicode_AsUTF8(c);

	clixon_err(OE_PLUGIN, 0, "pyclixon_beh:callback: method %s of "
		   "class %s second element not a string or tuple of strings",
		   name, classt);
	goto out_err;
    }
    if (PyLong_AsUnsignedLong(PyTuple_GET_ITEM(o, 0)) < 0)
	goto out_err;
    if (PyTuple_Check(o2)) {
	int size = PyTuple_GET_SIZE(o2);
	for (i = 0; i < size; i++) {
	    xmlstr = PyUnicode_AsUTF8AndSize(PyTuple_GET_ITEM(o2, i), NULL);
	    if (!xmlstr) {
		clixon_err(OE_PLUGIN, 0,
			   "pyclixon_beh:callback: Could not convert string "
			   "return %u of method %s to a string.", i, name);
		goto out_err;
	    }
	    if (clixon_xml_parse_string(xmlstr, YB_NONE, NULL, &xtop, NULL) < 0){
		clixon_err(OE_PLUGIN, 0,
			   "pyclixon_beh:callback: Could not parse "
			   "returned XML string %u from %s.", i, name);
		goto out_err;
	    }
	}
    } else {
	xmlstr = PyUnicode_AsUTF8AndSize(o2, NULL);
	if (!xmlstr) {
	    clixon_err(OE_PLUGIN, 0,
		       "pyclixon_beh:callback: Could not convert string "
		       "return of method %s to a string.", name);
	    goto out_err;
	}
	if (clixon_xml_parse_string(xmlstr, YB_NONE, NULL, &xtop, NULL) < 0) {
	    clixon_err(OE_PLUGIN, 0, "pyclixon_beh:callback: Could not parse "
		       "returned XML string from %s.", name);
	    goto out_err;
	}
    }
    rv = 0;
 out_err:
    return rv;
}

static int
pyclixon_beh_statedata(struct clixon_beh_plugin *p,
		       cvec *nsc, char *xpath, cxobj *xtop)
{
    struct plugin *bp = clixon_beh_plugin_get_cb_data(p);
    PyObject *args = PyTuple_New(2);
    PyObject *arg1 = PyTuple_New(cvec_len(nsc));
    PyObject *o = NULL;
    unsigned int i;
    int rv;

    for (i = 0; i < cvec_len(nsc); i++)
	PyTuple_SET_ITEM(arg1, i, PyUnicode_FromString(cvec_i_str(nsc, i)));
    PyTuple_SET_ITEM(args, 0, arg1);
    PyTuple_SET_ITEM(args, 1, PyUnicode_FromString(xpath));
    if (pyclixon_call_rv(bp->handler, "statedata", args, true, &o) < 0)
	return -1;
    if (!o)
	return -1;
    rv = process_state_return(bp, "statedata", o, xtop);
    Py_DECREF(o);

    return rv;
}

static int
pyclixon_beh_system_only(struct clixon_beh_plugin *p,
			 cvec *nsc, char *xpath, cxobj *xtop)
{
    struct plugin *bp = clixon_beh_plugin_get_cb_data(p);
    PyObject *args = PyTuple_New(2);
    PyObject *arg1 = PyTuple_New(cvec_len(nsc));
    PyObject *o = NULL;
    unsigned int i;
    int rv;

    for (i = 0; i < cvec_len(nsc); i++)
	PyTuple_SET_ITEM(arg1, i, PyUnicode_FromString(cvec_i_str(nsc, i)));
    PyTuple_SET_ITEM(args, 0, arg1);
    PyTuple_SET_ITEM(args, 1, PyUnicode_FromString(xpath));
    if (pyclixon_call_rv(bp->handler, "system_only", args, true, &o) < 0)
	return -1;
    if (!o)
	return -1;
    rv = process_state_return(bp, "system_only", o, xtop);
    Py_DECREF(o);

    return rv;
}

static int
pyclixon_beh_lockdb(struct clixon_beh_plugin *p,
		    const char *db, int lock, int id)
{
    struct plugin *bp = clixon_beh_plugin_get_cb_data(p);
    PyObject *args = PyTuple_New(3);

    PyTuple_SET_ITEM(args, 0, PyUnicode_FromString(db));
    PyTuple_SET_ITEM(args, 1, PyInt_FromLong(lock));
    PyTuple_SET_ITEM(args, 2, PyInt_FromLong(id));
    return pyclixon_call_rv_int(bp->handler, "lockdb", args, true);
}

static int
pyclixon_beh_exit(struct clixon_beh_plugin *p)
{
    struct plugin *bp = clixon_beh_plugin_get_cb_data(p);

    pyclixon_call_rv_int(bp->handler, "exit", NULL, true);
    Py_DECREF(bp->handler);
    return 0;
}

static int
pyclixon_beh_start(struct clixon_beh_plugin *p)
{
    struct plugin *bp = clixon_beh_plugin_get_cb_data(p);

    return pyclixon_call_rv_int(bp->handler, "start", NULL, true);
}

static int
pyclixon_beh_yang_patch(struct clixon_beh_plugin *p, yang_stmt *yang)
{
    struct plugin *bp = clixon_beh_plugin_get_cb_data(p);
    PyObject *args = PyTuple_New(1);
    struct yangobj *y;

    y = yangobj_new(yang);
    PyTuple_SET_ITEM(args, 0, SWIG_NewPointerObj(SWIG_as_voidptr(y),
						 SWIGTYPE_p_yangobj,
						 SWIG_POINTER_OWN));
    return pyclixon_call_rv_int(bp->handler, "yang_patch", args, true);
}

static int
pyclixon_xml_copy_one(cxobj *x0, cxobj *x1)
{
    int   retval = -1;
    char *s;

    if (x0 == NULL || x1 == NULL){
        clixon_err(OE_XML, EINVAL, "x0 or x1 is NULL");
        goto done;
    }
    if ((s = xml_name(x0))) /* malloced string */
        if ((xml_name_set(x1, s)) < 0)
            goto done;
    if ((s = xml_prefix(x0))) /* malloced string */
        if ((xml_prefix_set(x1, s)) < 0)
            goto done;
    switch (xml_type(x0)){
    case CX_ELMNT:
        xml_spec_set(x1, xml_spec(x0));
        break;
    case CX_BODY:
    case CX_ATTR:
        if ((s = xml_value(x0))){ /* malloced string */
            if (xml_value_set(x1, s) < 0)
                goto done;

        }
        break;
    default:
        break;
    }
    xml_flag_set(x1, xml_flag(x0, 0xFFFF));
    retval = 0;
 done:
    return retval;
}

static int
pyclixon_xml_copy(cxobj *x0, cxobj *x1)
{
    int    retval = -1;
    cxobj *x;
    cxobj *xcopy;

    if (pyclixon_xml_copy_one(x0, x1) <0)
        goto done;
    x = NULL;
    while ((x = xml_child_each(x0, x, -1)) != NULL) {
        if ((xcopy = xml_new(xml_name(x), x1, xml_type(x))) == NULL)
            goto done;
        if (pyclixon_xml_copy(x, xcopy) < 0) /* recursion */
            goto done;
    }
    retval = 0;
  done:
    return retval;
}

cxobj *
pyclixon_xml_dup(cxobj *x0)
{
    cxobj *x1;

    if ((x1 = xml_new("new", NULL, xml_type(x0))) == NULL)
        return NULL;
    if (pyclixon_xml_copy(x0, x1) < 0)
        return NULL;
    return x1;
}

/* Bit positions of the XML flags */
#define XML_FLAG_MARK_POS	0
#define XML_FLAG_TRANSIENT_POS	1
#define XML_FLAG_ADD_POS	2
#define XML_FLAG_DEL_POS	3
#define XML_FLAG_CHANGE_POS	4
#define XML_FLAG_NONE_POS	5
#define XML_FLAG_DEFAULT_POS	6
#define XML_FLAG_TOP_POS	7
#define XML_FLAG_BODYKEY_POS	8
#define XML_FLAG_ANYDATA_POS	9
#define XML_FLAG_CACHE_DIRTY_POS 10
static char *xml_flag2str_array[16] = {
    [XML_FLAG_MARK_POS] = "mark",
    [XML_FLAG_TRANSIENT_POS] = "transient",
    [XML_FLAG_ADD_POS] = "add",
    [XML_FLAG_DEL_POS] = "del",
    [XML_FLAG_CHANGE_POS] = "change",
    [XML_FLAG_NONE_POS] = "none",
    [XML_FLAG_DEFAULT_POS] = "default",
    [XML_FLAG_TOP_POS] = "top",
    [XML_FLAG_BODYKEY_POS] = "bodykey",
    [XML_FLAG_ANYDATA_POS] = "anydata",
    [XML_FLAG_CACHE_DIRTY_POS] = "cachedirty",
};
#define MAX_XML_ATTRSTR 100

static size_t xml_flags2str(char *str, size_t len, uint16_t flags)
{
    size_t pos = 0, left, i;

    if (flags == 0)
	return false;
    if (len > 0)
	str[len] = '\0';
    for (i = 0; i < 16 && flags; i++) {
	if (!xml_flag2str_array[i])
	    continue;
	if (!((1 << i) & flags))
	    continue;
	if (pos < len)
	    left = len - pos;
	else
	    left = 0;
	if (pos == 0)
	    pos += snprintf(str + pos, left, "%s", xml_flag2str_array[i]);
	else
	    pos += snprintf(str + pos, left, ",%s", xml_flag2str_array[i]);
	flags &= ~(1 << i);
    }
    return pos;
}

static int
pyclixon_xml_addattrs(cxobj *x, cxobj *xo)
{
    int rv = 0;
    cxobj *c, *co;
    char attrstr[MAX_XML_ATTRSTR];
    size_t attrstr_len;

    attrstr_len = xml_flags2str(attrstr, sizeof(attrstr), xml_flag(xo, 0xffff));
    if (attrstr_len > 0) {
	if (!xml_add_attr(x, "clixonflags", attrstr, NULL, NULL)) {
	    clixon_err(OE_XML, 0, "Unable to add clixonflags attr");
	    return -1;
	}
    }
    c = NULL;
    co = NULL;
    while ((c = xml_child_each(x, c, CX_ELMNT)) != NULL) {
	co = xml_child_each(xo, co, CX_ELMNT);
	rv = pyclixon_xml_addattrs(c, co);
	if (rv < 0)
	    break;
    }
    return rv;
}

static PyObject *
clixon_beh_xml2str(cxobj *oxml)
{
    cxobj *xml = NULL;
    cbuf *cb = NULL;
    PyObject *rv = NULL;

    xml = xml_dup(oxml);
    if (!xml) {
	clixon_err(OE_XML, 0, "Unable to duplicate xml");
	goto out_err;
    }
    cb = cbuf_new();
    if (!cb) {
	clixon_err(OE_XML, 0, "Unable to allocate cbuf");
	goto out_err;
    }

    if (pyclixon_xml_addattrs(xml, oxml) < 0)
	goto out_err;
    if (clixon_xml2cbuf(cb, xml, 0, 0, NULL, -1,  0) < 0)
	goto out_err;
    rv = PyUnicode_FromString(cbuf_get(cb));
 out_err:
    if (xml)
	xml_free(xml);
    if (cb)
	cbuf_free(cb);
    return rv;
}

struct transaction {
    PyObject *myself;
    PyObject *userdata;
    cxobj *orig_xml;
    cxobj *new_xml;
    struct xmlobj *orig_xmlobj;
    struct xmlobj *new_xmlobj;
    PyObject *orig_str;
    PyObject *new_str;
};

static int
pyclixon_call_trans(struct clixon_beh_plugin *p, struct clixon_beh_trans *t,
		    const char *method)
{
    struct plugin *bp = clixon_beh_plugin_get_cb_data(p);
    struct transaction *data = clixon_beh_trans_get_data(t);
    PyObject *args;
    int retval = -1;

    if (!data) {
	data = calloc(1, sizeof(*data));
	if (!data) {
	    clixon_err(OE_XML, 0, "Could not allocate transaction data");
	    goto out_err;
	}
	data->myself = SWIG_NewPointerObj(SWIG_as_voidptr(data),
					  SWIGTYPE_p_transaction,
					  SWIG_POINTER_OWN);
	data->userdata = Py_NewRef(Py_None);
	data->orig_xml = clixon_beh_trans_orig_xml(t);
	data->new_xml = clixon_beh_trans_new_xml(t);
	clixon_beh_trans_set_data(t, data);
    }

    args = PyTuple_New(1);
    Py_INCREF(data->myself);
    PyTuple_SET_ITEM(args, 0, data->myself);
    retval = pyclixon_call_rv_int(bp->handler, method, args, true);

 out_err:
    return retval;
}

static int
pyclixon_beh_begin(struct clixon_beh_plugin *p, struct clixon_beh_trans *t)
{
    return pyclixon_call_trans(p, t, "begin");
}

static int
pyclixon_beh_validate(struct clixon_beh_plugin *p, struct clixon_beh_trans *t)
{
    return pyclixon_call_trans(p, t, "validate");
}

static int
pyclixon_beh_complete(struct clixon_beh_plugin *p, struct clixon_beh_trans *t)
{
    return pyclixon_call_trans(p, t, "complete");
}

static int
pyclixon_beh_commit(struct clixon_beh_plugin *p, struct clixon_beh_trans *t)
{
    return pyclixon_call_trans(p, t, "commit");
}

static int
pyclixon_beh_commit_done(struct clixon_beh_plugin *p,
			 struct clixon_beh_trans *t)
{
    return pyclixon_call_trans(p, t, "commit_done");
}

static int
pyclixon_beh_revert(struct clixon_beh_plugin *p, struct clixon_beh_trans *t)
{
    return pyclixon_call_trans(p, t, "revert");
}

static int
pyclixon_beh_end(struct clixon_beh_plugin *p, struct clixon_beh_trans *t)
{
    struct transaction *data = clixon_beh_trans_get_data(t);
    int rv = pyclixon_call_trans(p, t, "end");

    Py_DECREF(data->myself);
    return rv;
}

static int
pyclixon_beh_abort(struct clixon_beh_plugin *p, struct clixon_beh_trans *t)
{
    struct transaction *data = clixon_beh_trans_get_data(t);
    int rv = pyclixon_call_trans(p, t, "abort");

    Py_DECREF(data->myself);
    return rv;
}

static int
pyclixon_beh_datastore_upgrade(struct clixon_beh_plugin *p,
			       const char *db, cxobj *xt,
			       modstate_diff_t *msd)
{
    /* FIXME */
    return 0;
}


struct clixon_beh_api pyclixon_beh_api_strxml = {
    .pre_daemon = pyclixon_beh_pre_daemon,
    .daemon = pyclixon_beh_daemon,
    .reset = pyclixon_beh_reset,
    .statedata = pyclixon_beh_statedata,
    .system_only = pyclixon_beh_system_only,
    .lockdb = pyclixon_beh_lockdb,
    .exit = pyclixon_beh_exit,
    .start = pyclixon_beh_start,
    .yang_patch = pyclixon_beh_yang_patch,
    .begin = pyclixon_beh_begin,
    .validate = pyclixon_beh_validate,
    .complete = pyclixon_beh_complete,
    .commit = pyclixon_beh_commit,
    .commit_done = pyclixon_beh_commit_done,
    .revert = pyclixon_beh_revert,
    .end = pyclixon_beh_end,
    .abort = pyclixon_beh_abort,
    .datastore_upgrade = pyclixon_beh_datastore_upgrade,
};

struct pyclixon_rpc_info {
    PyObject *handler;
};

static int
pyclixon_rpc_callback(clixon_handle h,
		      cxobj        *xe,
		      cbuf         *cbret,
		      void         *xarg,
		      void         *regarg)
{
    struct pyclixon_rpc_info *info = regarg;
    PyObject *arg, *args = PyTuple_New(2);
    PyObject *o = NULL;
    const char *xmlstr;
    struct xmlobj *xml;

    xml = xmlobj_new(NULL, xe);
    if (!xml) {
	clixon_err(OE_PLUGIN, 0, "pyclixon_beh:rpc: Could not create xmlobj.");
	return -1;
    }
    arg = SWIG_NewPointerObj(SWIG_as_voidptr(xml),
			     SWIGTYPE_p_xmlobj,
			     0);
    PyTuple_SET_ITEM(args, 0, arg);
    arg = PyUnicode_FromString(xarg);
    PyTuple_SET_ITEM(args, 1, arg);
    if (pyclixon_call_rv(info->handler, "rpc", args, false, &o) < 0)
	return -1;
    if (!o)
	return -1;
    if (!PyTuple_Check(o) || PyTuple_GET_SIZE(o) != 2 ||
		!PyLong_Check(PyTuple_GET_ITEM(o, 0)) ||
		!PyUnicode_Check(PyTuple_GET_ITEM(o, 1))) {
	PyObject *t = PyObject_GetAttrString(info->handler, "__class__");
	PyObject *c = PyObject_GetAttrString(t, "__name__");
	const char *classt = PyUnicode_AsUTF8(c);

	clixon_err(OE_PLUGIN, 0, "pyclixon_beh:rpc: method rpc of "
		   "class %s didn't return a tuple of size 2, first element "
		   "an int and second a string", classt);
	Py_DECREF(o);
	return -1;
    }
    if (PyLong_AsUnsignedLong(PyTuple_GET_ITEM(o, 0)) < 0) {
	Py_DECREF(o);
	return -1;
    }
    xmlstr = PyUnicode_AsUTF8AndSize(PyTuple_GET_ITEM(o, 1), NULL);
    if (!xmlstr) {
	clixon_err(OE_PLUGIN, 0, "pyclixon_beh:rpc: Could not convert string "
		   "return of rpc callback to a string.");
	Py_DECREF(o);
	return -1;
    }
    if (cbuf_append_str(cbret, (char *) xmlstr) < 0) {
	clixon_err(OE_PLUGIN, 0, "pyclixon_beh:rpc: Could not append return "
		   "string.");
	Py_DECREF(o);
	return -1;
    }
    Py_DECREF(o);
    return 0;
}

struct pyclixon_action_info {
    PyObject *handler;
};

static int
pyclixon_action_callback(clixon_handle h,
			 cxobj        *xe,
			 cbuf         *cbret,
			 void         *xarg,
			 void         *regarg)
{
    struct pyclixon_action_info *info = regarg;
    PyObject *arg, *args = PyTuple_New(2);
    PyObject *o = NULL;
    const char *xmlstr;
    struct xmlobj *xml;

    xml = xmlobj_new(NULL, xe);
    if (!xml) {
	clixon_err(OE_PLUGIN, 0,
		   "pyclixon_beh:action: Could not create xmlobj.");
	return -1;
    }
    arg = SWIG_NewPointerObj(SWIG_as_voidptr(xml),
			     SWIGTYPE_p_xmlobj,
			     0);
    PyTuple_SET_ITEM(args, 0, arg);
    arg = PyUnicode_FromString(xarg);
    PyTuple_SET_ITEM(args, 1, arg);
    if (pyclixon_call_rv(info->handler, "action", args, false, &o) < 0)
	return -1;
    if (!o)
	return -1;
    if (!PyTuple_Check(o) || PyTuple_GET_SIZE(o) != 2 ||
		!PyLong_Check(PyTuple_GET_ITEM(o, 0)) ||
		!PyUnicode_Check(PyTuple_GET_ITEM(o, 1))) {
	PyObject *t = PyObject_GetAttrString(info->handler, "__class__");
	PyObject *c = PyObject_GetAttrString(t, "__name__");
	const char *classt = PyUnicode_AsUTF8(c);

	clixon_err(OE_PLUGIN, 0, "pyclixon_beh:action: method action of "
		   "class %s didn't return a tuple of size 2, first element "
		   "an int and second a string", classt);
	Py_DECREF(o);
	return -1;
    }
    if (PyLong_AsUnsignedLong(PyTuple_GET_ITEM(o, 0)) < 0) {
	Py_DECREF(o);
	return -1;
    }
    xmlstr = PyUnicode_AsUTF8AndSize(PyTuple_GET_ITEM(o, 1), NULL);
    if (!xmlstr) {
	clixon_err(OE_PLUGIN, 0,
		   "pyclixon_beh:action: Could not convert string "
		   "return of action callback to a string.");
	Py_DECREF(o);
	return -1;
    }
    if (cbuf_append_str(cbret, (char *) xmlstr) < 0) {
	clixon_err(OE_PLUGIN, 0, "pyclixon_beh:action: Could not append return "
		   "string.");
	Py_DECREF(o);
	return -1;
    }
    Py_DECREF(o);
    return 0;
}

void clixon_errt(int oe, int ev, char *str)
{
    clixon_err(oe, ev, "%s", str);
}

void clixon_logt(int logtype, char *str)
{
    struct clixon_beh *beh = clixon_beh_get_global_beh();
    clixon_beh_log(beh, logtype, "%s", str);
}

void plugin_rpc_errt(char *ns, char *type, char *tag, char *info,
		     char *severity, char *message)
{
    struct clixon_beh *beh = clixon_beh_get_global_beh();
    struct clixon_handle *h = clixon_beh_get_handle(beh);

    clixon_plugin_rpc_err(h, ns, type, tag, info, severity, "%s", message);
}
%}

%constant int LOG_TYPE_LOG = LOG_TYPE_LOG;
%constant int LOG_TYPE_ERR = LOG_TYPE_ERR;
%constant int LOG_TYPE_DEBUG = LOG_TYPE_DEBUG;

%nodefaultctor plugin;
struct plugin { };

%newobject add_plugin_strxml;
%inline %{
struct plugin *add_plugin(const char *name,
			  const char *namespace,
			  PyObject *handler)
{
    int rv;
    struct plugin *bp;
    struct clixon_beh *beh = clixon_beh_get_global_beh();

    if (name == NULL)
	return NULL;
    if (handler == NULL)
	return NULL;

    bp = malloc(sizeof(*bp));
    if (!bp) {
	PyErr_Format(PyExc_RuntimeError,
		     "Out of memory allocating BEH info");
	return NULL;
    }

    bp->handler = handler;

    Py_INCREF(handler);
    rv = clixon_beh_add_plugin(beh, name, namespace,
			       &pyclixon_beh_api_strxml, bp, &bp->p);
    if (rv < 0) {
	Py_DECREF(handler);
	free(bp);
	return NULL;
    }

    return bp;
}
%}

%extend plugin {
    ~plugin()
    {
	clixon_beh_del_plugin(self->p);
    }

    void log(int logtype, char *str)
    {
	clixon_beh_log_plugin(self->p, logtype, "%s", str);
    }
}

%rename(add_stream) add_streamt;
%rename(stream_notify) stream_notifyt;
%inline %{
void set_err_handler(PyObject *handler)
{
    if (err_handler) {
	Py_DECREF(err_handler);
    }
    err_handler = handler;
}

/* FIXME - There is no way to unregister this.  Maybe it doesn't matter. */
void add_rpc_callback(const char *name,
		      const char *namespace,
		      PyObject *handler)
{
    int rv;
    struct pyclixon_rpc_info *info;
    struct clixon_beh *beh = clixon_beh_get_global_beh();
    struct clixon_handle *h = clixon_beh_get_handle(beh);

    if (name == NULL) {
	PyErr_Format(PyExc_RuntimeError,
		     "No name given for add_rpc_callback");
	return;
    }
    if (namespace == NULL) {
	PyErr_Format(PyExc_RuntimeError,
		     "No namespace given for add_rpc_callback");
	return;
    }
    if (handler == NULL) {
	PyErr_Format(PyExc_RuntimeError,
		     "No handler given for add_rpc_callback");
	return;
    }

    info = malloc(sizeof(*info));
    if (!info) {
	PyErr_Format(PyExc_RuntimeError,
		     "Out of memory allocating RPC info");
	return;
    }
    info->handler = handler;
    Py_INCREF(handler);
    rv = rpc_callback_register(h, pyclixon_rpc_callback, info, namespace,
			       name);
    if (rv == -1) {
	PyErr_Format(PyExc_RuntimeError,
		     "Error registering RPC callback");
	Py_DECREF(handler);
	free(info);
    }
}

/* FIXME - There is no way to unregister this.  Maybe it doesn't matter. */
void add_action_callback(char *yang_path,
			 PyObject *handler)
{
    int rv;
    struct pyclixon_action_info *info;
    struct clixon_beh *beh = clixon_beh_get_global_beh();
    struct clixon_handle *h = clixon_beh_get_handle(beh);
    yang_stmt *yspec;
    yang_stmt *ya = NULL;

    if (ya == NULL) {
	PyErr_Format(PyExc_RuntimeError,
		     "No yang action given for add_action_callback");
	return;
    }
    if (handler == NULL) {
	PyErr_Format(PyExc_RuntimeError,
		     "No handler given for add_action_callback");
	return;
    }

    yspec = clicon_dbspec_yang(h);
    if (yspec == NULL) {
	PyErr_Format(PyExc_RuntimeError,
		     "No yang dbspec available");
	return;
    }
    if (yang_abs_schema_nodeid(yspec, yang_path, &ya) < 0) {
	PyErr_Format(PyExc_RuntimeError,
		     "Invalid yang path: %s", yang_path);
	return;
    }
    if (!ya) {
	PyErr_Format(PyExc_RuntimeError,
		     "Empty yang path: %s", yang_path);
	return;
    }

    info = malloc(sizeof(*info));
    if (!info) {
	PyErr_Format(PyExc_RuntimeError,
		     "Out of memory allocating action info");
	return;
    }
    info->handler = handler;
    Py_INCREF(handler);
    rv = action_callback_register(h, ya, pyclixon_action_callback, info);
    if (rv == -1) {
	PyErr_Format(PyExc_RuntimeError,
		     "Error registering action callback");
	Py_DECREF(handler);
	free(info);
    }
}

void
add_streamt(char *name, char *description, bool replay_enabled)
{
    struct clixon_beh *beh = clixon_beh_get_global_beh();
    struct clixon_handle *h = clixon_beh_get_handle(beh);
    struct timeval retention = {0,0};

    if (clicon_option_exists(h, "CLICON_STREAM_RETENTION"))
	retention.tv_sec = clicon_option_int(h, "CLICON_STREAM_RETENTION");
    if (stream_add(h, name, description, replay_enabled, &retention) < 0) {
	PyErr_Format(PyExc_RuntimeError,
		     "Error adding stream for %s", name);
	return;
    }
    if (clicon_option_exists(h, "CLICON_STREAM_PUB") &&
		stream_publish(h, name) < 0) {
	PyErr_Format(PyExc_RuntimeError,
		     "Error publishing stream for %s", name);
	return;
    }
}

void
stream_notifyt(char *name, char *xmlstr)
{
    struct clixon_beh *beh = clixon_beh_get_global_beh();
    struct clixon_handle *h = clixon_beh_get_handle(beh);

    if (stream_notify(h, name, "%s", xmlstr) < 0)
	PyErr_Format(PyExc_RuntimeError,
		     "Error notifying stream for %s", name);
}

char *
username_get(void)
{
    struct clixon_beh *beh = clixon_beh_get_global_beh();
    struct clixon_handle *h = clixon_beh_get_handle(beh);

    return clicon_username_get(h);
}

/*
 * FIXME - there should probably be a clicon_option_feature() added to
 * clixon for this to use.
 */
bool
is_feature_set(char *module, char *name)
{
    struct clixon_beh *beh = clixon_beh_get_global_beh();
    struct clixon_handle *h = clixon_beh_get_handle(beh);
    cxobj *x = NULL;
    unsigned int module_len;

    if (!module || !name) {
	PyErr_Format(PyExc_RuntimeError,
		     "is_feature_set called with NULL value");
	return false;
    }
    module_len = strlen(module);

    x = NULL;
    while ((x = xml_child_each(clicon_conf_xml(h), x, CX_ELMNT)) != NULL) {
	char *v, *v2;
	unsigned int len;

        if (strcmp(xml_name(x), "CLICON_FEATURE") != 0)
            continue;
	v = xml_body(x);
	if (!v)
	    continue;
	v2 = strchr(v, ':');
	if (!v2)
	    continue;
	len = v2 - v;
	v2++;
	if (module_len == len && strncmp(v, module, len) == 0 &&
		strcmp(v2, name) == 0)
	    return true;
    }
    return false;
}

%}

%constant int XMLOBJ_TYPE_ELEMENT = CX_ELMNT;
%constant int XMLOBJ_TYPE_ATTR = CX_ATTR;
%constant int XMLOBJ_TYPE_BODY = CX_BODY;

%constant int XMLOBJ_FLAG_MARK = XML_FLAG_MARK;
%constant int XMLOBJ_FLAG_TRANSIENT = XML_FLAG_TRANSIENT;
%constant int XMLOBJ_FLAG_ADD = XML_FLAG_ADD;
%constant int XMLOBJ_FLAG_DEL = XML_FLAG_DEL;
%constant int XMLOBJ_FLAG_CHANGE = XML_FLAG_CHANGE;
%constant int XMLOBJ_FLAG_NONE = XML_FLAG_NONE;
%constant int XMLOBJ_FLAG_DEFAULT = XML_FLAG_DEFAULT;
%constant int XMLOBJ_FLAG_TOP = XML_FLAG_TOP;
%constant int XMLOBJ_FLAG_BODYKEY = XML_FLAG_BODYKEY;
%constant int XMLOBJ_FLAG_ANYDATA = XML_FLAG_ANYDATA;
%constant int XMLOBJ_FLAG_CACHE_DIRTY = XML_FLAG_CACHE_DIRTY;
%constant int XMLOBJ_FLAG_FULL_MASK = 0xffff;

%nodefaultctor xmlobj;
struct xmlobj { };

%extend xmlobj {
    ~xmlobj()
    {
	free_xmlobj(self);
    }

    PyObject *to_str()
    {
	return clixon_beh_xml2str(self->xml);
    }

    char *get_name()
    {
	return xml_name(self->xml);
    }

    char *get_prefix()
    {
	return xml_prefix(self->xml);
    }

    struct xmlobj *get_parent()
    {
	return xmlobj_new(self->orig_ref, xml_parent(self->xml));
    }

    int get_flags(int mask)
    {
	return xml_flag(self->xml, mask);
    }

    /* Returns a list of strings for the flags that are set. */
    %newobject get_flags_strs;
    char *get_flags_strs()
    {
	char attrstr[MAX_XML_ATTRSTR];
	size_t attrstr_len;

	attrstr_len = xml_flags2str(attrstr, sizeof(attrstr),
				    xml_flag(self->xml, 0xffff));
	if (attrstr_len == 0)
	    return NULL;
	return strdup(attrstr);
    }

    char *get_value()
    {
	return xml_value(self->xml);
    }

    char *get_type_str()
    {
	return xml_type2str(xml_type(self->xml));
    }

    int get_type()
    {
	return xml_type(self->xml);
    }

    int nr_children()
    {
	return xml_child_nr(self->xml);
    }

    int nr_children_type(int type)
    {
	return xml_child_nr_type(self->xml, type);
    }

    struct xmlobj *child_i(int i)
    {
	return xmlobj_new(self->orig_ref, xml_child_i(self->xml, i));
    }

    struct xmlobj *child_i_type(int i, int type)
    {
	return xmlobj_new(self->orig_ref, xml_child_i_type(self->xml, i, type));
    }

    struct xmlobj *find(char *name)
    {
	return xmlobj_new(self->orig_ref, xml_find(self->xml, name));
    }

    struct xmlobj *find_type(char *prefix, char *name, int type)
    {
	return xmlobj_new(self->orig_ref,
			  xml_find_type(self->xml, prefix, name, type));
    }

    char *find_type_value(char *prefix, char *name, int type)
    {
	return xml_find_type_value(self->xml, prefix, name, type);
    }

    char *get_body()
    {
	return xml_body(self->xml);
    }

    char *get_attr_value(char *prefix, char *name)
    {
	return xml_find_type_value(self->xml, prefix, name, CX_ATTR);
    }
}

%nodefaultctor yangobj;
struct yangobj { };

%extend yangobj {
    ~yangobj()
    {
	free_yangobj(self);
    }

    PyObject *to_str(int marginal = 0, bool pretty = false)
    {
	cbuf *cb = NULL;
	PyObject *rv = NULL;

	cb = cbuf_new();
	if (!cb) {
	    clixon_err(OE_XML, 0, "Unable to allocate cbuf");
	    goto out_err;
	}
	if (yang_print_cbuf(cb, self->yang, marginal, pretty) < 0) {
	    clixon_err(OE_XML, 0, "Unable to convert yang to cbuf");
	    goto out_err;
	}

	rv = PyUnicode_FromString(cbuf_get(cb));
    out_err:
	if (cb)
	    cbuf_free(cb);
	return rv;
    }

    int nr_children()
    {
	return yang_len_get(self->yang);
    }

    struct yangobj *child_i(int i)
    {
	return yangobj_new(yang_child_i(self->yang, i));
    }

    char *find_mynamespace()
    {
	return yang_find_mynamespace(self->yang);
    }

    char *find_myprefix()
    {
	return yang_find_myprefix(self->yang);
    }

    char *keyword_get()
    {
	return yang_key2str(yang_keyword_get(self->yang));
    }

    char *argument_get()
    {
	return yang_argument_get(self->yang);
    }
}

struct yangobj *get_yang_base();
%nodefaultctor plugin;
struct transaction { };

%extend transaction {
    ~transaction()
    {
	if (self->userdata)
	    Py_DECREF(self->userdata);
	if (self->orig_str)
	    Py_DECREF(self->orig_str);
	if (self->new_str)
	    Py_DECREF(self->new_str);
	if (self->orig_xmlobj)
	    free_xmlobj(self->orig_xmlobj);
	if (self->new_xmlobj)
	    free_xmlobj(self->new_xmlobj);
	free(self);
    }

    void set_userdata(PyObject *data)
    {
	Py_DECREF(self->userdata);
	self->userdata = Py_NewRef(data);
    }

    PyObject *get_userdata()
    {
	return Py_NewRef(self->userdata);
    }

    PyObject *orig_str()
    {
	if (!self->orig_str) {
	    if (!self->orig_xml)
		Py_RETURN_NONE;
	    self->orig_str = clixon_beh_xml2str(self->orig_xml);
	    if (!self->orig_str)
		self->orig_str = Py_NewRef(Py_None);
	}
	return Py_NewRef(self->orig_str);
    }

    PyObject *new_str()
    {
	if (!self->new_str) {
	    if (!self->new_xml)
		Py_RETURN_NONE;
	    self->new_str = clixon_beh_xml2str(self->new_xml);
	    if (!self->new_str)
		self->new_str = Py_NewRef(Py_None);
	}
	return Py_NewRef(self->new_str);
    }

    struct xmlobj *orig_xml()
    {
	if (!self->orig_xmlobj)
	    self->orig_xmlobj = xmlobj_new(NULL, self->orig_xml);
	return xmlobj_new(self->orig_xmlobj, self->orig_xml);
    }

    struct xmlobj *new_xml()
    {
	if (!self->new_xmlobj)
	    self->new_xmlobj = xmlobj_new(NULL, self->new_xml);
	return xmlobj_new(self->new_xmlobj, self->new_xml);
    }
}

/* Clixon privilege handling. */
int geteuid();
int restore_priv();
int drop_priv_temp(int euid);

%constant int OE_DB = OE_DB;
%constant int OE_DAEMON = OE_DAEMON;
%constant int OE_EVENTS = OE_EVENTS;
%constant int OE_CFG = OE_CFG;
%constant int OE_NETCONF = OE_NETCONF;
%constant int OE_PROTO = OE_PROTO;
%constant int OE_REGEX = OE_REGEX;
%constant int OE_UNIX = OE_UNIX;
%constant int OE_SYSLOG = OE_SYSLOG;
%constant int OE_ROUTING = OE_ROUTING;
%constant int OE_XML = OE_XML;
%constant int OE_JSON = OE_JSON;
%constant int OE_RESTCONF = OE_RESTCONF;
%constant int OE_PLUGIN = OE_PLUGIN;
%constant int OE_YANG  = OE_YANG;
%constant int OE_FATAL = OE_FATAL;
%constant int OE_UNDEF = OE_UNDEF;
%constant int OE_SSL = OE_SSL;
%constant int OE_SNMP  = OE_SNMP;
%constant int OE_NGHTTP2 = OE_NGHTTP2;

%rename(err) clixon_errt;
void clixon_errt(int oe, int ev, char *str);

%rename(log) clixon_logt;
void clixon_logt(int logtype, char *str);

%rename(rpc_err) plugin_rpc_errt;
void plugin_rpc_errt(char *ns, char *type, char *tag, char *info,
		     char *severity, char *message);

%constant char *NETCONF_BASE_NAMESPACE = "urn:ietf:params:xml:ns:netconf:base:1.0";
