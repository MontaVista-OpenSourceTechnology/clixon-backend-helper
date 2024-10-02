appname = 'linux-system'

conf_data = configuration_data()
conf_data.set('SYSCONFDIR', my_sysconfdir)
conf_data.set('DATADIR', my_datadir)
conf_data.set('LIBDIR', my_libdir)
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
             install_dir: my_libdir + '/' + appname + '/clispec')

install_data(['ietf-system@2014-08-06.yang',
	      'iana-crypt-hash@2014-08-06.yang',
	      'linux-system@2024-06-19.yang'],
             install_dir: my_datadir + '/clixon/' + appname)

install_data('startup_db',
             install_dir: my_localstatedir + '/' + appname)

install_data('linux-system.py',
	     install_dir: my_libexecdir + '/' + appname)

