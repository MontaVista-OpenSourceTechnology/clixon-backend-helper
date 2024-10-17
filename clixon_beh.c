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
 * Back end helper code
 */

#include <dlfcn.h>
#include <stdbool.h>
#include <Python.h>

#include "clixon_beh.h"

static int
clixon_beh_vasprintf(char **rstr, const char *fmt, va_list va)
{
    va_list va2;
    size_t len;
    char c[1], *str;
    int rv;

    va_copy(va2, va);
    len = (size_t) vsnprintf(c, 0, fmt, va) + 1L;
    str = malloc(len);
    if (!str)
	return -1;
    rv = vsnprintf(str, len, fmt, va2);
    va_end(va2);

    if (rv < 0)
	free(str);
    else
	*rstr = str;
    return rv;
}

static int
clixon_beh_asprintf(char **rstr, const char *fmt, ...)
{
    va_list va;
    int rv;

    va_start(va, fmt);
    rv = clixon_beh_vasprintf(rstr, fmt, va);
    va_end(va);

    return rv;
}

struct clixon_beh_module {
    int refcount;
    /* Either the dlopen handle or the python module. */
    void *dlhandle;
    enum {
	CLIXON_BEH_C_PLUGIN,
	CLIXON_BEH_PYTHON_PLUGIN,
    } plugin_type;
};

static struct clixon_beh_module *curr_module;

struct clixon_beh_plugin {
    qelem_t link;

    struct clixon_beh *beh;
    char *name;
    char *namespace;
    const struct clixon_beh_api *api;
    void *cb_data;

    struct clixon_beh_module *module;
};

struct clixon_beh *
clixon_beh_plugin_get_beh(struct clixon_beh_plugin *p)
{
    return p->beh;
}

struct clixon_beh {
    clixon_handle h;
};

struct clixon_handle *
clixon_beh_get_handle(struct clixon_beh *beh)
{
    return beh->h;
}

struct clixon_beh_trans {
    cxobj *orig_xml;
    cxobj *new_xml;
    void *data;

    /* Trees in the td that are changed, indexed by namespace. */
    struct cvec *changed_trees;
};

void
clixon_beh_trans_set_data(struct clixon_beh_trans *t, void *data)
{
    t->data = data;
}

void *
clixon_beh_trans_get_data(struct clixon_beh_trans *t)
{
    return t->data;
}

cxobj *
clixon_beh_trans_orig_xml(struct clixon_beh_trans *t)
{
    return t->orig_xml;
}

cxobj *
clixon_beh_trans_new_xml(struct clixon_beh_trans *t)
{
    return t->new_xml;
}

static struct clixon_beh_plugin *plugins; /* Registered plugins */
static cvec *plugin_ns_present; /* Vector of the namespaces registered. */

#define clixon_beh_next_plugin(p) \
    (NEXTQ(struct clixon_beh_plugin *, (p)) == plugins ? NULL :	\
     NEXTQ(struct clixon_beh_plugin *, (p)))
#define clixon_beh_for_each_plugin(p) \
    for ((p) = plugins; (p) != NULL; p = clixon_beh_next_plugin(p))

static bool python_initialized;

int
clixon_beh_add_plugin(struct clixon_beh *beh,
		      const char *name, const char *namespace,
		      const struct clixon_beh_api *api,
		      void *cb_data,
		      struct clixon_beh_plugin **rp)
{
    int retval = -1;
    struct clixon_beh_plugin *p;

    p = calloc(1, sizeof(*p));
    if (!p) {
	clixon_err(OE_CFG, 0, "Unable to allocate clixon beh plugin");
	return -1;
    }
    p->name = strdup(name);
    if (!p->name) {
	clixon_err(OE_CFG, 0, "Unable to allocate clixon beh plugin name");
	goto out_err;
    }

    if (namespace) {
        cg_var *cv = cvec_find_var(plugin_ns_present, namespace);

	p->namespace = strdup(namespace);
	if (!p->namespace) {
	    clixon_err(OE_CFG, 0,
		       "Unable to allocate clixon beh plugin namespace");
	    goto out_err;
	}

	if (!cv) {
            cv = cvec_add(plugin_ns_present, CGV_UINT32);
            if (!cv) {
		clixon_err(OE_CFG, 0,
			   "Unable to allocate plugin namespace info");
                goto out_err;
            }
            if (!cv_name_set(cv, namespace)) {
		clixon_err(OE_CFG, 0,
			   "Unable to set plugin namespace info");
                goto out_err;
            }
        }
        cv_uint32_set(cv, cv_uint32_get(cv) + 1);
    }

    p->beh = beh;
    p->api = api;
    p->cb_data = cb_data;
    if (curr_module) {
	p->module = curr_module;
	curr_module->refcount++;
    }
    if (rp)
	*rp = p;
    ADDQ(p, plugins);
    p = NULL;
    retval = 0;
 out_err:
    if (p) {
	free(p->name);
	free(p->namespace);
	free(p);
    }
    return retval;
}

void
clixon_beh_del_plugin(struct clixon_beh_plugin *p)
{
    DELQ(p, plugins, struct clixon_beh_plugin *);
    if (p->api && p->api->exit)
	p->api->exit(p);
    if (p->name)
	free(p->name);
    if (p->namespace)
	free(p->namespace);

    if (p->module) {
	p->module->refcount--;
	if (p->module->refcount == 0) {
	    switch (p->module->plugin_type) {
	    case CLIXON_BEH_C_PLUGIN:
		if (p->module->dlhandle)
		    dlclose(p->module->dlhandle);
		break;

	    case CLIXON_BEH_PYTHON_PLUGIN:
		/*
		 * We finalize python before we delete the plugins so
		 * that automatic cleanup should clean everything up.
		 * If we get here and python is not initialized, we
		 * can't unload the module because it's going to be
		 * gone, anyway.
		 */
		if (python_initialized && p->module->dlhandle)
		    Py_DECREF(p->module->dlhandle);
		break;
	    }
	    free(p->module);
	}
    }
    free(p);
}

void *
clixon_beh_plugin_get_cb_data(struct clixon_beh_plugin *p)
{
    return p->cb_data;
}

static char *
xml_nsxml_fetch(cxobj *x)
{
    cxobj *c = NULL;

    while ((c = xml_child_each_attr(x, c)) != NULL) {
        if (strcmp(xml_name(c), "xmlns") == 0)
            return xml_value(c);
    }
    return NULL;
}

static int
nss_add_ns(cvec *nss, struct clixon_beh_trans *bt, const char *ns)
{
    cg_var *var;
    cvec *xnvec;

    var = cvec_find_var(nss, ns);
    if (!var) {
        xnvec = cvec_new(0);
        if (!xnvec)
            return -1;
        var = cvec_add(nss, CGV_VOID);
        if (!var) {
            cvec_free(xnvec);
            return -1;
        }
        if (!cv_name_set(var, ns)) {
            cvec_free(xnvec);
            return -1;
        }
        cv_void_set(var, xnvec);
    } else {
        xnvec = cv_void_get(var);
    }
    var = cvec_add(xnvec, CGV_VOID);
    if (!var)
        return -1;
    cv_void_set(var, bt);

    return 0;
}

static void
clixon_beh_trans_free(struct clixon_beh_trans *bt)
{
#if 0
    if (bt->dvec)
        free(bt->dvec);
    if (bt->avec)
        free(bt->avec);
    if (bt->scvec)
        free(bt->scvec);
    if (bt->tcvec)
        free(bt->tcvec);
#endif
    if (bt->changed_trees) {
        cg_var *var = NULL;

        while ((var = cvec_each(bt->changed_trees, var)) != NULL) {
            cvec *vec2 = cv_void_get(var);
            cg_var *var2 = NULL;

            while ((var2 = cvec_each(vec2, var2)) != NULL) {
                struct clixon_beh_trans *bt2 = cv_void_get(var2);
                /*
                 * Sub-transactions all have pointers into the main
                 * transaction, so there is no need to free anything
                 * unless we called xml_diff on it, and then just the
                 * parts it allocated.
                 */
                clixon_beh_trans_free(bt2);
            }
            cvec_free(vec2);
        }
        cvec_free(bt->changed_trees);
    }
    free(bt);
}

static cvec *
bt_find_changed_namespaces(struct clixon_beh_trans *obt)
{
    cvec  *nss;
    cxobj *xnorig = NULL, *xnnew = NULL;
    char  *ns;
    char  *ns2;
    struct clixon_beh_trans *bt = NULL;

    nss = cvec_new(0);
    if (!nss)
        return NULL;

    if (obt->orig_xml)
	xnorig = xml_child_each(obt->orig_xml, NULL, CX_ELMNT);
    if (obt->new_xml)
	xnnew = xml_child_each(obt->new_xml, NULL, CX_ELMNT);
    while (xnorig || xnnew) {
        if (xnorig && xml_flag(xnorig, XML_FLAG_DEL)) {
            ns = xml_nsxml_fetch(xnorig);
            if (ns) {
		if (cvec_find_var(plugin_ns_present, ns)) {
		    if ((bt = calloc(1, sizeof(*bt))) == NULL)
			goto fail;
		    bt->orig_xml = xnorig;
#if 0
		    if ((bt->dvec = malloc(sizeof(cxobj *))) == NULL)
			goto fail;
		    bt->dvec[0] = xnorig;
		    bt->dlen = 1;
#endif
		}
	    }
	    xnorig = xml_child_each(obt->orig_xml, xnorig, CX_ELMNT);
        } else if (xnnew && xml_flag(xnnew, XML_FLAG_ADD)) {
            ns = xml_nsxml_fetch(xnnew);
            if (ns) {
		if (cvec_find_var(plugin_ns_present, ns)) {
		    if ((bt = calloc(1, sizeof(*bt))) == NULL)
			goto fail;
		    bt->new_xml = xnnew;
#if 0
		    if ((bt->avec = malloc(sizeof(cxobj *))) == NULL)
			goto fail;
		    bt->avec[0] = xnnew;
		    bt->alen = 1;
#endif
		}
	    }
	    xnnew = xml_child_each(obt->new_xml, xnnew, CX_ELMNT);
        } else {
            if ((xnorig && xml_flag(xnorig, XML_FLAG_CHANGE)) ||
                (xnnew && xml_flag(xnnew, XML_FLAG_CHANGE))) {
                if (!xnnew || !xnorig) {
                    clixon_err(OE_XML, EINVAL,
			       "xnorig, xnnew, without the partner");
                    goto fail;
                }
                ns = xml_nsxml_fetch(xnorig);
                ns2 = xml_nsxml_fetch(xnnew);
                if (ns || ns2) {
		    if (!ns || !ns2 || strcmp(ns, ns2) != 0) {
			clixon_err(OE_XML, EINVAL, "xnorig/xnnew ns mismatch");
			goto fail;
		    }
		    if (cvec_find_var(plugin_ns_present, ns)) {
			if ((bt = calloc(1, sizeof(*bt))) == NULL)
			    goto fail;
			bt->orig_xml = xnorig;
			bt->new_xml = xnnew;
#if 0
			if (xml_diff(src,
				     tgt,
				     &bt->dvec,  /* removed: only in running */
				     &bt->dlen,
				     &bt->avec,  /* added: only in candidate */
				     &bt->alen,
				     &bt->scvec, /* changed: original values */
				     &bt->tcvec, /* changed: wanted values */
				     &bt->clen) < 0)
			    goto fail;
#endif
		    }
		}
	    }
            if (xnorig)
                xnorig = xml_child_each(obt->orig_xml, xnorig, CX_ELMNT);
            if (xnnew)
                xnnew = xml_child_each(obt->new_xml, xnnew, CX_ELMNT);
        }
        if (bt) {
            if (nss_add_ns(nss, bt, ns) < 0)
                goto fail;
            bt = NULL;
        }
    }

    return nss;
 fail:
    if (bt)
        clixon_beh_trans_free(bt);
    cvec_free(nss);
    return NULL;
}

static int
clixon_beh_trans_call_one(struct clixon_beh_plugin *p,
			  clixon_beh_transaction_cb fn,
			  struct clixon_beh_trans *bt)
{
    int  retval = 0;

    if (!fn)
	return 0;

    if (p->namespace) {
        cg_var *cv = cvec_find_var(bt->changed_trees, p->namespace);
        cvec *vec;

        if (cv) {
            vec = cv_void_get(cv);
            cv = NULL;
            while ((cv = cvec_each(vec, cv)) != NULL) {
                bt = cv_void_get(cv);
                retval = fn(p, bt);
                if (retval < 0)
                    break;
            }
        }
    } else {
        retval = fn(p, bt);
    }
    return retval;
}

static int
clixon_beh_begin(clixon_handle h, transaction_data td)
{
    int rv = 0;
    struct clixon_beh_plugin *p;
    struct clixon_beh_trans *bt;

    bt = calloc(1, sizeof(*bt));
    if (!bt) {
	clixon_err(OE_XML, 0, "Out of memory");
	return -1;
    }
    bt->orig_xml = transaction_src(td);
    bt->new_xml = transaction_target(td);
    bt->changed_trees = bt_find_changed_namespaces(bt);
    if (!bt->changed_trees) {
	free(bt);
	return -1;
    }
    transaction_arg_set(td, bt);

    clixon_beh_for_each_plugin(p) {
	if (p->api)
	    rv = clixon_beh_trans_call_one(p, p->api->begin, bt);
	if (rv < 0)
	    break;
    }

    return rv;
}

static int
clixon_beh_end(clixon_handle h, transaction_data td)
{
    int rv = 0;
    struct clixon_beh_plugin *p;
    struct clixon_beh_trans *bt = transaction_arg(td);

    clixon_beh_for_each_plugin(p) {
	if (p->api)
	    rv = clixon_beh_trans_call_one(p, p->api->end, bt);
	if (rv < 0)
	    break;
    }

    clixon_beh_trans_free(bt);
    return rv;
}

static int
clixon_beh_validate(clixon_handle h, transaction_data td)
{
    int rv = 0;
    struct clixon_beh_plugin *p;
    struct clixon_beh_trans *bt = transaction_arg(td);

    clixon_beh_for_each_plugin(p) {
	if (p->api)
	    rv = clixon_beh_trans_call_one(p, p->api->validate, bt);
	if (rv < 0)
	    break;
    }

    return rv;
}

static int
clixon_beh_complete(clixon_handle h, transaction_data td)
{
    int rv = 0;
    struct clixon_beh_plugin *p;
    struct clixon_beh_trans *bt = transaction_arg(td);

    clixon_beh_for_each_plugin(p) {
	if (p->api)
	    rv = clixon_beh_trans_call_one(p, p->api->complete, bt);
	if (rv < 0)
	    break;
    }

    return rv;
}

static int
clixon_beh_commit(clixon_handle h, transaction_data td)
{
    int rv = 0;
    struct clixon_beh_plugin *p;
    struct clixon_beh_trans *bt = transaction_arg(td);

    clixon_beh_for_each_plugin(p) {
	if (p->api)
	    rv = clixon_beh_trans_call_one(p, p->api->commit, bt);
	if (rv < 0)
	    break;
    }

    return rv;
}

static int
clixon_beh_commit_done(clixon_handle h, transaction_data td)
{
    int rv = 0;
    struct clixon_beh_plugin *p;
    struct clixon_beh_trans *bt = transaction_arg(td);

    clixon_beh_for_each_plugin(p) {
	if (p->api)
	    rv = clixon_beh_trans_call_one(p, p->api->commit_done, bt);
	if (rv < 0)
	    break;
    }

    return rv;
}

static int
clixon_beh_revert(clixon_handle h, transaction_data td)
{
    int rv = 0;
    struct clixon_beh_plugin *p;
    struct clixon_beh_trans *bt = transaction_arg(td);

    clixon_beh_for_each_plugin(p) {
	if (p->api)
	    rv = clixon_beh_trans_call_one(p, p->api->revert, bt);
	if (rv < 0)
	    break;
    }

    return rv;
}

static int
clixon_beh_abort(clixon_handle h, transaction_data td)
{
    int rv = 0;
    struct clixon_beh_plugin *p;
    struct clixon_beh_trans *bt = transaction_arg(td);

    if (!bt)
	return 0;

    clixon_beh_for_each_plugin(p) {
	if (p->api)
	    rv = clixon_beh_trans_call_one(p, p->api->abort, bt);
	if (rv < 0)
	    break;
    }

    clixon_beh_trans_free(bt);
    return rv;
}

static bool
clixon_beh_find_namespace(cvec *nsc, char *ns)
{
    cg_var *cv = NULL;
    while ((cv = cvec_each(nsc, cv)) != NULL) {
	char *s = cv_string_get(cv);
	if (s && strcmp(s, ns) == 0)
	    return true;
    }
    return false;
}

static int
clixon_beh_statedata(clixon_handle h, cvec *nsc, char *xpath, cxobj *xtop)
{
    int rv = 0;
    struct clixon_beh_plugin *p = plugins;

    clixon_beh_for_each_plugin(p) {
	rv = 0;
	if (p->api && p->api->statedata &&
		(!p->namespace || clixon_beh_find_namespace(nsc, p->namespace)))
	    rv = p->api->statedata(p, nsc, xpath, xtop);
	if (rv < 0)
	    break;
    }

    return rv;
}

static int
clixon_beh_system_only(clixon_handle h, cvec *nsc, char *xpath, cxobj *xtop)
{
    int rv = 0;
    struct clixon_beh_plugin *p = plugins;

    clixon_beh_for_each_plugin(p) {
	rv = 0;
	if (p->api && p->api->system_only &&
		(!p->namespace || clixon_beh_find_namespace(nsc, p->namespace)
		 /* FIXME - the following is a hack for now. */
		 || strcmp(xpath, "/") == 0))
	    rv = p->api->system_only(p, nsc, xpath, xtop);
	if (rv < 0)
	    break;
    }

    return rv;
}

static int
clixon_beh_exit(clixon_handle h)
{
    struct clixon_beh *beh = NULL;
    struct clixon_beh_plugin *p, *p2;
    const struct clixon_beh_api *api;

    if (plugins)
	beh = plugins->beh;

    /*
     * Shutting down is tricky.  The first thing we do is call all the
     * exit functions, allowing everything to clean up.  Python modules
     * should break all circular loops to avoid leaking memory.
     */
    p = plugins;
    while (p) {
	p2 = clixon_beh_next_plugin(p);
	api = p->api;
	p->api = NULL;
	if (api && api->exit)
	    api->exit(p);
	p = p2;
    }

    /*
     * Now we finalize python.  Any leftover python plugins should get
     * deleted unless there is a loop.
     */
    if (python_initialized) {
	Py_Finalize();
	python_initialized = false;
    }

    /*
     * Now we go through all the plugins that are left and delete them
     * completely.
     */
    while (plugins)
	clixon_beh_del_plugin(plugins);

    if (beh)
	free(beh);
    if (plugin_ns_present)
	cvec_free(plugin_ns_present);
    return 0;
}

static int
clixon_beh_pre_daemon(clixon_handle h)
{
    int rv = 0;
    struct clixon_beh_plugin *p;

    clixon_beh_for_each_plugin(p) {
	if (p->api && p->api->pre_daemon)
	    rv = p->api->pre_daemon(p);
	if (rv < 0)
	    break;
    }

    return rv;
}

static int
clixon_beh_daemon(clixon_handle h)
{
    int rv = 0;
    struct clixon_beh_plugin *p;

    clixon_beh_for_each_plugin(p) {
	if (p->api && p->api->daemon)
	    rv = p->api->daemon(p);
	if (rv < 0)
	    break;
    }

    return rv;
}

static int
clixon_beh_reset(clixon_handle h, const char *db)
{
    int rv = 0;
    struct clixon_beh_plugin *p;

    clixon_beh_for_each_plugin(p) {
	if (p->api && p->api->reset)
	    rv = p->api->reset(p, db);
	if (rv < 0)
	    break;
    }

    return rv;
}

static int
clixon_beh_lockdb(clixon_handle h, char *db, int lock, int id)
{
    int rv = 0;
    struct clixon_beh_plugin *p;

    clixon_beh_for_each_plugin(p) {
	if (p->api && p->api->lockdb)
	    rv = p->api->lockdb(p, db, lock, id);
	if (rv < 0)
	    break;
    }

    return rv;
}

static clixon_plugin_api api = {
    .ca_name = "clixon_beh backend",
    .ca_init = clixon_plugin_init,
    .ca_exit = clixon_beh_exit,
    .ca_pre_daemon = clixon_beh_pre_daemon,
    .ca_daemon = clixon_beh_daemon,
    .ca_reset = clixon_beh_reset,
    .ca_lockdb = clixon_beh_lockdb,
    .ca_statedata = clixon_beh_statedata,
    .ca_system_only = clixon_beh_system_only,
    .ca_trans_begin = clixon_beh_begin,
    .ca_trans_end = clixon_beh_end,
    .ca_trans_validate = clixon_beh_validate,
    .ca_trans_complete = clixon_beh_complete,
    .ca_trans_commit = clixon_beh_commit,
    .ca_trans_commit_done = clixon_beh_commit_done,
    .ca_trans_revert = clixon_beh_revert,
    .ca_trans_abort = clixon_beh_abort,
};

static int
clixon_beh_plugin_load_one_so(struct clixon_beh *beh, char *plugin_file,
			      int dlflags)
{
    int retval = -1, rv;
    void *handle = NULL;
    clixon_beh_initfn initfn;
    struct clixon_beh_plugin *tail = NULL;

    dlerror();
    if ((handle = dlopen(plugin_file, dlflags)) == NULL) {
        char *error = dlerror();
        clixon_err(OE_PLUGIN, errno, "dlopen(%s): %s", plugin_file,
		   error ? error : "Unknown error");
        goto out_err;
    }
    if ((initfn = dlsym(handle, CLIXON_BEH_PLUGIN_INIT)) == NULL){
        char *error = dlerror();
        clixon_err(OE_PLUGIN, errno,
		   "Failed to find %s when loading clixon plugin %s: %s",
		   CLIXON_BEH_PLUGIN_INIT, plugin_file,
		   error ? error : "Unknown");
        goto out_err;
    }

    curr_module = calloc(1, sizeof(*curr_module));
    if (!curr_module) {
        clixon_err(OE_PLUGIN, 0, "Unable to allocate module");
        goto out_err;
    }
    curr_module->plugin_type = CLIXON_BEH_C_PLUGIN;
    curr_module->dlhandle = handle;
    handle = NULL;

    tail = PREVQ(struct clixon_beh_plugin *, plugins);
    rv = initfn(beh);

    if (rv < 0) {
	clixon_err(OE_PLUGIN, errno, "Failed to initialize %s",
		   plugin_file);
	goto out_err;
    }

    if (curr_module->refcount == 0) {
	/* No new plugins were registered, warn and return. */
	clixon_log(beh->h, LOG_DEBUG, "Warning: No plugins in %s",
		   plugin_file);
	retval = 0;
	goto out_err;
    }

    curr_module = NULL;
    retval = 1;

 out_err:
    if (retval != 1) {
	/* Delete the plugins we added. */
        while (tail != PREVQ(struct clixon_beh_plugin *, plugins))
	    clixon_beh_del_plugin(PREVQ(struct clixon_beh_plugin *, plugins));
    }
    if (curr_module) {
	if (curr_module->refcount == 0) {
	    if (curr_module->dlhandle)
		dlclose(curr_module->dlhandle);
	    free(curr_module);
	}
	curr_module = NULL;
    }
    if (handle)
	dlclose(handle);
    return retval;
}

static int
clixon_beh_plugin_load_one_py(struct clixon_beh *beh, const char *modname,
			      const char *full_path)
{
    int retval = -1;
    PyObject *module = NULL;
    char *modstr, *s;
    struct clixon_beh_plugin *tail = NULL;

    /* Get the name without the '.py'. */
    modstr = strdup(modname);
    if (!modstr) {
	clixon_err(OE_PLUGIN, errno, "Failed to allocate module name %s",
		   full_path);
	goto out_err;
    }
    s = strrchr(modstr, '.');
    if (s)
	*s = '\0';

    curr_module = calloc(1, sizeof(*curr_module));
    if (!curr_module) {
        clixon_err(OE_PLUGIN, 0, "Unable to allocate module");
        goto out_err;
    }
    curr_module->plugin_type = CLIXON_BEH_PYTHON_PLUGIN;

    tail = PREVQ(struct clixon_beh_plugin *, plugins);
    module = PyImport_ImportModule(modstr);

    if (PyErr_Occurred()) {
	/* FIXME - convert to clixon_err() */
	PyErr_Print();
	clixon_err(OE_PLUGIN, errno, "Failed to initialize %s",
		   full_path);
	goto out_err;
    }

    if (curr_module->refcount == 0) {
	/* No new plugins were registered, warn and return. */
	clixon_log(beh->h, LOG_DEBUG, "Warning: No plugins in %s",
		   full_path);
	retval = 0;
	goto out_err;
    }

    curr_module->dlhandle = module;
    curr_module = NULL;
    module = NULL;
    retval = 1;

 out_err:
    if (retval != 1) {
	/* Delete the plugins we added. */
        while (tail != PREVQ(struct clixon_beh_plugin *, plugins))
	    clixon_beh_del_plugin(PREVQ(struct clixon_beh_plugin *, plugins));
    }
    if (curr_module) {
	if (curr_module->refcount == 0) {
	    if (curr_module->dlhandle)
		Py_DECREF(curr_module->dlhandle);
	    free(curr_module);
	}
	curr_module = NULL;
    }
    if (module)
	Py_DECREF(module);
    return retval;
}

static int
clixon_beh_load_plugins(struct clixon_beh *beh,
			const char *plugin_dir)
{
    int retval = -1;
    int ndp;
    struct dirent *dp = NULL;
    int i;
    int dlflags;
    char *plugin_file = NULL, *suffix;

    if ((ndp = clicon_file_dirent(plugin_dir, &dp, "\\.(so|py)$", S_IFREG)) < 0)
	return -1;
    for (i = 0; i < ndp; i++) {
        if (clixon_beh_asprintf(&plugin_file,
				"%s/%s", plugin_dir, dp[i].d_name) < 0) {
	    clixon_err(OE_CFG, 0, "Out of memory allocation plugin filename");
	    goto out_err;
	}
        clixon_debug(CLIXON_DBG_INIT, "Loading plugin '%s'", plugin_file);
	suffix = strrchr(dp[i].d_name, '.');
	if (!suffix)
	    continue; /* Shouldn't be possible. */
	if (strcmp(suffix, ".so") == 0) {
	    dlflags = RTLD_NOW;
	    if (clicon_option_bool(beh->h, "CLICON_PLUGIN_DLOPEN_GLOBAL"))
		dlflags |= RTLD_GLOBAL;
	    else
		dlflags |= RTLD_LOCAL;
	    if (clixon_beh_plugin_load_one_so(beh, plugin_file, dlflags) < 0)
		goto out_err;
	} else if (strcmp(suffix, ".py") == 0) {
	    if (!python_initialized) {
		char *pathcmd;

		if (clixon_beh_asprintf(&pathcmd, "sys.path.append(\"%s\")",
					plugin_dir) < 0) {
		    clixon_err(OE_CFG, 0, "Out of memory getting python path");
		    goto out_err;
		}

		Py_Initialize();
		PyRun_SimpleString("import sys");
		PyRun_SimpleString(pathcmd);
		python_initialized = true;
		free(pathcmd);
	    }
	    if (clixon_beh_plugin_load_one_py(beh, dp[i].d_name,
					      plugin_file) < 0)
		goto out_err;
	}
	free(plugin_file);
	plugin_file = NULL;
    }
    if (!plugins) {
	clixon_beh_log(beh, LOG_DEBUG,
		       "Warning: No plugins in %s", plugin_dir);
	retval = 0;
    } else {
	retval = 1;
    }
 out_err:
    if (dp)
        free(dp);
    if (plugin_file)
	free(plugin_file);
    return retval;
}

static int
clixon_beh_parse_config_file(clixon_handle  h,
			     const char    *filename,
			     yang_stmt     *yspec,
			     cxobj        **xconfig)
{
    int    retval = -1;
    FILE  *fp = NULL;
    cxobj *xt = NULL;
    cxobj *xerr = NULL;
    cxobj *xa;
    int    ret;

    if ((fp = fopen(filename, "r")) == NULL) {
        clixon_err(OE_UNIX, errno, "open configure file: %s", filename);
        return -1;
    }
    if ((ret = clixon_xml_parse_file(fp, YB_MODULE, yspec, &xt, &xerr)) < 0)
        goto out_err;
    if (ret == 0){
        clixon_err_netconf(h, OE_NETCONF, 0, xerr, "Config file: %s", filename);
        goto out_err;
    }
    /* Ensure a single root */
    if (xt == NULL || xml_child_nr(xt) != 1) {
        clixon_err(OE_CFG, 0,
		   "Config file %s: Lacks single top element", filename);
        goto out_err;
    }
    if (xml_rootchild(xt, 0, &xt) < 0)
        goto out_err;

    /* Check well-formedness */
    if (strcmp(xml_name(xt), "clixon-beh-config") != 0 ||
              (xa = xml_find_type(xt, NULL, "xmlns", CX_ATTR)) == NULL ||
              strcmp(xml_value(xa), CLIXON_BEH_NAMESPACE) != 0){
        clixon_err(OE_CFG, 0, "Config file %s: Lacks top-level \"clixon-beh-config\" element\nClixon config files should begin with: <clixon-beh-config xmlns=\"%s\">", filename, CLIXON_BEH_NAMESPACE);
        goto out_err;
    }
    *xconfig = xt;
    xt = NULL;
    retval = 0;
 out_err:
    if (xt)
        xml_free(xt);
    if (fp)
        fclose(fp);
    if (xerr)
        xml_free(xerr);
    return retval;
}

static struct clixon_beh *global_beh;
struct clixon_beh *clixon_beh_get_global_beh(void)
{
    return global_beh;
}

clixon_plugin_api *
clixon_plugin_init(clixon_handle h) {
    char *cfgdir, *mycfgfile = NULL;
    clixon_plugin_api *rapi = NULL;
    const char *yangspec = "clixon-beh-config";
    yang_stmt *yspec = NULL;
    cxobj *xconfig = NULL, *x;
    char *plugin_dir = NULL;
    struct clixon_beh *beh = NULL;

    clixon_debug(CLIXON_DBG_DEFAULT, "clixon_be_helper Entry\n");

    beh = calloc(1, sizeof(*beh));
    if (!beh) {
	clixon_err(OE_CFG, 0, "Can't allocate beh");
	goto out_err;
    }
    beh->h = h;

    plugin_ns_present = cvec_new(0);
    if (!plugin_ns_present) {
	clixon_err(OE_CFG, 0, "Can't allocate plugin_ns_present");
	goto out_err;
    }

    cfgdir = clicon_option_str(h, "CLICON_CONFIGDIR");
    if (!cfgdir) {
	clixon_err(OE_CFG, 0, "CLICON_CONFIGDIR not set");
	goto out_err;
    }
    if (clixon_beh_asprintf(&mycfgfile, "%s/clixon_beh/clixon_beh.xml", cfgdir) < 0) {
	clixon_err(OE_CFG, 0, "Out of memory allocation clixon_beh.xml");
	goto out_err;
    }
    if ((yspec = yspec_new(h, "clixon_beh")) == NULL)
        goto out_err;
    if (yang_spec_parse_module(h, yangspec, NULL, yspec) < 0)
        goto out_err;
    if (clixon_beh_parse_config_file(h, mycfgfile, yspec, &xconfig) < 0) {
	yspec = NULL; /* It's now owned by the module code. */
        goto out_err;
    }
    yspec = NULL; /* It's now owned by the module code. */
    if (xml_spec(xconfig) == NULL){
        clixon_err(OE_CFG, 0, "Config file %s: did not find corresponding Yang specification\nHint: File does not begin with: <clixon-beh-config xmlns=\"%s\"> or clixon-beh-config.yang not found?", mycfgfile, CLIXON_BEH_NAMESPACE);
        goto out_err;
    }

    global_beh = beh;
    x = NULL;
    while ((x = xml_child_each(xconfig, x, CX_ELMNT)) != NULL) {
	char *name = xml_name(x);

	if (strcmp(name, "CLIXON_BEH_PLUGIN_DIR") == 0) {
	    plugin_dir = xml_body(x);
	    if (!plugin_dir) {
		clixon_err(OE_CFG, 0, "CLIXON_BEH_PLUGIN_DIR didn't have body");
		global_beh = NULL;
		goto out_err;
	    }
	    if (clixon_beh_load_plugins(beh, plugin_dir) <= 0) {
		global_beh = NULL;
		goto out_err;
	    }
	} else {
	    clixon_err(OE_CFG, 0, "Unknown element: %s", name);
	}
    }
    if (!plugin_dir) {
	clixon_err(OE_CFG, 0, "CLIXON_BEH_PLUGIN_DIR not present");
	global_beh = NULL;
	goto out_err;
    }

    beh = NULL;
    rapi = &api;

 out_err:
    if (!rapi && plugin_ns_present)
	cvec_free(plugin_ns_present);
    if (xconfig)
        xml_free(xconfig);
    if (yspec)
        ys_free(yspec);
    if (mycfgfile)
	free(mycfgfile);
    if (beh)
	free(beh);
    return rapi;
}
