from dataclasses import dataclass
import os
import pwd
import grp

#Server Side

@dataclass
class UnixUser:
    uid = os.getuid() #PK
    user_info = pwd.getpwuid(uid)

    username = user_info.pw_name
    gid = user_info.pw_gid

    groups = None 

    def setGroups(self):
        self.groups = [g.gr_name for g in grp.getgrall() if self.username in g.gr_mem]
