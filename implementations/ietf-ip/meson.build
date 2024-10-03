appname = 'ietf-ip'

conf_data = configuration_data()
conf_data.set('SYSCONFDIR', my_sysconfdir)
conf_data.set('DATADIR', my_datadir)
conf_data.set('LOCALSTATEDIR', my_localstatedir)
conf_data.set('SBINDIR', prefix + '/' + get_option('sbindir'))
conf_data.set('LIBEXECDIR', my_libexecdir)
conf_data.set('CLICON_GROUP', get_option('clicon_group'))
conf_data.set('CLICON_USER', get_option('clicon_user'))
conf_data.set('APPNAME', appname)

configure_file(input : appname + '.xml.in',
               output : appname + '.xml',
               configuration : conf_data,
	       install_dir: my_sysconfdir + '/clixon')

configure_file(input : 'clixon_beh.xml.in',
               output : 'clixon_beh.xml',
               configuration : conf_data,
	       install_dir: my_sysconfdir + '/clixon/' + appname + '/clixon_beh')

install_data('autocli.xml',
             install_dir: my_sysconfdir + '/clixon/' + appname)

install_data(appname + '_cli.cli',
             install_dir: my_sysconfdir + '/clixon/' + appname + '/clispec')

install_data(['iana-if-type@2014-05-08.yang',
	      'ietf-interfaces@2018-02-20.yang',
	      'ietf-ip@2018-02-22.yang'],
             install_dir: my_datadir + '/clixon/' + appname)

install_data('startup_db',
             install_dir: my_localstatedir + '/' + appname)

install_data('ietf-ip.py',
	     install_dir: my_libexecdir + '/' + appname)

