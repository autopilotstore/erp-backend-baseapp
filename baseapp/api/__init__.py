"""Whitelisted REST endpoints owned by baseapp.

Re-exported here so the public path stays short
(``/api/method/baseapp.api.<name>``) instead of leaking the module layout.

``@frappe.whitelist()`` marks the **function object** itself
(``frappe.whitelist.add(fn)``, frappe/__init__.py:471) and ``is_whitelisted()``
tests membership of that set — so a re-exported name is recognised just fine.
"""

from baseapp.api.item_name import check_item_name

__all__ = ["check_item_name"]
