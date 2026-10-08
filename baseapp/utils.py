import json
import pathlib

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.model.naming import make_autoname
from frappe.utils import flt, getdate, nowdate


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

    # Sales Taxes and Charges: custom_rates (JSON array of rates)
    ensure_sales_taxes_custom_fields()

    # Item: is_dynamic_product_bundle flag
    ensure_dynamic_product_bundle_custom_fields()

    # Item: is_product_bundle flag (derived from the Product Bundle master)
    ensure_product_bundle_custom_fields()

    # Item: sales quantity limits and multiples
    ensure_item_sales_quantity_custom_fields()

    # Gender master: keep only Male / Female / Prefer not to say
    sync_genders()

    # Role "All": hide from role lists (safe — "All" is added to perms programmatically)
    disable_all_role()

    # Warehouse Type "Store": seed on every site
    sync_warehouse_type()

    # Main Bank Account "Rekening Bank Utama" (under "1120.000 - Bank"): seed on every site
    sync_main_bank_account()

    # Piutang Payment Gateway (under "1132.000 - Piutang Lain lain"): seed on every site
    sync_payment_gateway_account()

    # Item Reorder: max stock threshold per (item, warehouse) — informational only
    ensure_item_reorder_custom_fields()

    # Item Attribute Value: the Desk grid only exposes attribute_value; abbr is derived
    # and mirrored by sync_attribute_value_and_abbr(). Clearing `reqd` is what lets the
    # form save at all (the client-side check runs before the server hook), and `hidden`
    # keeps the derived column out of the way.
    make_property_setter("Item Attribute Value", "abbr", "reqd", 0, "Check")
    make_property_setter("Item Attribute Value", "abbr", "hidden", 1, "Check")


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


def ensure_sales_taxes_custom_fields():
    """Add custom_rates to the Sales Taxes and Charges child table (idempotent).

    Fieldtype is JSON, which in Frappe only accepts a JSON-encoded *string* — a
    raw list is rejected ("Value for ... cannot be a list"). So the REST payload
    on each `taxes` row must be: "custom_rates": "[5, 10, 15]".
    On read the value comes back as a string, so the frontend must JSON.parse it.
    """
    create_custom_fields(
        {
            "Sales Taxes and Charges": [
                {
                    "fieldname": "custom_rates",
                    "label": "Rates",
                    "fieldtype": "JSON",
                    "insert_after": "rate",
                    "description": 'JSON array of alternative rates as text, e.g. "[5, 10, 15]"',
                }
            ]
        }
    )


def ensure_dynamic_product_bundle_custom_fields():
    """Add the is_dynamic_product_bundle flag to Item (idempotent).

    Bundle structure (options / allowed items / allowed item groups) lives in the
    standalone doctypes Dynamic Product Bundle Option / Item / Item Group.
    """
    create_custom_fields(
        {
            "Item": [
                {
                    "fieldname": "is_dynamic_product_bundle",
                    "label": "Is Dynamic Product Bundle",
                    "fieldtype": "Check",
                    "default": "0",
                    "insert_after": "is_stock_item",
                    "in_standard_filter": 1,
                    "description": (
                        "Paket yang komponen isinya dipilih dinamis oleh kasir saat transaksi. "
                        "Struktur pilihan diatur di Dynamic Product Bundle Option / Item / Item Group."
                    ),
                }
            ]
        }
    )


def ensure_item_reorder_custom_fields():
    """Add max_stock_level to Item Reorder child (per item + warehouse).

    Informational / notification only — the field does NOT trigger any stock
    logic in ERPNext. Idempotent; safe to run on install & every migrate.
    """
    create_custom_fields(
        {
            "Item Reorder": [
                {
                    "fieldname": "max_stock_level",
                    "label": "Max Stock Level",
                    "fieldtype": "Float",
                    "non_negative": 1,
                    "insert_after": "material_request_type",
                }
            ]
        }
    )


def ensure_item_sales_quantity_custom_fields():
    """Add sales quantity limits to Item (idempotent)."""
    create_custom_fields(
        {
            "Item": [
                {
                    "fieldname": "min_sales_qty",
                    "label": "Minimum Sales Qty",
                    "fieldtype": "Float",
                    "default": "0.00",
                    "non_negative": 1,
                    "depends_on": "eval: doc.is_sales_item",
                    "insert_after": "sales_uom",
                    "description": "Minimum sales quantity in Stock UOM; 0 means no minimum.",
                },
                {
                    "fieldname": "max_sales_qty",
                    "label": "Maximum Sales Qty",
                    "fieldtype": "Float",
                    "default": "0.00",
                    "non_negative": 1,
                    "depends_on": "eval: doc.is_sales_item",
                    "insert_after": "min_sales_qty",
                    "description": "Maximum sales quantity in Stock UOM; 0 means no maximum.",
                },
                {
                    "fieldname": "sales_qty_multiple",
                    "label": "Sales Qty Multiple",
                    "fieldtype": "Float",
                    "default": "0.00",
                    "non_negative": 1,
                    "depends_on": "eval: doc.is_sales_item",
                    "insert_after": "max_sales_qty",
                    "description": "Required sales quantity multiple in Stock UOM; 0 disables this limit.",
                },
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


def _seed_account(
    company,
    *,
    account_number,
    account_name,
    parent_number,
    account_type=None,
    root_type="Asset",
    report_type="Balance Sheet",
):
    """Create a ledger Account under a numbered group parent (per company).

    Idempotent & multi-site safe: skips when an account with the same
    account_name + is_group=0 already exists for that company, and only creates
    it when the parent group account (matched by account_number + is_group=1)
    exists in the company's COA. Returns the new account name or None when
    skipped / failed (failure is logged, never raised).
    """
    if frappe.db.exists(
        "Account", {"company": company, "account_name": account_name, "is_group": 0}
    ):
        return None

    parent = frappe.db.get_value(
        "Account", {"company": company, "account_number": parent_number, "is_group": 1}, "name"
    )
    if not parent:
        frappe.log_error(
            f"Parent account number '{parent_number}' not found for company {company}; "
            f"skipping creation of '{account_name}'.",
            "baseapp: _seed_account",
        )
        return None

    doc = {
        "doctype": "Account",
        "account_number": account_number,
        "account_name": account_name,
        "is_group": 0,
        "root_type": root_type,
        "report_type": report_type,
        "company": company,
        "parent_account": parent,
        "account_currency": frappe.get_cached_value("Company", company, "default_currency"),
    }
    if account_type:
        doc["account_type"] = account_type

    try:
        return frappe.get_doc(doc).insert(ignore_permissions=True).name
    except Exception:
        # e.g. root/child company COA restrictions — log and move on so a single
        # company never aborts app install/migrate.
        frappe.log_error(frappe.get_traceback(), f"baseapp: _seed_account ({company})")
        return None


def sync_main_bank_account():
    """Seed a "Rekening Bank Utama" ledger under "1120.000 - Bank" per company (idempotent)."""
    for company in frappe.get_all("Company", pluck="name"):
        _seed_account(
            company,
            account_number=MAIN_BANK_ACCOUNT["account_number"],
            account_name=MAIN_BANK_ACCOUNT["account_name"],
            parent_number="1120.000",
            account_type=MAIN_BANK_ACCOUNT["account_type"],
        )


def sync_payment_gateway_account():
    """Seed a "Piutang Payment Gateway" ledger under "1132.000 - Piutang Lain lain" per company.

    account_type deliberately left empty (generic ledger), as decided by the user.
    """
    for company in frappe.get_all("Company", pluck="name"):
        _seed_account(
            company,
            account_number="1132.002",
            account_name="Piutang Payment Gateway",
            parent_number="1132.000",
        )


ITEM_GROUP_ROOT = "All Item Groups"
DEFAULT_ITEM_GROUP = "Non Category"


def collapse_item_groups():
    """Collapse the Item Group master to "All Item Groups" + "Non Category".

    Destructive and meant to run exactly once: every other Item Group is deleted --
    the ERPNext seeded ones ("Default", "Products", "Raw Material", "Services",
    "Sub Assemblies", "Consumable") *and* any group created by the user. Items,
    already saved documents and the Stock Settings default are repointed to
    "Non Category" (is_group = 0, so it stays selectable on Item).

    Deliberately NOT called from enforce_baseapp_settings(): that hook runs on
    every `bench migrate`, which would keep wiping Item Groups created after
    go-live. It is registered in hooks.after_install (fresh installs) and as
    baseapp.patches.collapse_item_groups (sites that already have the app, whose
    install already marked every existing patch as completed).
    """
    if not frappe.db.exists("DocType", "Item Group"):
        # baseapp is normally installed after erpnext; stay safe on a bare bench
        return

    if not frappe.db.exists("Item Group", ITEM_GROUP_ROOT):
        frappe.get_doc(
            {"doctype": "Item Group", "item_group_name": ITEM_GROUP_ROOT, "is_group": 1}
        ).insert(ignore_permissions=True)

    if not frappe.db.exists("Item Group", DEFAULT_ITEM_GROUP):
        frappe.get_doc(
            {
                "doctype": "Item Group",
                "item_group_name": DEFAULT_ITEM_GROUP,
                "parent_item_group": ITEM_GROUP_ROOT,
                "is_group": 0,
            }
        ).insert(ignore_permissions=True)

    # 1. every stored pointer to a group -- Item, transaction rows, already saved
    #    documents, configuration tables -- moves to the single leaf group
    for row in _item_group_columns():
        _repoint_item_group(row.table_name, row.column_name)

    # 2. default used when creating new items
    if frappe.db.exists("DocType", "Stock Settings"):
        frappe.db.set_single_value("Stock Settings", "item_group", DEFAULT_ITEM_GROUP)

    # 3. drop every other group, deepest first (on_trash refuses a non-empty group)
    for name in frappe.get_all(
        "Item Group",
        filters={"name": ("not in", [ITEM_GROUP_ROOT, DEFAULT_ITEM_GROUP])},
        pluck="name",
        order_by="lft desc",
    ):
        frappe.delete_doc("Item Group", name, force=True, ignore_permissions=True)

    frappe.clear_cache()


def _item_group_columns():
    """Every (table, column) in this site's DB that stores an Item Group.

    Read from the schema instead of a hardcoded doctype list: being off by one
    table (e.g. "Stock Entry Detail", which also denormalises item_group) silently
    leaves broken links behind. "other_item_group" (Pricing Rule / Promotional
    Scheme) is a separate filter field with the same semantics.
    """
    return frappe.db.sql(
        """select table_name, column_name
        from information_schema.columns
        where table_schema = database()
            and table_name like %s
            and column_name in ('item_group', 'other_item_group')""",
        ("tab%",),
        as_dict=True,
    )


def _repoint_item_group(table, column):
    """Point every stored value of `column` at DEFAULT_ITEM_GROUP.

    Raw UPDATE on purpose: these are denormalised/historical columns, so we want
    no validation, no set_value overhead, untouched "modified" timestamps, and a
    NULL-safe comparison. Both identifiers come from information_schema, with
    `table` already restricted to the tab* doctype tables.
    """
    frappe.db.sql(
        f"update `{table}` set `{column}` = %s where ifnull(`{column}`, '') != %s",
        (DEFAULT_ITEM_GROUP, DEFAULT_ITEM_GROUP),
    )


def sync_attribute_value_and_abbr(doc, method=None):
    """Hook: Item Attribute.before_validate — user only fills the attribute value.

    `abbr` ends up identical to `attribute_value`. It is kept only because
    make_variant_item_code() still reads it to build a variant's item_name
    ("{template_item_name}-{abbr}"); item_code is unaffected because variants get a
    series code from assign_variant_item_code(). The Desk grid hides the column and no
    longer requires it (see enforce_baseapp_settings).

    before_validate, not validate, on purpose — frappe/model/document.py:

        1389  run_before_save_methods()
        1403      run_method("before_validate")   <- here
        1405      if flags.ignore_validate: return
        1409      run_method("validate")
         826  _validate_mandatory()              <- inside _validate(), later

    A value filled here therefore still satisfies Item Attribute Value.abbr's `reqd`
    check, and also survives import paths that set ignore_validate.
    """
    if doc.numeric_values:
        return  # ERPNext clears the table for numeric attributes

    for row in doc.item_attribute_values or []:
        value = (row.attribute_value or "").strip()
        abbr = (row.abbr or "").strip()

        if not value and not abbr:
            # Either one would do; say so explicitly instead of letting
            # validate_duplication() crash on a None abbr.
            frappe.throw(
                frappe._("Row {0}: fill Attribute Value (Abbreviation is derived).").format(row.idx),
                title=frappe._("Item Attribute Value"),
            )

        # attribute_value is canonical; abbr always mirrors it.
        value = value or abbr
        row.attribute_value = value
        row.abbr = value


ITEM_NAMING_SERIES = "YY.MM.######"


def enable_item_naming_series():
    """Switch Item master to baseapp's server-side auto-numbering.

    Generated codes look like "2609000001" (YY.MM. + a 6 digit monthly counter).
    With the mode on, Item.autoname() ignores any item_code sent by the client and
    overwrites it with the generated name — except for variants, which keep an
    explicit item_code and only fall back to "{template}-{abbr}" when it is empty.

    Two ordered steps, the second being the one that actually activates the mode:

    1. replace the "options" of the Item.naming_series field — this drives both the
       Desk dropdown and get_default_naming_series().
    2. save Stock Settings: only StockSettings.validate() writes the
       __default.item_naming_by value that Item.autoname() reads, and it is also
       what calls set_by_naming_series() to create the Item property setters
       (item_code hidden + not mandatory, naming_series visible).

    One-shot on purpose: NOT part of enforce_baseapp_settings(), so a deliberate
    change made later in Desk is not reverted on every migrate. Registered in
    hooks.after_install (fresh installs) and as
    baseapp.patches.enable_item_naming_series (sites that already have the app,
    whose install already marked every shipped patch as completed).
    """
    # baseapp is normally installed after erpnext; stay safe on a bare bench
    if not frappe.db.exists("DocType", "Item"):
        return

    # 1. the Series format itself. PropertySetter.validate() clears the Item meta
    #    cache, so the new options are picked up immediately.
    make_property_setter("Item", "naming_series", "options", ITEM_NAMING_SERIES, "Text")

    # 2. flip the mode. save() — not set_value/db.set_single_value — because only
    #    validate() writes the __default that Item.autoname() reads.
    stock_settings = frappe.get_single("Stock Settings")
    if stock_settings.item_naming_by != "Naming Series":
        stock_settings.item_naming_by = "Naming Series"
        stock_settings.save()


MINIMUM_PASSWORD_SCORE = 1


def set_minimum_password_score():
    """Turn the password policy on and set its minimum score.

    The score is only ever *read* while the policy is on: User.test_password_strength()
    returns {} straight away when enable_password_policy is falsy
    (frappe/core/doctype/user/user.py:995-998). And SystemSettings.validate() blanks the
    score on every save while the policy is off
    (frappe/core/doctype/system_settings/system_settings.py:122-127) — including writes
    coming through the API, because frappe.client.save/set_value both run validate().
    Writing the score on its own would therefore be both inert and short lived, so the
    policy is enabled together with it.

    frappe.db.set_single_value() writes tabSingles directly and skips validate(). That is
    safe here: the pair written below would pass validate() anyway (policy on + score > 0).

    One-shot on purpose: NOT part of enforce_baseapp_settings(), so a later, deliberate
    change to the policy is not reverted on every migrate. Registered in
    hooks.after_install (fresh installs) and as
    baseapp.patches.set_minimum_password_score (sites that already have the app, whose
    install already marked every shipped patch as completed).
    """
    # baseapp is normally installed after frappe; stay safe on a bare bench
    if not frappe.db.exists("DocType", "System Settings"):
        return

    frappe.db.set_single_value("System Settings", "enable_password_policy", 1)
    frappe.db.set_single_value("System Settings", "minimum_password_score", MINIMUM_PASSWORD_SCORE)

    # set_single_value() already clears the document cache, but System Settings is also
    # cached in Redis (the "system_settings" key and client_cache); flush so the policy is
    # live without waiting for a bench restart.
    frappe.clear_cache()


def assign_variant_item_code(doc, method=None):
    """Give a variant a plain series code instead of "{template}-{abbr}".

    Without this, Item.autoname() -> make_variant_item_code() codes a variant
    "{template_item_code}-{abbr}" (erpnext/controllers/item_variant.py:524), whose
    width depends on the length of Item Attribute Value.abbr *and* on how many
    attributes the template carries. The code doubles as the printed barcode, so
    a variable width eats module width on a fixed-size label.

    before_insert runs *before* set_new_name() (frappe/model/document.py:468 vs
    479), and Item.autoname() only derives a variant code when item_code is empty
    -- so filling item_code here is what makes the override stick.

    The series key is the same one non-variants use ("YY.MM.######.#####" still
    counts in 6 digits, the trailing ".#####" is skipped because series_set is
    already True), so plain items, templates and variants all draw from one
    monthly counter and can never collide.
    """
    if not doc.get("variant_of"):
        return

    doc.item_code = make_autoname(f"{ITEM_NAMING_SERIES}.#####")

    # create_variant() has already set the readable "{template_item_name}-{abbr}"
    # name; a manual insert has not, and Item.validate() would then fall back to
    # item_name = item_code -- i.e. a product literally called "2609000012".
    if not doc.item_name:
        from erpnext.controllers.item_variant import make_variant_item_code

        template = frappe.get_cached_doc("Item", doc.variant_of)
        probe = frappe._dict({"item_code": None, "item_name": None, "attributes": doc.attributes})
        make_variant_item_code(template.item_code, template.item_name, probe)
        doc.item_name = probe.item_name


def rebuild_variant_item_name(variant, template=None):
    """Recompute a variant's item_name from its template — item_code is left alone.

    Reuses ERPNext's own make_variant_item_code() rather than formatting the string
    here, so the result is byte identical to what a freshly created variant gets
    (same "-" separator, same numeric-attribute fallback).

    Only the name is returned. item_code is deliberately untouched: it is the series
    code that doubles as the printed barcode, so recomputing it would break both.
    """
    from erpnext.controllers.item_variant import make_variant_item_code

    template = template or frappe.get_cached_doc("Item", variant.variant_of)

    probe = frappe._dict({"item_code": None, "item_name": None, "attributes": variant.attributes})
    make_variant_item_code(template.item_code, template.item_name, probe)

    return probe.item_name if probe.item_name != variant.item_name else None


def sync_variant_item_names(doc, method=None):
    """Hook: Item.on_update — renaming a template renames its variants too.

    ERPNext skips item_name on purpose when it re-saves the variants of an edited
    template: copy_attributes_to_variant() lists it in exclude_fields
    (erpnext/controllers/item_variant.py:449). Renaming "KAOS" to "T-SHIRT" therefore
    leaves every variant still called "KAOS-S". This hook closes that gap.

    Placement matters. doc_events run *after* the controller method (Document.hook,
    frappe/model/document.py:1636), so Item.on_update's own update_variants() — which
    re-saves each variant (erpnext/stock/doctype/item/item.py:826) — has already
    finished and these writes are the last word. From validate/before_save they would
    simply be overwritten.

    Item Variant Settings > "Do not update variants on save" is deliberately ignored:
    that setting governs copying template *fields* onto variants, not naming. Remove
    the hook from hooks.py to switch the cascade off.

    Only renames cascade — existing variants are never repaired, and a template that
    is not renamed never touches its variants. Runs synchronously (unlike ERPNext's
    update_variants, which enqueues above 30 variants); a template with a very large
    number of variants would need the same enqueue treatment.
    """
    if not doc.get("has_variants") or not doc.item_name:
        return

    # never fan out from app/site setup — patches and fixtures create Items freely
    if frappe.flags.in_install or frappe.flags.in_migrate or frappe.flags.in_patch:
        return

    previous = doc.get_doc_before_save()
    if not previous or previous.item_name == doc.item_name:
        return

    # Resolve everything before writing anything: one clashing name must leave the
    # whole family untouched instead of half renamed.
    renames = []
    claimed = {}
    for name in frappe.db.get_all(
        "Item", filters={"variant_of": doc.name}, pluck="name", order_by="name asc"
    ):
        variant = frappe.get_doc("Item", name)
        new_name = rebuild_variant_item_name(variant, doc)
        if not new_name:
            continue

        active = item_name_matches(new_name, exclude_name=name)["active"]
        if active:
            frappe.throw(
                frappe._(
                    "Cannot rename variant {0} to {1}: that Item Name is already used by active Item(s) {2}."
                ).format(
                    frappe.bold(name),
                    frappe.bold(new_name),
                    ", ".join(frappe.bold(row.name) for row in active[:5]),
                ),
                title=frappe._("Variant Name Clash"),
            )

        # Two variants can compute the same name — e.g. template attributes Warna and
        # Ukuran both abbreviated "M", on variants carrying only one of the two. Only a
        # NEWLY created collision blocks; twins that are already identical are left as
        # they are rather than blocking an unrelated rename.
        twin = claimed.get(new_name)
        if twin and twin[1] != variant.item_name:
            frappe.throw(
                frappe._(
                    "Variants {0} and {1} would both be renamed to {2}. Adjust the attribute value abbreviation or the template name first."
                ).format(frappe.bold(twin[0]), frappe.bold(name), frappe.bold(new_name)),
                title=frappe._("Variant Name Clash"),
            )
        claimed.setdefault(new_name, (name, variant.item_name))

        renames.append((name, new_name))

    for name, new_name in renames:
        # update_modified=False: bookkeeping, not a user edit — matches
        # _set_item_product_bundle_flag() and ERPNext's own rename_variant_item_code().
        frappe.db.set_value("Item", name, "item_name", new_name, update_modified=False)


def set_default_item_barcode(doc, method=None):
    """A new Item with no barcode of its own gets one equal to its item_code.

    Only on create (doc.is_new()) and only when the client sent no barcode at all.
    Barcodes the client did send are never second-guessed, and an existing Item is
    never repaired: update_child_table() replaces the child table wholesale, so
    re-adding a row here would quietly override a deletion the frontend asked for.

    before_validate, not validate: doc_events run *after* the controller method
    (Document.hook, frappe/model/document.py:1636), so running first means the row
    we append is still covered by Item.validate_barcode()'s global uniqueness
    check.

    barcode_type is left empty on purpose: any non-empty type makes
    validate_barcode() run barcodenumber's check digit test, which rejects
    everything that is not exactly 8/12/13 digits -- so "2609000001" would fail
    and take the whole Item insert down with it.
    """
    if not doc.is_new() or doc.get("barcodes") or not doc.item_code:
        return

    doc.append("barcodes", {"barcode": doc.item_code, "uom": doc.stock_uom})


def normalize_item_name(value):
    """Comparison key for Item Name: case insensitive, surrounding space ignored."""
    return (value or "").strip().lower()


def item_name_matches(item_name, exclude_name=None):
    """Items whose item_name matches `item_name`, split by whether they are active.

    Equality leans on the column collation (Frappe builds tables with
    utf8mb4_unicode_ci, which is case insensitive) so the index on item_name still
    applies. The Python re-check keeps the rule explicit instead of inherited from
    the schema. `exclude_name` is the Item being saved, so an UPDATE never matches
    itself.
    """
    normalized = normalize_item_name(item_name)
    if not normalized:
        return {"active": [], "inactive": []}

    rows = frappe.db.get_all(
        "Item",
        filters=[["item_name", "=", normalized], ["name", "!=", exclude_name or ""]],
        fields=["name", "item_name", "disabled"],
        order_by="disabled asc, name asc",
        limit=50,
    )
    rows = [row for row in rows if normalize_item_name(row.item_name) == normalized]

    return {
        "active": [row for row in rows if not row.disabled],
        "inactive": [row for row in rows if row.disabled],
    }


def prevent_duplicate_item_name(doc, method=None):
    """Hook: Item.validate — refuse an Item Name already held by an ACTIVE Item.

    ERPNext ships no check at all here: item.json marks only item_code unique,
    Item.validate() never looks at duplicates, and item.js has no client side check
    either — so two Items may share a name freely. That hurts because item_name is
    Item.title_field (used for document titles and notifications) and is the only
    human readable handle left, now that item_code is an opaque series number.

    Only ACTIVE duplicates block. A name held solely by disabled Items stays
    usable: the frontend pre-checks with baseapp.api.check_item_name and asks the
    user whether to reactivate the old Item instead of creating a new one.
    """
    # never fight app/site setup — fixtures and patches legitimately create Items
    if frappe.flags.in_install or frappe.flags.in_migrate or frappe.flags.in_patch:
        return

    if not doc.item_name:
        return

    active = item_name_matches(doc.item_name, doc.name)["active"]
    if not active:
        return

    frappe.throw(
        frappe._("Item Name {0} is already used by active Item(s) {1}.").format(
            frappe.bold(doc.item_name), ", ".join(frappe.bold(row.name) for row in active[:5])
        ),
        title=frappe._("Duplicate Item Name"),
    )


PRODUCT_BUNDLE_ITEM_FLAG = "is_product_bundle"


def ensure_product_bundle_custom_fields():
    """Add the is_product_bundle flag to Item (idempotent).

    Mirrors is_dynamic_product_bundle, but unlike that one this is *derived*: baseapp
    maintains it from the Product Bundle master (sync_item_product_bundle_flag),
    because ERPNext keeps no trace of a bundle on the Item itself. Read-only in the
    form so nobody edits it by hand.
    """
    create_custom_fields(
        {
            "Item": [
                {
                    "fieldname": PRODUCT_BUNDLE_ITEM_FLAG,
                    "label": "Is Product Bundle",
                    "fieldtype": "Check",
                    "default": "0",
                    "read_only": 1,
                    "no_copy": 1,
                    "insert_after": "is_dynamic_product_bundle",
                    "in_standard_filter": 1,
                    "description": (
                        "Paket statis (doctype Product Bundle): 1 = Item ini punya Product Bundle "
                        "yang AKTIF. Diisi otomatis oleh baseapp — jangan diisi manual."
                    ),
                }
            ]
        }
    )


def item_has_active_product_bundle(item_code):
    """Mirror of ERPNext's own packed_item.is_product_bundle(): only enabled bundles count.

    Deliberately queries new_item_code and not the primary key: Product Bundle is
    autonamed from new_item_code, but the field stays editable afterwards, so the two
    can drift apart. ERPNext follows new_item_code, so this has to as well.
    """
    if not item_code:
        return False

    return bool(frappe.db.exists("Product Bundle", {"new_item_code": item_code, "disabled": 0}))


def _set_item_product_bundle_flag(item_code, value):
    if not item_code or not frappe.db.exists("Item", item_code):
        return

    if frappe.db.get_value("Item", item_code, PRODUCT_BUNDLE_ITEM_FLAG) == value:
        return

    # update_modified=False: this is system bookkeeping, it should not look like a
    # user edit on the Item. frappe.db.set_value() clears the document cache itself.
    frappe.db.set_value("Item", item_code, PRODUCT_BUNDLE_ITEM_FLAG, value, update_modified=False)


def _refresh_item_product_bundle_flag(item_code):
    _set_item_product_bundle_flag(item_code, 1 if item_has_active_product_bundle(item_code) else 0)


def sync_item_product_bundle_flag(doc, method=None):
    """Hook: Product Bundle.on_update — mirror the bundle into Item.is_product_bundle.

    Why a stored flag at all: ERPNext keeps nothing on Item (item.json has no bundle
    field, product_bundle.py never writes back), and frappe.client.get_list cannot
    reach another table — its filter DSL has no subquery/join. The frontend needs
    "is this item a bundle?" as something it can filter and sort on.

    Follows ERPNext's own definition (packed_item.is_product_bundle): only an ENABLED
    Product Bundle counts, so toggling `disabled` flips the flag too.

    on_update fires for insert as well (Document.run_post_save_methods runs
    on_update whenever _action == "save", and insert uses _action="save"), so one
    hook covers create and edit.

    new_item_code is editable, so a changed value has to fix the previous item too.
    """
    previous = doc.get_doc_before_save()
    old_item_code = previous.new_item_code if previous else None

    _refresh_item_product_bundle_flag(doc.new_item_code)

    if old_item_code and old_item_code != doc.new_item_code:
        _refresh_item_product_bundle_flag(old_item_code)


def clear_item_product_bundle_flag(doc, method=None):
    """Hook: Product Bundle.on_trash — an Item has at most one Product Bundle.

    Cleared directly instead of recomputed: on_trash runs while the row is still
    there, so a re-read would keep finding the bundle being deleted. Both fields are
    cleared because new_item_code may have drifted from the primary key.
    """
    for item_code in {doc.new_item_code, doc.name}:
        _set_item_product_bundle_flag(item_code, 0)


STANDARD_ITEM_PRICE_FIELDS = {
    "Standard Selling": "valuation_rate",
    "Standard Buying": "standard_rate",
}


def prevent_standard_price_list_deletion(doc, method=None):
    """Keep the standard price lists required by Item rate synchronization."""
    if doc.name in STANDARD_ITEM_PRICE_FIELDS:
        frappe.throw(
            frappe._("{0} cannot be deleted because it is required for Item price synchronization.").format(
                frappe.bold(doc.name)
            ),
            title=frappe._("Standard Price List"),
        )


def _is_current_general_stock_uom_price(price, stock_uom, today):
    valid_from = getdate(price.valid_from) if price.valid_from else None
    valid_upto = getdate(price.valid_upto) if price.valid_upto else None

    return (
        price.uom == stock_uom
        and not price.customer
        and not price.supplier
        and not price.batch_no
        and not flt(price.packing_unit)
        and (not valid_from or valid_from <= today)
        and (not valid_upto or valid_upto >= today)
    )


def sync_standard_item_prices(doc, method=None):
    """Ensure an Item's stock UOM prices match its rates in the standard price lists."""
    today = getdate(nowdate())

    for price_list, item_field in STANDARD_ITEM_PRICE_FIELDS.items():
        rate = flt(doc.get(item_field))
        if rate < 0:
            continue

        matches = frappe.get_all(
            "Item Price",
            filters={"item_code": doc.name, "price_list": price_list, "uom": doc.stock_uom},
            fields=[
                "name",
                "uom",
                "price_list_rate",
                "valid_from",
                "valid_upto",
                "customer",
                "supplier",
                "batch_no",
                "packing_unit",
            ],
            order_by="valid_from desc, modified desc",
            limit_page_length=0,
        )
        item_price = next(
            (
                row
                for row in matches
                if _is_current_general_stock_uom_price(row, doc.stock_uom, today)
            ),
            None,
        )

        if item_price:
            if flt(item_price.price_list_rate) != rate:
                price_doc = frappe.get_doc("Item Price", item_price.name)
                price_doc.price_list_rate = rate
                price_doc.save()
        elif rate > 0:
            frappe.get_doc(
                {
                    "doctype": "Item Price",
                    "item_code": doc.name,
                    "price_list": price_list,
                    "uom": doc.stock_uom,
                    "price_list_rate": rate,
                }
            ).insert()


def sync_item_rate_from_standard_price(doc, method=None):
    """Mirror changes to a standard stock-UOM Item Price onto its Item rate field."""
    previous = doc.get_doc_before_save()
    if not previous or flt(previous.price_list_rate) == flt(doc.price_list_rate):
        return

    item_field = STANDARD_ITEM_PRICE_FIELDS.get(doc.price_list)
    if not item_field:
        return

    item = frappe.db.get_value("Item", doc.item_code, ["stock_uom", item_field], as_dict=True)
    if not item or not _is_current_general_stock_uom_price(doc, item.stock_uom, getdate(nowdate())):
        return

    rate = flt(doc.price_list_rate)
    if flt(item.get(item_field)) != rate:
        frappe.db.set_value("Item", doc.item_code, item_field, rate, update_modified=False)


def backfill_item_product_bundle_flags():
    """One-shot: rebuild Item.is_product_bundle for bundles created before the field.

    Registered in hooks.after_install and as baseapp.patches.backfill_is_product_bundle
    (sites that already have the app, whose install already marked every shipped patch
    as completed). Idempotent, so re-running is harmless.
    """
    if not (frappe.db.exists("DocType", "Item") and frappe.db.exists("DocType", "Product Bundle")):
        return

    if not frappe.db.has_column("Item", PRODUCT_BUNDLE_ITEM_FLAG):
        # the patch can run before enforce_baseapp_settings created the field
        ensure_product_bundle_custom_fields()

    # subquery reads new_item_code, matching item_has_active_product_bundle() and
    # ERPNext's own packed_item.is_product_bundle(); "is not null" keeps NOT IN safe
    active_bundles = (
        "select new_item_code from `tabProduct Bundle` "
        "where ifnull(disabled, 0) = 0 and new_item_code is not null"
    )

    frappe.db.sql(
        f"""update `tabItem` set `{PRODUCT_BUNDLE_ITEM_FLAG}` = 1
        where name in ({active_bundles}) and ifnull(`{PRODUCT_BUNDLE_ITEM_FLAG}`, 0) != 1"""
    )
    frappe.db.sql(
        f"""update `tabItem` set `{PRODUCT_BUNDLE_ITEM_FLAG}` = 0
        where name not in ({active_bundles}) and ifnull(`{PRODUCT_BUNDLE_ITEM_FLAG}`, 0) != 0"""
    )