import frappe
from frappe import _
from frappe.model.document import Document


class DynamicProductBundleItem(Document):
	def validate(self):
		self.set_default_uom()
		self.validate_bundle_item()
		self.validate_option()
		self.validate_uom()
		self.validate_qty()
		self.validate_duplicate()

	def set_default_uom(self):
		"""UOM default = stock_uom milik item (fetch_from), jaga-jaga saat diisi via API."""
		if not self.uom and self.item:
			self.uom = frappe.db.get_value("Item", self.item, "stock_uom")

	def validate_bundle_item(self):
		if self.item and self.item == self.bundle_item:
			frappe.throw(_("An item cannot be a component of itself."))

		if self.bundle_item and not frappe.db.get_value(
			"Item", self.bundle_item, "is_dynamic_product_bundle"
		):
			frappe.throw(
				_(
					"Item {0} is not a Dynamic Product Bundle. "
					"Enable 'Is Dynamic Product Bundle' on the item first."
				).format(frappe.bold(self.bundle_item))
			)

	def validate_option(self):
		"""bundle_option kosong = komponen tetap; terisi = harus milik paket & bertipe filter Item."""
		if not self.bundle_option:
			return

		option = frappe.db.get_value(
			"Dynamic Product Bundle Option",
			self.bundle_option,
			["bundle_item", "filter_type"],
			as_dict=True,
		)
		if not option:
			frappe.throw(_("Pilihan isian {0} tidak ditemukan.").format(frappe.bold(self.bundle_option)))

		if option.bundle_item != self.bundle_item:
			frappe.throw(
				_("Pilihan isian {0} bukan milik paket {1}.").format(
					frappe.bold(self.bundle_option), frappe.bold(self.bundle_item)
				)
			)

		if option.filter_type != "Item":
			frappe.throw(
				_(
					"Pilihan isian {0} bertipe filter 'Item Group', "
					"sehingga item harus didaftarkan pada tabel Item Group."
				).format(frappe.bold(self.bundle_option))
			)

	def validate_uom(self):
		"""UOM harus salah satu UOM yang terdaftar pada item tersebut."""
		if not (self.item and self.uom):
			return

		valid_uoms = {frappe.db.get_value("Item", self.item, "stock_uom")}
		valid_uoms.update(
			frappe.get_all("UOM Conversion Detail", filters={"parent": self.item}, pluck="uom")
		)
		valid_uoms.discard(None)

		if self.uom not in valid_uoms:
			frappe.throw(
				_("UOM {0} tidak terdaftar pada item {1}.").format(
					frappe.bold(self.uom), frappe.bold(self.item)
				)
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

	def validate_duplicate(self):
		filters = {
			"bundle_item": self.bundle_item,
			"item": self.item,
			"uom": self.uom,
			"name": ["!=", self.name],
		}
		if self.bundle_option:
			filters["bundle_option"] = self.bundle_option
		else:
			filters["bundle_option"] = ["is", "not set"]

		if frappe.db.exists("Dynamic Product Bundle Item", filters):
			frappe.throw(
				_("Item {0} sudah terdaftar pada paket {1} dengan pilihan/UOM yang sama.").format(
					frappe.bold(self.item), frappe.bold(self.bundle_item)
				)
			)
