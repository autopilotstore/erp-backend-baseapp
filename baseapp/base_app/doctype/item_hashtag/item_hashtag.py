"""Child table of Item — one row per hashtag.

No validation lives here on purpose. The rules need to look at the sibling rows of the
same parent (duplicates) and should report which row is wrong, so they run in the parent
hook `baseapp.utils.normalize_item_hashtags()` instead.
"""

from frappe.model.document import Document


class ItemHashtag(Document):
	pass
