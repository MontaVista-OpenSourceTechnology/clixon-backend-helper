project('clixon-backend-helper', 'c')

prefix = get_option('prefix')
my_libexecdir = prefix + '/' + get_option('libexecdir')
my_datadir = prefix + '/' + get_option('datadir')

py3 = import('python').find_installation('python3')
pylib = py3.get_variable('BLDLIBRARY')
pyinc = py3.get_variable('INCLUDEPY')

if get_option('prefix') == '/usr'
  pyinstall = py3.get_variable('DESTLIB')
  pyinstall_so = py3.get_variable('DESTSHARED')
else
  pyver = py3.get_variable('py_version_short')
  pyinstall = prefix + '/lib/python' + pyver + '/dist-packages'
  pyinstall_so = pyinstall
endif

swig = find_program('swig')
swig_py_gen = custom_target(
    'clixon_beh.py',
    input: ['clixon_beh.i'],
    output: ['clixon_beh.py', 'pyclixon_beh.c'],
    command: [swig, '-python', '-o', '@OUTPUT1@',
                '-outdir', '.', '@INPUT@'],
    install: true,
    install_dir: [pyinstall]
)

shared_library('_clixon_beh', swig_py_gen[1],
               name_prefix: '',
               override_options: 'b_lundef=false',
	       include_directories: pyinc,
	       install: true,
	       install_dir: pyinstall_so)

shared_library('clixon_beh', 'clixon_beh.c',
               name_prefix: '',
               override_options: 'b_lundef=false',
	       include_directories: pyinc,
	       link_args: pylib,
	       install: true,
	       install_dir: my_libexecdir + '/clixon_beh')

install_data('clixon-beh-config@2024-06-05.yang',
             install_dir: my_datadir + '/clixon')

install_headers('clixon_beh.h')
