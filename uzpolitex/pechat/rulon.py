"""Zakaz qopi uchun rulon tanlash va bosma rulon itemi.

- Laminat rulon: qop enidan eng yaqin standart en (35/40/45/50/55) — kichigi
  yetmasa kattaroq olinadi (rulon qopdan tor bo'lishi mumkin emas).
- Bosma rulon: har zakaz-qop uchun alohida item «<qop> Рулон Печать» —
  Печать chiqimi, Конверт rasxodi. Zakazlar skladda aralashmaydi.
"""

import frappe

STANDART_ENLAR = (35, 40, 45, 50, 55)
BOSMA_GROUP = "Полуфабрикат - Печать"


def laminat_rulon(en_cm):
    """Qop eniga mos laminat rulon itemi (topilmasa None)."""
    en = float(en_cm or 0)
    if not en:
        return None
    mos = [s for s in STANDART_ENLAR if s >= en]
    n = mos[0] if mos else STANDART_ENLAR[-1]
    nom = f"Ламинат Рулон-{n}"
    return nom if frappe.db.exists("Item", nom) else None


def bosma_rulon(qop_item):
    """Qop itemi uchun bosma rulon itemini oladi/yaratadi va qopga bog'laydi."""
    mavjud = frappe.db.get_value("Item", qop_item, "uz_bosma_rulon")
    if mavjud and frappe.db.exists("Item", mavjud):
        return mavjud
    code = f"{qop_item} Рулон Печать"
    if not frappe.db.exists("Item", code):
        it = frappe.new_doc("Item")
        it.item_code = it.item_name = code
        it.item_group = BOSMA_GROUP
        it.stock_uom = "Meter"
        it.is_stock_item = 1
        it.is_sales_item = 0
        it.insert(ignore_permissions=True)
    frappe.db.set_value("Item", qop_item, "uz_bosma_rulon", code)
    return code
