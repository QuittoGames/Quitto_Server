from dataclasses import dataclass
import os
import pwd
import grp

#Server Side

@dataclass
class UnixUser:
    uid: int
    username: str
    gid: int
    groups: list[str]
    

    @staticmethod
    def load_unix_user(uid: int | None = None) -> 'UnixUser':
        uid = uid or os.getuid()
        user = pwd.getpwuid(uid)

        groups = [
            g.gr_name
            for g in grp.getgrall()
            if user.pw_name in g.gr_mem
        ]

        return UnixUser(
            uid=uid,
            username=user.pw_name,
            gid=user.pw_gid,
            groups=groups
        )