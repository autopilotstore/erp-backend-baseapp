import frappe


def execute():
    """Disable auto-creation of Contact when a Lead is created.

    ERPNext creates a Contact automatically on Lead insert only when
    CRM Settings > Auto Creation of Contact is enabled (default).
    """
    frappe.db.set_single_value("CRM Settings", "auto_creation_of_contact", 0)
