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

project('pyhello-clixon-backend-helper', 'c')

appname = 'pyhello_beh'

prefix = get_option('prefix')
if get_option('prefix') == '/usr'
   my_sysconfdir = get_option('sysconfdir')
else
   my_sysconfdir = prefix + '/' + get_option('sysconfdir')
endif
my_localstatedir = get_option('localstatedir')
my_libexecdir = prefix + '/' + get_option('libexecdir')
my_datadir = prefix + '/' + get_option('datadir')
my_libdir = prefix + '/' + get_option('libdir')

conf_data = configuration_data()
conf_data.set('SYSCONFDIR', my_sysconfdir)
conf_data.set('DATADIR', my_datadir)
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

install_data('clixon-pyhello-beh@2024-05-25.yang',
             install_dir: my_datadir + '/clixon/' + appname)

install_data('startup_db',
             install_dir: my_localstatedir + '/' + appname)

install_data('pyhello.py',
	     install_dir: my_libexecdir + '/' + appname)

