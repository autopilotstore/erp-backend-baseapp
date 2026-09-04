import json
import pathlib

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def set_contact_status_open(doc, method):
    if not doc.status:
        doc.status = "Open"


def enforce_baseapp_settings():
    """Re-enforce settings on install & every migrate (idempotent, multi-site safe)."""
    if frappe.db.get_single_value("CRM Settings", "auto_creation_of_contact"):
        frappe.db.set_single_value("CRM Settings", "auto_creation_of_contact", 0)

    # Ensure Contact.status default is "Open" (make_property_setter replaces existing)
    make_property_setter("Contact", "status", "default", "Open", "Text")

    # Country: phone code & flag emoji
    ensure_country_custom_fields()
    sync_country_phone_flags()

    # Gender master: keep only Male / Female / Prefer not to say
    sync_genders()

    # Role "All": hide from role lists (safe — "All" is added to perms programmatically)
    disable_all_role()

    # Mode of Payment "Accounts Receivable": seed on every site
    sync_mode_of_payment()

    # Warehouse Type "Store": seed on every site
    sync_warehouse_type()

    # Main Bank Account "Rekening Bank Utama" (under "1120.000 - Bank"): seed on every site
    sync_main_bank_account()


def ensure_country_custom_fields():
    """Add phone_code & flag_emoji custom fields to Country (idempotent)."""
    create_custom_fields(
        {
            "Country": [
                {"fieldname": "phone_code", "label": "Phone Code", "fieldtype": "Data"},
                {"fieldname": "flag_emoji", "label": "Flag Emoji", "fieldtype": "Data"},
            ]
        }
    )


def sync_country_phone_flags():
    """Sync phone_code & flag_emoji into Country from data/country.json (by iso2)."""
    data_file = pathlib.Path(__file__).parent / "data" / "country.json"
    if not data_file.exists():
        frappe.log_error(
            f"country.json not found at {data_file}. "
            "Place the file there to sync phone_code/flag_emoji into Country.",
            "baseapp: sync_country_phone_flags",
        )
        return

    countries = json.loads(data_file.read_text(encoding="utf-8"))
    for row in countries:
        name = frappe.db.get_value("Country", {"code": row.get("iso2")}, "name")
        if name:
            frappe.db.set_value(
                "Country",
                name,
                {"phone_code": row.get("phonecode"), "flag_emoji": row.get("emoji")},
                update_modified=False,
            )


KEEP_GENDERS = ("Male", "Female", "Prefer not to say")


def sync_genders():
    """Keep only Male / Female / Prefer not to say in Gender master (idempotent)."""
    # Ensure the 3 desired genders exist (create if missing)
    for gender_name in KEEP_GENDERS:
        if not frappe.db.exists("Gender", gender_name):
            frappe.get_doc({"doctype": "Gender", "gender": gender_name}).insert(
                ignore_permissions=True
            )

    # Remove other genders, unless they are referenced by existing documents
    for name in frappe.get_all("Gender", pluck="name"):
        if name in KEEP_GENDERS:
            continue
        try:
            frappe.delete_doc("Gender", name, ignore_permissions=True)
        except frappe.exceptions.LinkExistsError:
            pass


def disable_all_role():
    """Disable the 'All' role so it doesn't appear in role lists (idempotent)."""
    if frappe.db.exists("Role", "All"):
        frappe.db.set_value("Role", "All", "disabled", 1)


def sync_mode_of_payment():
    """Seed an "Accounts Receivable" Mode of Payment on every site (idempotent)."""
    mode = "Accounts Receivable"
    receivable_account_name = "1131.0010 - Piutang Dagang"

    if not frappe.db.exists("Mode of Payment", mode):
        frappe.get_doc(
            {
                "doctype": "Mode of Payment",
                "mode_of_payment": mode,
                "type": "General",
                "enabled": 1,
            }
        ).insert(ignore_permissions=True)

    # Link each company's receivable account (by exact name, then by account_number)
    mop = frappe.get_doc("Mode of Payment", mode)
    existing_companies = {row.company for row in mop.accounts}
    changed = False
    for company in frappe.get_all("Company", pluck="name"):
        if company in existing_companies:
            continue
        account = frappe.db.get_value(
            "Account",
            {"company": company, "name": receivable_account_name, "is_group": 0},
            "name",
        )
        if not account:
            account = frappe.db.get_value(
                "Account",
                {"company": company, "account_number": "1131.0010", "is_group": 0},
                "name",
            )
        if account:
            mop.append("accounts", {"company": company, "default_account": account})
            changed = True
    if changed:
        mop.save(ignore_permissions=True)


def sync_warehouse_type():
    """Seed a "Store" Warehouse Type on every site (idempotent)."""
    if not frappe.db.exists("Warehouse Type", "Store"):
        frappe.get_doc(
            {"doctype": "Warehouse Type", "name": "Store", "description": "Store"}
        ).insert(ignore_permissions=True)


MAIN_BANK_ACCOUNT = {
    "account_number": "1120.001",
    "account_name": "Rekening Bank Utama",
    "is_group": 0,
    "account_type": "Bank",
    "root_type": "Asset",
    "report_type": "Balance Sheet",
}


def sync_main_bank_account():
    """Seed a "Rekening Bank Utama" ledger under "1120.000 - Bank" per company.

    Idempotent & multi-site safe: skips companies that already have the account
    (matched by account_name + is_group=0), and only creates it when the parent
    account "1120.000 - Bank" already exists in that company's COA.
    """
    for company in frappe.get_all("Company", pluck="name"):
        if frappe.db.exists(
            "Account",
            {
                "company": company,
                "account_name": MAIN_BANK_ACCOUNT["account_name"],
                "is_group": 0,
            },
        ):
            continue

        parent = frappe.db.get_value(
            "Account",
            {"company": company, "account_number": "1120.000", "is_group": 1},
            "name",
        )
        if not parent:
            # Parent "1120.000 - Bank" not present yet (e.g. COA not loaded for
            # this company) — skip creation as per requirements.
            frappe.log_error(
                f"Parent '1120.000 - Bank' not found for company {company}; "
                "skipping creation of 'Rekening Bank Utama'.",
                "baseapp: sync_main_bank_account",
            )
            continue

        try:
            frappe.get_doc(
                {
                    "doctype": "Account",
                    **MAIN_BANK_ACCOUNT,
                    "company": company,
                    "parent_account": parent,
                    "account_currency": frappe.get_cached_value(
                        "Company", company, "default_currency"
                    ),
                }
            ).insert(ignore_permissions=True)
        except Exception:
            # e.g. root/child company COA restrictions — log and move on so a
            # single company never aborts app install/migrate.
            frappe.log_error(
                frappe.get_traceback(), f"baseapp: sync_main_bank_account ({company})"
            )