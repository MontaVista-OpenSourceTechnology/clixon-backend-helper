project('clixon-backend-helper', 'c')

prefix = get_option('prefix')
my_libexecdir = prefix + '/' + get_option('libexecdir')
my_datadir = prefix + '/' + get_option('datadir')

shared_library('clixon_beh', 'clixon_beh.c',
               name_prefix: '',
               override_options: 'b_lundef=false',
	       install: true,
	       install_dir: my_libexecdir + '/clixon_beh')

install_data('clixon-beh-config@2024-06-05.yang',
             install_dir: my_datadir + '/clixon')

install_headers('clixon_beh.h')
