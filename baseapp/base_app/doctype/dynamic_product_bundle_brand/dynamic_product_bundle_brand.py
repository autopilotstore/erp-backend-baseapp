import frappe
from frappe import _
from frappe.model.document import Document


class DynamicProductBundleBrand(Document):
	def validate(self):
		self.validate_bundle_item()
		self.validate_option()
		self.validate_duplicate()

	def validate_bundle_item(self):
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
		"""Pilihan wajib milik paket yang sama dan bertipe filter Item Group.

		Brand adalah filter tambahan di dalam satu pilihan, bukan tipe filter sendiri
		(lihat Dynamic Product Bundle Option.filter_type).
		"""
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

		if option.filter_type != "Item Group":
			frappe.throw(
				_(
					"Pilihan isian {0} bertipe filter 'Item', sehingga brand tidak boleh "
					"didaftarkan di sini."
				).format(frappe.bold(self.bundle_option))
			)

	def validate_duplicate(self):
		if frappe.db.exists(
			"Dynamic Product Bundle Brand",
			{
				"bundle_option": self.bundle_option,
				"brand": self.brand,
				"name": ["!=", self.name],
			},
		):
			frappe.throw(
				_("Brand {0} sudah terdaftar pada pilihan isian {1}.").format(
					frappe.bold(self.brand), frappe.bold(self.bundle_option)
				)
			)
