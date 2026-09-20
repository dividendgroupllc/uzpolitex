"""Sales Order submit -> Печать Топшириқ (reja) AVTO yaratish.

Topshiriq = zakazga bog'langan REJA (kraska normasi + AI aralashma retsepti).
Haqiqiy sarf smena bo'yicha (Pechat Jurnal) yoziladi; kalibrlash keyin.
"""

import frappe

from uzpolitex.pechat import order_ink, rulon


def create_from_so(so):
    if frappe.db.exists("Pechat Topshiriq", {"sales_order": so.name, "docstatus": ["<", 2]}):
        return None
    if not so.get("uz_qop_zakazlar"):
        return None
    t = frappe.new_doc("Pechat Topshiriq")
    t.sales_order = so.name
    t.customer = so.customer
    t.holat = "Черновик"
    has_qop = False
    for z in so.uz_qop_zakazlar:
        if not z.item:
            continue
        # zakaz uchun bosma rulon itemi oldindan tayyor bo'lsin (Печать chiqimi)
        rulon.bosma_rulon(z.item)
        item = frappe.get_doc("Item", z.item)
        t.append("qoplar", {
            "item": z.item, "soni": z.soni, "en_cm": z.en_cm, "boy_cm": z.boy_cm,
            "dizayn_old": item.get("uz_dizayn_old"), "dizayn_orqa": item.get("uz_dizayn_orqa"),
            "dizayn_lenta": item.get("uz_dizayn_lenta")})
        has_qop = True
    if not has_qop:
        return None
    for row in order_ink.compute_prep(so):
        t.append("kraska_reja", row)
    t.insert(ignore_permissions=True)
    return t.name


@frappe.whitelist()
def reja_yangila(name):
	"""Topshiriq kraska rejasini JORIY dizayn ranglari va kalibrlangan g/m²
	bilan qayta hisoblaydi (dizayn tuzatilgach reja eskirib qoladi)."""
	t = frappe.get_doc("Pechat Topshiriq", name)
	so = frappe.get_doc("Sales Order", t.sales_order)
	eski_fakt = {r.rang: r.fakt_kg for r in t.kraska_reja if r.fakt_kg}
	t.set("kraska_reja", [])
	for row in order_ink.compute_prep(so):
		t.append("kraska_reja", row)
	borlar = set()
	for r in t.kraska_reja:
		r.fakt_kg = eski_fakt.get(r.rang, 0)
		borlar.add(r.rang)
	for rang, kg in eski_fakt.items():
		if rang not in borlar:
			t.append("kraska_reja", {"rang": rang, "turi": "Режадан ташқари",
			                         "reja_kg": 0, "fakt_kg": kg})
	t.flags.ignore_validate_update_after_submit = True
	t.save(ignore_permissions=True)
	return {"qatorlar": len(t.kraska_reja)}


def on_submit_so(doc, method=None):
    name = create_from_so(doc)
    if name:
        frappe.msgprint(
            frappe._("Печать Топшириқ (черновик) яратилди: {0}").format(
                frappe.utils.get_link_to_form("Pechat Topshiriq", name)),
            indicator="green", alert=True)
