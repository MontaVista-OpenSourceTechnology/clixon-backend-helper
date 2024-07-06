#
# ***** BEGIN LICENSE BLOCK *****
# 
# Copyright (C) 2024 MontaVista Software, LLC <source@mvista.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Alternatively, the contents of this file may be used under the terms of
# the GNU General Public License Version 3 or later (the "GPL"),
# in which case the provisions of the GPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of the GPL, and not to allow others to
# use your version of this file under the terms of Apache License version 2, 
# indicate your decision by deleting the provisions above and replace them with
# the notice and other provisions required by the GPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the Apache License version 2 or the GPL.
#
# ***** END LICENSE BLOCK *****
#

if get_option('prefix') == '/usr'
  pyinstall = py3.get_variable('DESTLIB') + '/clixon_beh'
  pyinstall_so = py3.get_variable('DESTSHARED')
else
  pyver = py3.get_variable('py_version_short')
  pyinstall = prefix + '/lib/python' + pyver + '/dist-packages/clixon_beh'
  pyinstall_so = pyinstall
endif

incdir = include_directories('..')

swig = find_program('swig')
swig_py_gen = custom_target(
    'cclixon.py',
    input: ['cclixon.i'],
    output: ['cclixon.py', 'cclixon.c'],
    command: [swig, '-python', '-o', '@OUTPUT1@',
                '-outdir', '@OUTDIR@', '@INPUT@'],
    install: true,
    install_dir: [pyinstall, false]
)

shared_library('_cclixon', swig_py_gen[1],
               name_prefix: '',
               override_options: 'b_lundef=false',
	       include_directories: [incdir, pyinc],
	       install: true,
	       install_dir: pyinstall_so)

install_data('__init__.py',
             install_dir: pyinstall)

install_data('transaction_framework.py',
             install_dir: pyinstall)

