import frappe
from frappe.tests.utils import FrappeTestCase


class TestItemPriceSync(FrappeTestCase):
	def test_item_with_both_rates_creates_one_standard_price_per_list(self):
		for price_list in ("Standard Selling", "Standard Buying"):
			self.assertTrue(
				frappe.db.get_value("Price List", {"name": price_list, "enabled": 1}),
				f"{price_list} must exist and be enabled",
			)

		item_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name")
		item_code = f"_Test Item Price Sync {frappe.generate_hash(length=8)}"
		item = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": item_code,
				"item_name": item_code,
				"item_group": item_group,
				"stock_uom": "Nos",
				"is_stock_item": 1,
				"is_sales_item": 1,
				"is_purchase_item": 1,
				"valuation_rate": 7000,
				"standard_rate": 7100,
			}
		).insert()

		for price_list, expected_rate in (("Standard Selling", 7100), ("Standard Buying", 7000)):
			prices = frappe.get_all(
				"Item Price",
				filters={"item_code": item.name, "price_list": price_list},
				fields=["price_list_rate", "uom"],
			)
			self.assertEqual(len(prices), 1)
			self.assertEqual(prices[0].price_list_rate, expected_rate)
			self.assertEqual(prices[0].uom, item.stock_uom)
