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

import clixon_beh

MY_NAMESPACE = "http://mvista.com/chronyd"

class Handler:
    def exit(self):
        self.p = None # Break circular dependency
        return 0;

    def begin(self, t):
        # Do any beginning stuff here.
        return 0

    def validate(self, t):
        print("Validate:")
        print("  orig: " + t.orig_str())
        print("  new: " + t.new_xml().to_str())
        return 0

    def commit(self, t):
        print("Commit: " + t.new_str())
        return 0

    def commit_done(self, t):
        print("Commit Done: " + t.new_str())
        return 0

    def revert(self, t):
        print("Revert: " + t.orig_str())
        return 0

    # At completion, remove the backup file.
    def end(self, t):
        print("End:")
        return 0

    # If we failed, revert the server file from the backup.
    def abort(self, t):
        print("Abort:")
        return 0

    def statedata(self, nsc, xpath):
        print("***statedata: %s %s" % (xpath, str(nsc)))
        return (0, "")

    def system_only(self, nsc, xpath):
        print("***system_only: %s %s" % (xpath, str(nsc)))
        if xpath == "/":
            # There is no state data in /statistics, so no need to fetch it.
            xpath = "/server"
            pass
        rv = self.statedata(nsc, xpath)
        print("system_only rv: " + str(rv))
        return rv

    pass

handler = Handler()
handler.p = clixon_beh.add_plugin("chronyd-server", MY_NAMESPACE, handler)
