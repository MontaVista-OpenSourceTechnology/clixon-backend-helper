

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

	    fprintf(stderr, "clixon_beh:callback: "
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
    /* FIXME */
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
		    const char *method)
{
    struct plugin *bp = clixon_beh_plugin_get_cb_data(p);
    PyObject *args = PyTuple_New(2), *orig_obj, *new_obj;
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

    PyTuple_SET_ITEM(args, 0, orig_obj);
    PyTuple_SET_ITEM(args, 1, new_obj);
    retval = pyclixon_call_rv_int(bp->handler, method, args, true);

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
    return pyclixon_call_trans(p, t, "end");
}

static int
pyclixon_beh_abort(struct clixon_beh_plugin *p, struct clixon_beh_trans *t)
{
    return pyclixon_call_trans(p, t, "abort");
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

%}

%nodefaultctor beh;
struct clixon_beh;
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
