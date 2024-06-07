/*
 *  clixon-be-help - A clixon backin plugin helper
 *  Copyright (C) 2024  Montavista Software, LLC <source@mvista.com>
 *
 *  SPDX-License-Identifier: LGPL-2.1-only
 */

#ifndef CLIXON_BE_HELPER_H
#define CLIXON_BE_HELPER_H

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <inttypes.h>
#include <string.h>
#include <errno.h>
#include <signal.h>
#include <unistd.h>
#include <syslog.h>
#include <fcntl.h>
#include <sys/time.h>

#include <cligen/cligen.h>
#include <clixon/clixon.h>
#include <clixon/clixon_backend.h> 

#define clixon_beh_stringify(a) clixon_beh_stringify2(a)
#define clixon_beh_stringify2(a) #a

struct clixon_beh;
struct clixon_beh_plugin;
struct clixon_beh_trans;

typedef int (*clixon_beh_daemon_cb)(struct clixon_beh_plugin *p);
typedef int (*clixon_beh_exit_cb)(struct clixon_beh_plugin *p);
typedef int (*clixon_beh_reset_cb)(struct clixon_beh_plugin *p, const char *cb);
typedef int (*clixon_beh_lockdb_cb)(struct clixon_beh_plugin *p,
				    const char *db, int lock, int id);
typedef int (*clixon_beh_transaction_cb)(struct clixon_beh_plugin *p,
					 struct clixon_beh_trans *t);
typedef int (*clixon_beh_statedata_cb)(struct clixon_beh_plugin *p,
				       cvec *nsc, char *xpath, cxobj *xtop);
typedef int (*clixon_beh_dstore_upgrade_cb)(struct clixon_beh_plugin *p,
					    const char *db, cxobj *xt,
					    modstate_diff_t *msd);

struct clixon_beh_api {
    clixon_beh_daemon_cb      pre_daemon;     /* Plugin just before daemonization (only daemon) */
    clixon_beh_daemon_cb      daemon;         /* Plugin daemonized (always called) */
    clixon_beh_reset_cb       reset;          /* Reset system status */
    clixon_beh_statedata_cb   statedata;      /* Provide state data XML from plugin */
    clixon_beh_lockdb_cb      lockdb;         /* Database lock changed state */
    clixon_beh_exit_cb        exit;
    clixon_beh_transaction_cb begin;    /* Transaction start */
    clixon_beh_transaction_cb validate; /* Transaction validation */
    clixon_beh_transaction_cb complete; /* Transaction validation complete */
    clixon_beh_transaction_cb commit;   /* Transaction commit */
    clixon_beh_transaction_cb commit_done; /* Transaction when commit done */
    clixon_beh_transaction_cb revert;   /* Transaction revert */
    clixon_beh_transaction_cb end;      /* Transaction completed  */
    clixon_beh_transaction_cb abort;    /* Transaction aborted */
    clixon_beh_dstore_upgrade_cb datastore_upgrade; /* General-purpose datastore upgrade */
};

int clixon_beh_add_plugin(struct clixon_beh *h,
			  const char *name, const char *namespace,
			  const char *priv_program,
			  const struct clixon_beh_api *api,
			  void *cb_data,
			  struct clixon_beh_plugin **p);

void *clixon_beh_plugin_get_cb_data(struct clixon_beh_plugin *p);
int clixon_beh_priv_func_stdin(struct clixon_beh_plugin *p);
int clixon_beh_priv_func_stdout(struct clixon_beh_plugin *p);

#define CLIXON_BEH_NAMESPACE "http://mvista.com/clixon-beh/config"

void clixon_beh_trans_set_data(struct clixon_beh_trans *t, void *data);
void *clixon_beh_trans_get_data(struct clixon_beh_trans *t);
cxobj *clixon_beh_trans_orig_xml(struct clixon_beh_trans *t);
cxobj *clixon_beh_trans_new_xml(struct clixon_beh_trans *t);

typedef int (*clixon_beh_initfn)(struct clixon_beh *beh);
#define CLIXON_BEH_PLUGIN_INITFN clixon_beh_plugin_init
#define CLIXON_BEH_PLUGIN_INIT clixon_beh_stringify(CLIXON_BEH_PLUGIN_INITFN)
int CLIXON_BEH_PLUGIN_INITFN(struct clixon_beh *beh);

struct clixon_beh *clixon_beh_plugin_get_beh(struct clixon_beh_plugin *p);
struct clixon_handle *clixon_beh_get_handle(struct clixon_beh *beh);

#define clixon_beh_log(beh, l, fmt, args...) \
    clixon_log(clixon_beh_get_handle(beh), l, fmt, ##args)

#define clixon_beh_log_plugin(p, l, fmt, args...) \
    clixon_beh_log(clixon_beh_plugin_get_beh(p), l, fmt, ##args)

#endif /* CLIXON_BE_HELPER_H */
