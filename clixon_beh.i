/*
 *  clixon-be-help - A clixon backin plugin helper
 *  Copyright (C) 2024  Montavista Software, LLC <source@mvista.com>
 *
 *  SPDX-License-Identifier: LGPL-2.1-only
 */

%module clixon_beh

%{

#include <stdbool.h>
#include <clixon_beh.h>
#include <cligen/cligen_buf.h>
#include <clixon/clixon_xml_io.h>

struct xmlobj {
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
	    free(x->orig_ref);
    }
    free(x);
}

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

void clixon_logt(int logtype, char *str)
{
    struct clixon_beh *beh = clixon_beh_get_global_beh();
    clixon_beh_log(beh, logtype, "%s", str);
}
%}

%constant int LOG_TYPE_LOG = LOG_TYPE_LOG;
%constant int LOG_TYPE_ERR = LOG_TYPE_ERR;
%constant int LOG_TYPE_DEBUG = LOG_TYPE_DEBUG;

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

    void log(int logtype, char *str)
    {
	clixon_beh_log_plugin(self->p, logtype, "%s", str);
    }
}

%constant int XMLOBJ_TYPE_ELEMENT = CX_ELMNT;
%constant int XMLOBJ_TYPE_ATTR = CX_ATTR;
%constant int XMLOBJ_TYPE_BODY = CX_BODY;

%nodefaultctor xmlobj;
struct xmlobj { };

%extend xmlobj {
    ~xmlobj()
    {
	free_xmlobj(self);
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

    %newobject get_flags;
    char *get_flags()
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

    char *get_attr(char *prefix, char *name)
    {
	return xml_find_type_value(self->xml, prefix, name, CX_ATTR);
    }
}

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

%rename(err) clixon_errt;
void clixon_errt(int oe, int ev, char *str);

%rename(log) clixon_logt;
void clixon_logt(int logtype, char *str);
