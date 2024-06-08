project('hello-clixon-backend-helper', 'c')

appname = 'hello_beh'

prefix = get_option('prefix')
if get_option('prefix') == '/usr'
  my_sysconfdir = get_option('sysconfdir')
  my_localstatedir = get_option('localstatedir')
else
  my_sysconfdir = prefix + '/' + get_option('sysconfdir')
  my_localstatedir = prefix + '/var'
endif
my_libexecdir = prefix + '/' + get_option('libexecdir')
my_datadir = prefix + '/' + get_option('datadir')
my_libdir = prefix + '/lib'

conf_data = configuration_data()
conf_data.set('SYSCONFDIR', my_sysconfdir)
conf_data.set('DATADIR', prefix + '/' + get_option('datadir'))
conf_data.set('LIBDIR', my_libdir)
conf_data.set('LOCALSTATEDIR', my_localstatedir)
conf_data.set('SBINDIR', prefix + '/' + get_option('sbindir'))
conf_data.set('LIBEXECDIR', my_libexecdir)
conf_data.set('CLICON_GROUP', get_option('clicon_group'))
conf_data.set('CLICON_USER', get_option('clicon_user'))

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

install_data('clixon-hello-beh@2024-05-25.yang',
             install_dir: my_datadir + '/clixon/' + appname)

install_data('startup_db',
             install_dir: my_localstatedir + '/' + appname)

shared_library('hello_clixon_beh', 'hello_clixon_beh.c',
               name_prefix: '',
               override_options: 'b_lundef=false',
	       install: true,
	       install_dir: my_libexecdir + '/' + appname)

