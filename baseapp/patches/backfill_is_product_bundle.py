"""Rebuild Item.is_product_bundle for Product Bundles that predate the field.

Fresh installs get the field from hooks.after_install instead: install_app() calls
set_all_patches_as_completed(), so patches shipped with the app are never run on the
site that installs it.
"""

from baseapp.utils import backfill_item_product_bundle_flags


def execute():
    backfill_item_product_bundle_flags()
