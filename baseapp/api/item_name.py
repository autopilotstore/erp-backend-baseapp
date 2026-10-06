"""Item Name endpoints.

ERPNext enforces nothing on Item Name — ``item.json`` marks only ``item_code``
unique, ``Item.validate()`` never looks at duplicates and ``item.js`` has no client
side check either. baseapp adds the two halves of the rule:

* server side, ``baseapp.utils.prevent_duplicate_item_name`` (doc_event on
  ``Item.validate``) refuses a name already held by an **active** Item;
* this endpoint, so the UI can act *before* saving — including the case the server
  deliberately allows, where the name is only held by **disabled** Items.
"""

import frappe

from baseapp.utils import item_name_matches, normalize_item_name


@frappe.whitelist()
def check_item_name(item_name, exclude=None):
    """Pre-check an Item Name before CREATE/UPDATE so the UI can branch.

    Returns both buckets, because the frontend needs them for different things:

    * ``duplicate_active``   — an active Item already holds the name. Saving will
      be rejected server side, so ask the user for a different name.
    * ``duplicate_inactive`` — only disabled Items hold it. Saving is allowed;
      offer to reactivate the old Item instead (``frappe.client.set_value`` with
      ``{"disabled": 0}``) rather than creating a duplicate.
    * ``ok``                 — the name is free.

    Matching is case insensitive and ignores surrounding space (router-invariant:
    the same normalisation the server side validator applies).

    :param item_name: the name to check.
    :param exclude: ``name`` of the Item being edited, so an UPDATE does not match
        itself. Omit it when creating.
    """
    frappe.has_permission("Item", "read", throw=True)

    matches = item_name_matches(item_name, exclude)

    if matches["active"]:
        status = "duplicate_active"
    elif matches["inactive"]:
        status = "duplicate_inactive"
    else:
        status = "ok"

    return {
        "item_name": item_name,
        "normalized": normalize_item_name(item_name),
        "status": status,
        "active": matches["active"],
        "inactive": matches["inactive"],
    }
