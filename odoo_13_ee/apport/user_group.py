# Copyright (C) 2023 Canonical Ltd.
# Author: Benjamin Drung <benjamin.drung@canonical.com>
# SPDX-License-Identifier: GPL-2.0-or-later

"""Functions around users and groups."""

import os


class UserGroupID:
    """Pair of user and group ID."""

    def __init__(self, uid, gid):
        self.uid = uid
        self.gid = gid

    def is_root(self):
        """Check if the user or group ID is root."""
        return self.uid == 0 or self.gid == 0


def get_process_user_and_group():
    """Return the current process's real user and group."""
    return UserGroupID(os.getuid(), os.getgid())
