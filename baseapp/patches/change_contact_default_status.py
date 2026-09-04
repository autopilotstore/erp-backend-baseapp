from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def execute():
    make_property_setter("Contact", "status", "default", "Open", "Text")
