"""Item Attribute controller override (app ``baseapp``).

Why this exists
---------------
Editing an ``Item Attribute Value``'s ``abbr`` makes ERPNext rebuild every affected
variant's ``item_code``::

    ItemAttribute.on_update()                          erpnext/stock/doctype/item_attribute/item_attribute.py:48
      -> update_variant_item_codes_for_abbr_renames()  erpnext/controllers/item_variant.py:199
           -> rename_variant_item_code()               erpnext/controllers/item_variant.py:219
                frappe.rename_doc("Item", variant.item_code, "{template}-{abbr}")

``rename_variant_item_code()`` feeds ``make_variant_item_code()`` a blank probe
(``{"item_code": None, ...}``), so the computed target is always
``"{template_item_code}-{abbr}"`` and its ``new_code.item_code == variant.item_code``
guard can never match.

That is precisely the scheme baseapp replaced: variants get a series code from
``baseapp.utils.assign_variant_item_code()``, and that same string is what gets printed
as the barcode. Letting the cascade run would rename the Item, desynchronise labels that
are already printed and leave the site with a mix of "2609000012" and "KAOS-M" variants.

How it is neutralised
---------------------
``on_update()`` is deliberately *not* copied verbatim. ERPNext evolves that method over
time, and a copy would silently stop inheriting those changes. Instead
``super().on_update()`` runs as-is, and only the cascade is disabled for the duration of
that call by rebinding the name ``on_update`` resolves in its own module namespace.

Scope: ``ItemAttribute.on_update`` is the only caller of
``update_variant_item_codes_for_abbr_renames()`` (erpnext:item_attribute.py:50), so
nothing else is affected. ``update_variant_attribute_values()`` -- the ``attribute_value``
rename propagation -- still runs untouched.

ERPNext upgrade note
--------------------
``bench update`` / ``bench migrate`` only replace ``apps/frappe`` and ``apps/erpnext``;
this file, ``baseapp/hooks.py`` and every other baseapp module are left alone. The real
exposure is an *internal API rename*: if ERPNext renames or drops
``update_variant_item_codes_for_abbr_renames``, the lookup below returns ``None`` and this
override becomes inert -- i.e. ERPNext's own behaviour returns and the abbr cascade is
back (silently, as this override raises nothing). Keep a regression check for that; see
the manual check documented next to ``assign_variant_item_code``.
"""

import sys

import frappe
from erpnext.stock.doctype.item_attribute.item_attribute import ItemAttribute

_ITEM_ATTRIBUTE_MODULE = "erpnext.stock.doctype.item_attribute.item_attribute"
_ABBR_CASCADE = "update_variant_item_codes_for_abbr_renames"


class CustomItemAttribute(ItemAttribute):
	def on_update(self):
		"""Run ERPNext's Item Attribute ``on_update`` without the abbr->item_code cascade."""
		module = sys.modules.get(_ITEM_ATTRIBUTE_MODULE)
		cascade = getattr(module, _ABBR_CASCADE, None) if module else None

		if cascade is None:
			# ERPNext renamed or removed the cascade: there is nothing to skip. Fall
			# through so a future ``on_update`` implementation is still inherited.
			super().on_update()
			return

		def _skip_abbr_cascade(item_attribute):
			frappe.logger("baseapp").debug(
				"Skipped ERPNext abbr->item_code variant rename for Item Attribute %s",
				item_attribute.name,
			)

		setattr(module, _ABBR_CASCADE, _skip_abbr_cascade)
		try:
			super().on_update()
		finally:
			setattr(module, _ABBR_CASCADE, cascade)
