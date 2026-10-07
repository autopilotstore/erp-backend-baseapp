"""Set the password policy on sites that already have baseapp installed.

Fresh installs get this from hooks.after_install instead: install_app() calls
set_all_patches_as_completed(), so patches shipped with the app are never run on
the site that installs it.
"""

from baseapp.utils import set_minimum_password_score


def execute():
    set_minimum_password_score()
