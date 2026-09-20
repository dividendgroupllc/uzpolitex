"""Ishlab chiqarish rollari va huquqlari.

- Оператор производства: Stock Entry yaratadi/yozadi, submit qilolmaydi
- Начальник цеха: submit/cancel/amend ham qiladi (smena tasdig'i)

Idempotent — qayta ishga tushirish xavfsiz:
    bench --site uz.politex execute uzpolitex.setup.roles.setup
"""

import frappe
from frappe.permissions import add_permission, update_permission_property

OPERATOR = "Оператор производства"
NACHALNIK = "Начальник цеха"

# doctype -> {role: qo'shimcha huquqlar (read har doim beriladi)}
GRANTS = {
	"Stock Entry": {
		OPERATOR: ["write", "create"],
		NACHALNIK: ["write", "create", "submit", "cancel", "amend"],
	},
	# Link maydonlar ishlashi uchun o'qish huquqi
	"Item": {OPERATOR: [], NACHALNIK: []},
	"Warehouse": {OPERATOR: [], NACHALNIK: []},
	"Workstation": {OPERATOR: [], NACHALNIK: []},
	"BOM": {OPERATOR: [], NACHALNIK: []},
	"Employee": {OPERATOR: [], NACHALNIK: []},
}


def setup():
	for role in (OPERATOR, NACHALNIK):
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
				ignore_permissions=True
			)
			print(f"Role yaratildi: {role}")

	for doctype, roles in GRANTS.items():
		for role, ptypes in roles.items():
			add_permission(doctype, role, permlevel=0)
			for pt in ptypes:
				update_permission_property(doctype, role, 0, pt, 1)
			print(f"OK: {doctype} <- {role} (read+{ptypes})")

	frappe.db.commit()
