import frappe
from frappe import _
from frappe.model.document import Document


class DynamicProductBundleOption(Document):
	def validate(self):
		self.validate_bundle_item()
		self.validate_qty()

	def validate_bundle_item(self):
		"""Option hanya boleh dibuat untuk item yang ditandai sebagai dynamic product bundle."""
		if not self.bundle_item:
			return
		if not frappe.db.get_value("Item", self.bundle_item, "is_dynamic_product_bundle"):
			frappe.throw(
				_(
					"Item {0} is not a Dynamic Product Bundle. "
					"Enable 'Is Dynamic Product Bundle' on the item first."
				).format(frappe.bold(self.bundle_item))
			)

	def validate_qty(self):
		self.min_qty = self.min_qty or 0
		self.max_qty = self.max_qty or 0
		if self.min_qty < 0 or self.max_qty < 0:
			frappe.throw(_("Min Qty and Max Qty cannot be negative."))
		if self.max_qty and self.min_qty > self.max_qty:
			frappe.throw(
				_("Min Qty ({0}) cannot be greater than Max Qty ({1}).").format(
					self.min_qty, self.max_qty
				)
			)
