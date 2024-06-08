

%module clixon_beh

%{

#include <stdbool.h>
#include <clixon_beh.h>
#include <cligen/cligen_buf.h>
#include <clixon/clixon_xml_io.h>

struct plugin {
    struct clixon_beh_plugin *p;
    PyObject *handler;
};

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
	    /* FIXME - convert to clixon_err() */
	    PyErr_Print();
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
pyclixon_beh_statedata(struct clixon_beh_plugin *p,
		       cvec *nsc, char *xpath, cxobj *xtop)
{
    struct plugin *bp = clixon_beh_plugin_get_cb_data(p);
    PyObject *args = PyTuple_New(2);
    PyObject *arg1 = PyTuple_New(cvec_len(nsc));
    PyObject *o = NULL;
    unsigned int i;
    const char *xmlstr;

    for (i = 0; i < cvec_len(nsc); i++)
	PyTuple_SET_ITEM(arg1, i, PyUnicode_FromString(cvec_i_str(nsc, i)));
    PyTuple_SET_ITEM(args, 0, arg1);
    PyTuple_SET_ITEM(args, 1, PyUnicode_FromString(xpath));
    if (pyclixon_call_rv(bp->handler, "statedata", args, true, &o) < 0)
	return -1;
    if (!o)
	return -1;
    if (!PyTuple_Check(o) || PyTuple_GET_SIZE(o) != 2 ||
		!PyLong_Check(PyTuple_GET_ITEM(o, 0)) ||
		!PyUnicode_Check(PyTuple_GET_ITEM(o, 1))) {
	PyObject *t = PyObject_GetAttrString(bp->handler, "__class__");
	PyObject *c = PyObject_GetAttrString(t, "__name__");
	const char *classt = PyUnicode_AsUTF8(c);

	clixon_err(OE_PLUGIN, 0, "pyclixon_beh:callback: method statedata of "
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
	clixon_err(OE_PLUGIN, 0, "pyclixon_beh:callback: Could convert string "
		   "return of method statedata to a string.");
	Py_DECREF(o);
	return -1;
    }
    Py_DECREF(o);
    if (clixon_xml_parse_string(xmlstr, YB_NONE, NULL, &xtop, NULL) < 0) {
	clixon_err(OE_PLUGIN, 0, "pyclixon_beh:callback: Could not parse "
		   "returned XML string.");
	return -1;
    }

    return 0;
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

static int
pyclixon_xml_addattrs(cxobj *x, cxobj *xo)
{
    uint16_t flags = xml_flag(xo,
			      XML_FLAG_ADD | XML_FLAG_DEL | XML_FLAG_CHANGE);
    int rv = 0;
    cxobj *c, *co;

    if (flags) {
	char attrstr[50] = "";

	if (flags & XML_FLAG_ADD)
	    strcat(attrstr, "add");
	if (flags & XML_FLAG_DEL) {
	    if (attrstr[0])
		strcat(attrstr, ",");
	    strcat(attrstr, "del");
	}
	if (flags & XML_FLAG_CHANGE) {
	    if (attrstr[0])
		strcat(attrstr, ",");
	    strcat(attrstr, "chd");
	}
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

static int
pyclixon_call_trans(struct clixon_beh_plugin *p, struct clixon_beh_trans *t,
		    const char *method, bool begin)
{
    struct plugin *bp = clixon_beh_plugin_get_cb_data(p);
    PyObject *orig_obj, *new_obj;
    cxobj *oxml = clixon_beh_trans_orig_xml(t);
    cxobj *orig_xml = NULL;
    cxobj *nxml = clixon_beh_trans_new_xml(t);
    cxobj *new_xml = NULL;
    cbuf *orig_cb = NULL, *new_cb = NULL;
    int retval = -1;

    if (oxml) {
	orig_xml = xml_dup(oxml);
	orig_cb = cbuf_new();
    }
    if (nxml) {
	new_xml = xml_dup(nxml);
	new_cb = cbuf_new();
    }

    if (oxml && !orig_xml) {
	clixon_err(OE_XML, 0, "Unable to duplicate orig_xml");
	goto out_err;
    }

    if (nxml && !new_xml) {
	clixon_err(OE_XML, 0, "Unable to duplicate new_xml");
	goto out_err;
    }

    if ((oxml && !orig_cb) || (nxml && !new_cb)) {
	clixon_err(OE_XML, 0, "Unable to allocate cbuf");
	goto out_err;
    }

    /*
     * We pull the add/delete/changed flags out of the old XML and set
     * the attributes in the new XML tree.
     */
    if (orig_xml) {
	if (pyclixon_xml_addattrs(orig_xml, oxml) < 0)
	    goto out_err;
	if (clixon_xml2cbuf(orig_cb, orig_xml, 0, 0, NULL, -1,  0) < 0)
	    goto out_err;
	orig_obj = PyUnicode_FromString(cbuf_get(orig_cb));
    } else {
	orig_obj = Py_None;
	Py_INCREF(Py_None);
    }
    if (new_xml) {
	if (pyclixon_xml_addattrs(new_xml, nxml) < 0)
	    goto out_err;
	if (clixon_xml2cbuf(new_cb, new_xml, 0, 0, NULL, -1,  0) < 0)
	    goto out_err;
	new_obj = PyUnicode_FromString(cbuf_get(new_cb));
    } else {
	new_obj = Py_None;
	Py_INCREF(Py_None);
    }

    if (!begin) {
	PyObject *args = PyTuple_New(3);
	PyObject *data = clixon_beh_trans_get_data(t);

	if (!data) {
	    data = Py_None;
	    Py_INCREF(data);
	}
	PyTuple_SET_ITEM(args, 0, data);
	PyTuple_SET_ITEM(args, 1, orig_obj);
	PyTuple_SET_ITEM(args, 2, new_obj);
	retval = pyclixon_call_rv_int(bp->handler, method, args, true);
    } else {
	PyObject *args = PyTuple_New(2);
	PyObject *o = NULL, *data;

	PyTuple_SET_ITEM(args, 0, orig_obj);
	PyTuple_SET_ITEM(args, 1, new_obj);
	retval = pyclixon_call_rv(bp->handler, method, args, true, &o);
	if (retval < 0)
	    goto out_err;
	if (!o) {
	    /* No begin method. */
	    retval = 0;
	    goto out_err;
	}
	if (!PyTuple_Check(o) || PyTuple_GET_SIZE(o) != 2 ||
		!PyLong_Check(PyTuple_GET_ITEM(o, 0))) {
	    PyObject *t = PyObject_GetAttrString(bp->handler, "__class__");
	    PyObject *c = PyObject_GetAttrString(t, "__name__");
	    const char *classt = PyUnicode_AsUTF8(c);

	    clixon_err(OE_PLUGIN, 0, "pyclixon_beh:callback: method begin of "
		       "class %s didn't return a tuple of size 2, first "
		       "element as an int", classt);
	    Py_DECREF(o);
	    goto out_err;
	}
	if (PyLong_AsUnsignedLong(PyTuple_GET_ITEM(o, 0)) < 0) {
	    Py_DECREF(o);
	    goto out_err;
	}
	data = PyTuple_GET_ITEM(o, 1);
	Py_INCREF(data);
	Py_DECREF(o);
	clixon_beh_trans_set_data(t, data);
    }

 out_err:
    if (orig_cb)
	cbuf_free(orig_cb);
    if (new_cb)
	cbuf_free(new_cb);
    if (orig_xml)
	xml_free(orig_xml);
    if (new_xml)
	xml_free(new_xml);
    return retval;
}

static int
pyclixon_beh_begin(struct clixon_beh_plugin *p, struct clixon_beh_trans *t)
{
    return pyclixon_call_trans(p, t, "begin", true);
}

static int
pyclixon_beh_validate(struct clixon_beh_plugin *p, struct clixon_beh_trans *t)
{
    return pyclixon_call_trans(p, t, "validate", false);
}

static int
pyclixon_beh_complete(struct clixon_beh_plugin *p, struct clixon_beh_trans *t)
{
    return pyclixon_call_trans(p, t, "complete", false);
}

static int
pyclixon_beh_commit(struct clixon_beh_plugin *p, struct clixon_beh_trans *t)
{
    return pyclixon_call_trans(p, t, "commit", false);
}

static int
pyclixon_beh_commit_done(struct clixon_beh_plugin *p,
			 struct clixon_beh_trans *t)
{
    return pyclixon_call_trans(p, t, "commit_done", false);
}

static int
pyclixon_beh_revert(struct clixon_beh_plugin *p, struct clixon_beh_trans *t)
{
    return pyclixon_call_trans(p, t, "revert", false);
}

static int
pyclixon_beh_end(struct clixon_beh_plugin *p, struct clixon_beh_trans *t)
{
    PyObject *data = clixon_beh_trans_get_data(t);
    int rv = pyclixon_call_trans(p, t, "end", false);
    if (data)
	Py_DECREF(data);
    return rv;
}

static int
pyclixon_beh_abort(struct clixon_beh_plugin *p, struct clixon_beh_trans *t)
{
    PyObject *data = clixon_beh_trans_get_data(t);
    int rv = pyclixon_call_trans(p, t, "abort", false);
    if (data)
	Py_DECREF(data);
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
    .lockdb = pyclixon_beh_lockdb,
    .exit = pyclixon_beh_exit,
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

void clixon_errt(int oe, int ev, char *str)
{
    clixon_err(oe, ev, "%s", str);
}
%}

%nodefaultctor plugin;
struct plugin { };

%newobject add_plugin_strxml;
%inline %{
struct plugin *add_plugin_strxml(const char *name,
				 const char *namespace,
				 const char *priv_program,
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
    bp->handler = handler;

    Py_INCREF(handler);
    rv = clixon_beh_add_plugin(beh, name, namespace, priv_program,
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
}

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
%constant int OE_YANG  = OE_YANG ;
%constant int OE_FATAL = OE_FATAL;
%constant int OE_UNDEF = OE_UNDEF;
%constant int OE_SSL = OE_SSL;
%constant int OE_SNMP  = OE_SNMP ;
%constant int OE_NGHTTP2 = OE_NGHTTP2;

%rename(clixon_err) clixon_errt;
void clixon_errt(int oe, int ev, char *str);
