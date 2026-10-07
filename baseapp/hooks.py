app_name = "baseapp"
app_title = "Base App"
app_publisher = "PT. Rapupa Guna Teknologi"
app_description = "Init setting + global bussiness logic"
app_email = "autopilotstore.id@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "baseapp",
# 		"logo": "/assets/baseapp/logo.png",
# 		"title": "Base App",
# 		"route": "/baseapp",
# 		"has_permission": "baseapp.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/baseapp/css/baseapp.css"
# app_include_js = "/assets/baseapp/js/baseapp.js"

# include js, css files in header of web template
# web_include_css = "/assets/baseapp/css/baseapp.css"
# web_include_js = "/assets/baseapp/js/baseapp.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "baseapp/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "baseapp/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "baseapp.utils.jinja_methods",
# 	"filters": "baseapp.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "baseapp.install.before_install"
# after_install runs when `bench install-app baseapp` is executed
# (after_migrate alone only runs on `bench migrate`, not on fresh install)
#
# collapse_item_groups, enable_item_naming_series and set_minimum_password_score are
# one-shot changes to existing master data / settings, so they are NOT part of
# after_migrate: that would wipe user created Item Groups, silently override an
# intentional Item Naming By change, or re-enable the password policy on every
# deploy. Already-installed sites get them once via baseapp.patches.*.
after_install = [
	"baseapp.utils.enforce_baseapp_settings",
	"baseapp.utils.collapse_item_groups",
	"baseapp.utils.enable_item_naming_series",
	"baseapp.utils.set_minimum_password_score",
	"baseapp.utils.backfill_item_product_bundle_flags",
]
after_migrate = "baseapp.utils.enforce_baseapp_settings"

# Uninstallation
# ------------

# before_uninstall = "baseapp.uninstall.before_uninstall"
# after_uninstall = "baseapp.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "baseapp.utils.before_app_install"
# after_app_install = "baseapp.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "baseapp.utils.before_app_uninstall"
# after_app_uninstall = "baseapp.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "baseapp.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "baseapp.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Contact": {
		"validate": "baseapp.utils.set_contact_status_open",
	},
	"Item": {
		# variants get a plain series code instead of "{template}-{abbr}"; must run
		# before set_new_name() picks the name, hence before_insert
		"before_insert": "baseapp.utils.assign_variant_item_code",
		"after_insert": "baseapp.utils.sync_standard_item_prices",
		# a new Item with no barcode of its own gets barcode = item_code
		"before_validate": "baseapp.utils.set_default_item_barcode",
		# Item Name must not collide with an ACTIVE Item (ERPNext checks nothing)
		"validate": "baseapp.utils.prevent_duplicate_item_name",
		# renaming a template renames its variants too (ERPNext keeps the stale name)
		"on_update": "baseapp.utils.sync_variant_item_names",
	},
	"Item Price": {
		"on_update": "baseapp.utils.sync_item_rate_from_standard_price",
	},
	"Price List": {
		"on_trash": "baseapp.utils.prevent_standard_price_list_deletion",
	},
	"Item Attribute": {
		# user only fills attribute_value; abbr mirrors it. before_validate, not
		# validate: the derived abbr still has to satisfy its `reqd` check, and
		# before_validate also runs on import paths that set ignore_validate.
		"before_validate": "baseapp.utils.sync_attribute_value_and_abbr",
	},
	"Product Bundle": {
		# keep Item.is_product_bundle in sync (on_update also fires on insert)
		"on_update": "baseapp.utils.sync_item_product_bundle_flag",
		"on_trash": "baseapp.utils.clear_item_product_bundle_flag",
	},
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"baseapp.tasks.all"
# 	],
# 	"daily": [
# 		"baseapp.tasks.daily"
# 	],
# 	"hourly": [
# 		"baseapp.tasks.hourly"
# 	],
# 	"weekly": [
# 		"baseapp.tasks.weekly"
# 	],
# 	"monthly": [
# 		"baseapp.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "baseapp.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Mixins to extend the standard doctype controller. The value MUST be a list of
# dotted paths (frappe/model/base_document.py resolves `reversed(extensions)`).
extend_doctype_class = {
	# Variants are coded from a naming series by utils.assign_variant_item_code().
	# ERPNext's ItemAttribute.on_update() would rename those Items back to
	# "{template}-{abbr}" whenever an Item Attribute Value's abbr is edited, so the
	# cascade is neutralised here. See overrides/item_attribute.py for the details
	# and the ERPNext upgrade caveat.
	"Item Attribute": ["baseapp.overrides.item_attribute.CustomItemAttribute"],
}

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "baseapp.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "baseapp.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["baseapp.utils.before_request"]
# after_request = ["baseapp.utils.after_request"]

# Job Events
# ----------
# before_job = ["baseapp.utils.before_job"]
# after_job = ["baseapp.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"baseapp.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []
