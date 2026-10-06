"""Switch Item to baseapp's naming series on sites that already have baseapp installed.

Fresh installs get this from hooks.after_install instead: install_app() calls
set_all_patches_as_completed(), so patches shipped with the app are never run on
the site that installs it.
"""

from baseapp.utils import enable_item_naming_series


def execute():
    enable_item_naming_series()
