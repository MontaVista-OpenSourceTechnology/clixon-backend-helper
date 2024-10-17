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
	      'ietf-ip@2018-02-22.yang',
	      'mv-ip@2024-10-17.yang'],
             install_dir: my_datadir + '/clixon/' + appname)

install_data('startup_db',
             install_dir: my_localstatedir + '/' + appname)

install_data('ietf-ip.py',
	     install_dir: my_libexecdir + '/' + appname)

