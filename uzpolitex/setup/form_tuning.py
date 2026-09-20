"""Stock Entry formasini operatorga moslashtirish (Property Setter'lar).

Idempotent — after_migrate hookda qayta qo'llanadi (make_property_setter
mavjudini o'chirib qaytadan yaratadi).

Printsip (user 2026-09-06): takroriy/ishlatilmaydigan fieldlar yashiriladi,
yorliqlar Excel jurnalidagi atamalarga moslanadi. Narxlar KO'RINADI (user
qarori). Skladchi oqimiga (Material Transfer) tegilmaydi — Manufacture'ga
xos yashirishlar depends_on orqali.
"""

from frappe.custom.doctype.property_setter.property_setter import make_property_setter

# butunlay ishlatilmaydigan funksiyalar (Work Order/Job Card yo'q, barcode yo'q,
# process loss o'rniga BOM'dagi Scrap otxod ishlatiladi)
HIDE_ALWAYS = [
	"work_order",
	"job_card",
	"use_multi_level_bom",
	"inspection_required",
	"scan_barcode",
	"section_break_7qsm",  # Process Loss bo'limi
	"process_loss_qty",
	"process_loss_percentage",
]

# Manufacture'da kerak emas, lekin skladchi oqimlarida qoladi
NOT_MANUFACTURE = "eval:doc.purpose!='Manufacture'"
HIDE_FOR_MANUFACTURE = [
	"section_break_jwgn",  # Default Warehouse bo'limi — stanokdan avto to'ladi
]

LABELS = {
	"bom_info_section": "Продукция",
	"bom_no": "Рецепт (BOM)",
	"fg_completed_qty": "Произведено, КГ",
	"get_items": "Пересчитать материалы",
}

DESCRIPTIONS = {
	"fg_completed_qty": (
		"Сколько КГ готовой продукции за смену (графа «КГ» журнала). "
		"Материалы заполнятся автоматически по рецепту — затем исправьте их на факт."
	),
}


def apply():
	for fieldname in HIDE_ALWAYS:
		make_property_setter("Stock Entry", fieldname, "hidden", 1, "Check")

	for fieldname in HIDE_FOR_MANUFACTURE:
		make_property_setter("Stock Entry", fieldname, "depends_on", NOT_MANUFACTURE, "Code")

	# from_bom checkbox: Manufacture'da doim 1 (JS qo'yadi), ko'rsatish shart emas
	make_property_setter(
		"Stock Entry",
		"from_bom",
		"depends_on",
		'eval:in_list(["Material Issue", "Repack", "Send to Subcontractor"], doc.purpose)',
		"Code",
	)

	for fieldname, label in LABELS.items():
		make_property_setter("Stock Entry", fieldname, "label", label, "Data")

	for fieldname, description in DESCRIPTIONS.items():
		make_property_setter("Stock Entry", fieldname, "description", description, "Small Text")

	# --- Sales Order: «Қоп заказлар» асосий киритиш; стандарт items АВТО тўлади ---
	# авто-тўлган стандарт жадвал ва нарх бўлимини йиғиштириб қўямиз (ихчамлаштириш)
	make_property_setter("Sales Order", "items_section", "collapsible", 1, "Check")
	for _f in ["currency_and_price_list", "additional_discount_section",
	           "packing_list", "pricing_rule_details", "payment_schedule_section"]:
		make_property_setter("Sales Order", _f, "collapsible", 1, "Check")

	# --- Employee: link maydonlarda ID (HR-EMP-...) o'rniga F.I.O. ko'rinsin ---
	make_property_setter(
		"Employee", None, "show_title_field_in_link", 1, "Check", for_doctype=True
	)
