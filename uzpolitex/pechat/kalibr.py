"""g/m² o'z-o'zini kalibrlash.

Har Pechat Jurnal (fakt) submit/cancelida qayta hisoblanadi:
  gm2 = Σ(fakt kraska kg) / Σ(bosilgan metr × qop dizaynining 1 metr rulondagi
  qoplama m²) — barcha submitted jurnallar bo'yicha.
Natija «Pechat Kalibr» (Single) da saqlanadi; Sales Order normasi (order_ink)
uz_kraska_gm2 bo'sh bo'lsa shu qiymatni oladi.
"""

import frappe
from frappe.utils import flt

from uzpolitex.pechat.order_ink import _component_area_m2

BOSHLANGICH_GM2 = 2.0


def qoplama_m2_per_metr(qop_item):
    """Qop dizaynlarining 1 metr rulonga to'g'ri keladigan qoplama yuzasi (m²).

    1 qop = boy_cm/100 metr rulon. Har komponent: Σ(qoplama% × komponent m²)."""
    item = frappe.get_doc("Item", qop_item)
    boy_m = flt(item.get("uz_boy_cm")) / 100.0
    if not boy_m:
        return 0.0
    m2_per_qop = 0.0
    for komp, dizayn in (("Олд", item.get("uz_dizayn_old")),
                         ("Орқа", item.get("uz_dizayn_orqa")),
                         ("Лента", item.get("uz_dizayn_lenta"))):
        if not dizayn:
            continue
        area = _component_area_m2(item, komp)
        d = frappe.get_doc("Pechat Dizayn", dizayn)
        for r in d.ranglar:
            if r.rang:
                m2_per_qop += flt(r.qoplama_pct) / 100.0 * area
    return m2_per_qop / boy_m


def get_gm2():
    v = flt(frappe.db.get_single_value("Pechat Kalibr", "gm2"))
    return v or BOSHLANGICH_GM2


def recompute():
    """HAQIQIY smena faktlaridan to'liq qayta hisob (idempotent).

    Har submitted «Pechat Smena Fakt»: fakt kg / shu smena jurnallarining
    qoplama m² (metr × dizayn qoplamasi)."""
    jami_kg = jami_m2 = 0.0
    for sf in frappe.get_all("Pechat Smena Fakt", filters={"docstatus": 1},
                             fields=["name", "posting_date", "smena"]):
        kg = sum(flt(r.fakt_kg) for r in frappe.get_all(
            "Pechat Smena Fakt Qator", filters={"parent": sf.name}, fields=["fakt_kg"]))
        if not kg:
            continue
        m2 = 0.0
        for j in frappe.get_all("Pechat Jurnal",
                                filters={"posting_date": sf.posting_date,
                                         "smena": sf.smena, "docstatus": 1},
                                fields=["qop_item", "metr"]):
            if j.qop_item and flt(j.metr):
                m2 += flt(j.metr) * qoplama_m2_per_metr(j.qop_item)
        if m2 <= 0:
            continue
        jami_kg += kg
        jami_m2 += m2

    s = frappe.get_doc("Pechat Kalibr")
    s.jami_kg = flt(jami_kg, 2)
    s.jami_m2 = flt(jami_m2, 2)
    s.gm2 = flt(jami_kg / jami_m2 * 1000, 2) if jami_m2 else 0
    s.save(ignore_permissions=True)
    return s.gm2
