"""Экструдор BOM — Нитка retsepti.

Miqdorlar Excel jurnalining (507 smena, 2025-06..2026-08) medianidan:
100 kg Нитка uchun: PP 95.86 + CaCO3 3.83 + Мастербач 1.26 = 100.95 kg kirim,
otxod 0.95 kg → massa balansi 100.0 kg. Bu faqat boshlang'ich avto-to'ldirish;
operator har smenada fakt sarflarni o'zi kiritadi.

    bench --site uz.politex execute uzpolitex.setup.ekstruder_bom.setup
"""

import frappe

COMPANY = "Uzpolitex Holding"
FG_ITEM = "Нитка"
BOM_QTY = 100  # kg

RAW_ITEMS = [
	("Полипропилен", 95.86),
	("Кальций Карбонат", 3.83),
	("Мастербач Краска", 1.26),
	# Вторичка BOM'ga kirmaydi: BOM'da 0 miqdor taqiqlangan (bom.py:800),
	# u ishlatilgan smenada (507 dan 8 holat) operator qatorni qo'lda qo'shadi.
]

SCRAP_ITEM = ("Экструдор отход", 0.95)


def setup():
	existing = frappe.db.get_value("BOM", {"item": FG_ITEM, "docstatus": 1})
	if existing:
		print(f"BOM allaqachon bor: {existing}")
		return existing

	bom = frappe.new_doc("BOM")
	bom.item = FG_ITEM
	bom.company = COMPANY
	bom.quantity = BOM_QTY
	bom.uom = "Kg"
	bom.rm_cost_as_per = "Valuation Rate"
	bom.is_active = 1
	bom.is_default = 1

	for item_code, qty in RAW_ITEMS:
		bom.append("items", {"item_code": item_code, "qty": qty, "uom": "Kg"})

	bom.append(
		"secondary_items",
		{
			"secondary_item_type": "Scrap",
			"item_code": SCRAP_ITEM[0],
			"qty": SCRAP_ITEM[1],
			"stock_qty": SCRAP_ITEM[1],
			"uom": "Kg",
			"stock_uom": "Kg",
			"conversion_factor": 1,
			"cost_allocation_per": 0,
			"process_loss_per": 0,
			"process_loss_qty": 0,
			"cost": 0,
			"base_cost": 0,
			"rate": 0,
		},
	)

	bom.insert(ignore_permissions=True)
	bom.submit()
	frappe.db.commit()
	print(f"BOM yaratildi va submit qilindi: {bom.name}")
	return bom.name
