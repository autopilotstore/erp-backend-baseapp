"""Create the Hashtag master rows that Item.hashtags already refers to.

`Item Hashtag.hashtag` became a Link to the new `Hashtag` master, so every value that
already sits in `tabItem Hashtag` needs a master row — otherwise the link is broken and
the Item can no longer be saved until that row is removed.

Idempotent: `Hashtag` is autonamed from the value itself (name = hashtag), so values
that already have a master row are skipped. Registered as
baseapp.patches.backfill_hashtag_master.
"""

import frappe


def execute():
	if not frappe.db.exists("DocType", "Hashtag"):
		return

	if not frappe.db.exists("DocType", "Item Hashtag"):
		return

	values = frappe.db.sql(
		"""select distinct hashtag from `tabItem Hashtag`
		where ifnull(hashtag, '') != '' order by hashtag asc""",
		pluck=True,
	)

	for value in values:
		value = (value or "").strip().lower()
		if not value or frappe.db.exists("Hashtag", value):
			continue

		frappe.get_doc({"doctype": "Hashtag", "hashtag": value}).insert(ignore_permissions=True)
