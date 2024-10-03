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
 */

/*
 */

#include <stdbool.h>

#include <clixon_beh.h>

/*
 * This file reflects the "system state" of hello world.  If it
 * exists, hello world is set.  If it does not exit, then hello world
 * is not set.  If it exists, it contains the "to" value.  This is
 * what is set in the commit call and fetched in the statedata call.
 */
#define WORLD_FILE "/tmp/world"

#define HELLO_BEH_NAMESPACE "http://clixon_beh/hello"

/*
 * Set this to 1 to print out the XML data received in validate.
 * Only really useful if you run clixon_backend in foreground (-F).
 */
#define DEBUG_XML_STRINGS 0

/*
 * The operation to perform on the data.  This is allocated in the
 * begin function, freed in the end function, set in the validate
 * function, and implemented in the commit function.
 */
struct hello_data {
    char to[10]; /* On HELLO_ADD, the value to put into WORLD_FILE. */
    enum {
        HELLO_NOP, /* Don't do anything. */
        HELLO_ADD, /* Create or update the WORLD_FILE. */
        HELLO_DEL  /* Delete the WORLD_FILE. */
    } op;
};

/*
 * Allocate a structure for us to store the results of validation in.
 * This is so we don't have to parse again in the commit.
 */
static int
hello_begin(struct clixon_beh_plugin *p, struct clixon_beh_trans *t) {
    struct hello_data *data;

    clixon_debug(CLIXON_DBG_DEFAULT, "Entry\n");
    data = malloc(sizeof(*data));
    if (!data) {
        clixon_err(OE_XML, 0, "Could not allocate memory");
        return -1;
    }
    data->op = HELLO_NOP;
    memset(data->to, 0, sizeof(data->to));
    clixon_beh_trans_set_data(t, data);
    return 0;
}

/*
 * Free the data for the transaction.
 */
static int
hello_end(struct clixon_beh_plugin *p, struct clixon_beh_trans *t) {
    struct hello_data *data = clixon_beh_trans_get_data(t);

    clixon_debug(CLIXON_DBG_DEFAULT, "Entry\n");
    free(data);
    return 0;
}

static const char *valid_tos[] = { "city", "state", "country", "world", NULL };

/*
 * Validate that the current XML object is of the form:
 *   <hello xmlns="urn:example:hello_beh">
 *     <to>world</to>
 *   </hello>
 * Returns the contents of "to" in str.
 *
 * Return value is 0 for not found, 1 for found, and -1 for error.
 */
static int
find_hello_to(cxobj *vec, const char **str)
{
    bool to_found = false;
    cxobj *c = NULL;
    int i;
    char *s, *ns;

    if (strcmp(xml_name(vec), "hello") != 0)
        return 0;

    /*
     * Get the namespace of this object.  You can't use xml2ns() here,
     * it will search up the tree for a namespace, and and possible
     * return the default namespace.  We want it for this object only.
     */
    ns = xml_find_type_value(vec, NULL, "xmlns", CX_ATTR);
    if (!ns || strcmp(ns, HELLO_BEH_NAMESPACE) != 0)
        return 0;

    while ((c = xml_child_each(vec, c, CX_ELMNT))) {
        if (strcmp(xml_name(c), "to") != 0) {
            clixon_err(OE_XML, 0, "Non-\"to\" in hello vec: %s",
                       xml_name(c));
            return -1;
        }
        if (to_found) {
            clixon_err(OE_XML, 0, "Multiple \"to\" in hello vec");
            return -1;
        }

        s = xml_body(c);
        if (!s) {
            clixon_err(OE_XML, 0, "The \"to\" element doesn't have a value");
            return -1;
        }

        for (i = 0; valid_tos[i]; i++) {
            if (strcmp(valid_tos[i], s) == 0)
                break;
        }
        if (!valid_tos[i]) {
            clixon_err(OE_XML, 0, "Invalid \"to\" element: %s", s);
            return -1;
        }

        *str = valid_tos[i];
        to_found = true;
    }

    if (to_found)
        return 1;
    return 0;
}

#if DEBUG_XML_STRINGS
static const char *xml_flag_strs[] = {
    "mark",
    "transient",
    "add",
    "del",
    "change",
    "none",
    "default",
    "top",
    "bodykey",
    "anydata",
    NULL
};

static void
print_xml_flags(FILE *f, uint16_t flags)
{
    unsigned int i;

    for (i = 0; xml_flag_strs[i]; i++) {
        if (flags & 1 << i)
            fprintf(f, " %s", xml_flag_strs[i]);
    }
}

static void
print_xml(FILE *f, int indent, cxobj *x)
{
    char *name, *value, *prefix, *s;
    uint16_t flags;
    cxobj *c;
    unsigned int i;

    if (!x)
        return;
    name = xml_name(x);
    value = xml_value(x);
    prefix = xml_prefix(x);
    flags = xml_flag(x, 0xffff);
    for (i = 0; i < indent; i++)
        fputc(' ', f);
    fputs(name, f);
    if (value) {
        fputc('=', f);
        fputs(value, f);
    }
    if (prefix) {
        fputc('(', f);
        fputs(prefix, f);
        fputc(')', f);
    }
    print_xml_flags(f, flags);

    s = xml_body(x);
    if (s) {
        fprintf(f, ": %s\n", s);
    } else {
        fputc('\n', f);
        for (i = 0; (c = xml_child_i(x, i)); i++)
            print_xml(f, indent + 2, c);
    }
}
#endif

/*
 * There are two basic ways to process the data given to validate (and
 * commit).  This define chooses which.  Setting to 1 causes validate
 * to go through the add/delete/changed xml tree and handle those.
 * Setting to 0 caused validate to directly process the source (the
 * old values) and target (the new values) trees for values that are
 * flagged ADD, DELETE, or CHANGED.
 */
#define PROCESS_VECS 0

/*
 * Validate the XML.  If we find that the WORLD_FILE needs to change,
 * we modify the hello_data struct to reflect what needs to be done.
 */
static int
hello_validate(struct clixon_beh_plugin *p, struct clixon_beh_trans *t) {
    struct hello_data *data = clixon_beh_trans_get_data(t);
    int rv;
    const char *place;
    cxobj *xt;

    clixon_debug(CLIXON_DBG_DEFAULT, "Entry\n");
#if DEBUG_XML_STRINGS
    clixon_debug(CLIXON_DBG_DEFAULT, "src:\n");
    print_xml(stdout, 2, transaction_src(td));
    clixon_debug(CLIXON_DBG_DEFAULT, "target:\n");
    print_xml(stdout, 2, transaction_target(td));
    clixon_debug(CLIXON_DBG_DEFAULT, "transaction:\n");
    transaction_print(stdout, td);
#endif

    /*
     * Get the previous data.  Here we only care about deletes, we
     * pick up changes in the target tree.
     */
    xt = clixon_beh_trans_orig_xml(t);
    if (xt) {
	rv = find_hello_to(xt, &place);
	if (rv == -1)
	    return -1;
	if (rv == 1) {
	    if (xml_flag(xt, XML_FLAG_DEL)) {
		strncpy(data->to, place, sizeof(data->to) - 1);
		data->op = HELLO_DEL;
	    }
	}
    }

    /*
     * Now go through the new data.  We look for additions and
     * changes, they are treated the same for this.
     */
    xt = clixon_beh_trans_new_xml(t);
    if (xt) {
	rv = find_hello_to(xt, &place);
	if (rv == -1)
	    return -1;
	if (rv) {
	    if (xml_flag(xt, XML_FLAG_ADD | XML_FLAG_CHANGE)) {
		strncpy(data->to, place, sizeof(data->to) - 1);
		data->op = HELLO_ADD;
	    }
	}
    }

    return 0;
}

/*
 * Take the value of hello_data and apply it.  If a change was
 * requested, the validate call will have set the data appropriately.
 */
static int
hello_commit(struct clixon_beh_plugin *p, struct clixon_beh_trans *t) {
    struct hello_data *data = clixon_beh_trans_get_data(t);
    FILE *f;
    int rv;

    clixon_debug(CLIXON_DBG_DEFAULT, "op: %d\n", data->op);
    switch (data->op) {
    case HELLO_DEL:
        rv = remove(WORLD_FILE);
        if (rv < 0 && errno != ENOENT) {
            clixon_err(OE_XML, 0, "Error deleting %s: %s",
                       WORLD_FILE, strerror(errno));
            return -1;
        }
        break;

    case HELLO_ADD:
        f = fopen("/tmp/world", "w");
        if (!f) {
            clixon_err(OE_XML, 0, "Error creating %s: %s",
                       WORLD_FILE, strerror(errno));
            return -1;
        }
        fprintf(f, "%s", data->to);
        fclose(f);

    case HELLO_NOP:
        break;
    }
    return 0;
}

/*
 * Retrieve the current state of WORLD_FILE from the filesystem and
 * return it in the XML structure xtop.
 */
static int
hello_statedata(struct clixon_beh_plugin *p,
		cvec *nsc, char *xpath, cxobj *xtop)
{
    int rv = -1;
    cxobj **xvec = NULL;
    FILE *f = fopen(WORLD_FILE, "r");
    char to[10], xmlstr[200];
    int k;
    char *s;
    int found = 0;

    clixon_debug(CLIXON_DBG_DEFAULT, "file: %p\n", f);
    clixon_debug(CLIXON_DBG_DEFAULT, "  xpath=%s\n", xpath);
    for (k = 0; (s = cvec_i_str(nsc, k)) != NULL; k++) {
        clixon_debug(CLIXON_DBG_DEFAULT, "  nsc(%d)=%s\n", k, s);
        if (strcmp(s, HELLO_BEH_NAMESPACE) == 0)
            found = 1;
    }
    if (!found)
        return -1;

    if (f) {
        memset(to, 0, sizeof(to));
        k = fread(to, 1, 9, f);
        fclose(f);

        if (!k) {
            clixon_err(OE_XML, 0, "Empty %s contents", WORLD_FILE);
            goto done;
        }
        for (k = 0; valid_tos[k]; k++) {
            if (strcmp(valid_tos[k], to) == 0)
                break;
        }
        if (!valid_tos[k]) {
            clixon_err(OE_XML, 0, "Invalid %s contents: %s", WORLD_FILE, to);
            goto done;
        }

        snprintf(xmlstr, sizeof(xmlstr),
                 "<hello xmlns=\"%s\"><to>%s</to></hello>",
                 HELLO_BEH_NAMESPACE, to);
        if (clixon_xml_parse_string(xmlstr, YB_NONE, NULL, &xtop, NULL) < 0)
            goto done;
    } else {
        if (clixon_xml_parse_string("", YB_NONE, NULL, &xtop, NULL) < 0)
            goto done;
    }
    rv = 0;
 done:
    if (xvec)
        free(xvec);
    return rv;
}

static struct clixon_beh_api api = {
    .statedata = hello_statedata,
    .begin = hello_begin,
    .end = hello_end,
    .commit = hello_commit,
    .validate = hello_validate,
};

int
clixon_beh_plugin_init(struct clixon_beh *beh)
{
    clixon_debug(CLIXON_DBG_DEFAULT, "Entry\n");
    return clixon_beh_add_plugin(beh, "hello_beh", HELLO_BEH_NAMESPACE,
				 &api, NULL, NULL);
}
