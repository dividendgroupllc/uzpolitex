"""Sales Order (zakaz) uchun kraska normasini hisoblash.

Har qop qatori: old+orqa+lenta dizaynlari × yuza(m²) × soni × qoplama% × g/m² /1000 = kg.
Aralashma ranglar asosiy kraskalarga yoyiladi (on-the-fly). orqa bo'sh = universal (0 kraska).
g/m² hozircha taxminiy (uz_kraska_gm2); keyin Печать smena fakti bilan kalibrlanadi.
"""

import frappe

from uzpolitex.pechat.kraska_mix import expand_to_bases


def _component_area_m2(item, komp):
    boy = (item.get("uz_boy_cm") or 0) / 100.0
    if komp == "Лента":
        en = (item.get("uz_lenta_en_cm") or 0) / 100.0
        return 2.0 * en * boy
    en = (item.get("uz_en_cm") or 0) / 100.0
    return en * boy


def _default_gm2():
    from uzpolitex.pechat import kalibr  # lazy: kalibr shu modulni import qiladi

    return kalibr.get_gm2()


def compute_doc(so):
    """so (in-memory Sales Order) uchun kraska normasini hisoblaydi va uz_kraska_normasi
    jadvalini to'ldiradi. SAQLAMAYDI. Ogohlantirishlar ro'yxatini qaytaradi."""
    gm2 = so.get("uz_kraska_gm2") or _default_gm2()
    totals = {}
    ogohlar = []
    item_cache = {}

    for line in so.get("items") or []:
        item = item_cache.get(line.item_code)
        if item is None:
            item = frappe.get_doc("Item", line.item_code)
            item_cache[line.item_code] = item
        if not item.get("uz_qop"):
            continue
        qty = line.qty or 0
        for komp, dizayn in (("Олд", item.get("uz_dizayn_old")),
                             ("Орқа", item.get("uz_dizayn_orqa")),
                             ("Лента", item.get("uz_dizayn_lenta"))):
            if not dizayn:
                continue
            area = _component_area_m2(item, komp)
            if area <= 0:
                ogohlar.append(f"{line.item_code}: ўлчам йўқ ({komp}).")
                continue
            d = frappe.get_doc("Pechat Dizayn", dizayn)
            for r in d.ranglar:
                if not r.rang:
                    ogohlar.append(f"{dizayn}: рангсиз қатор ({r.qoplama_pct}%).")
                    continue
                kg = (r.qoplama_pct or 0) / 100.0 * area * qty * gm2 / 1000.0
                for baza, bkg in expand_to_bases(r.rang, kg):
                    pantone = r.pantone if baza == r.rang else f"{r.pantone or r.rang}?"
                    e = totals.setdefault(baza, {"kg": 0.0, "pantone": pantone})
                    e["kg"] += bkg

    so.set("uz_kraska_normasi", [])
    for rang, e in sorted(totals.items(), key=lambda kv: -kv[1]["kg"]):
        so.append("uz_kraska_normasi", {"rang": rang, "pantone": e["pantone"], "kg": round(e["kg"], 2)})
    return list(dict.fromkeys(ogohlar))


@frappe.whitelist()
def compute(sales_order):
    so = frappe.get_doc("Sales Order", sales_order)
    ogohlar = compute_doc(so)
    so.save()
    return {"qatorlar": len(so.uz_kraska_normasi), "ogohlar": ogohlar}


def compute_prep(so):
    """Печать Топшириқ учун: дизайн-ранг даражасида (базага ЁЙИЛМАЙ) режа кг + ретсепт.
    Босмачи нимани тайёрлашни билади. [{rang, turi, reja_kg, retsept, pantone}]."""
    gm2 = so.get("uz_kraska_gm2") or _default_gm2()
    agg = {}
    for line in so.get("items") or []:
        item = frappe.get_doc("Item", line.item_code)
        if not item.get("uz_qop"):
            continue
        qty = line.qty or 0
        for komp, dizayn in (("Олд", item.get("uz_dizayn_old")),
                             ("Орқа", item.get("uz_dizayn_orqa")),
                             ("Лента", item.get("uz_dizayn_lenta"))):
            if not dizayn:
                continue
            area = _component_area_m2(item, komp)
            if area <= 0:
                continue
            d = frappe.get_doc("Pechat Dizayn", dizayn)
            for r in d.ranglar:
                if not r.rang:
                    continue
                kg = (r.qoplama_pct or 0) / 100.0 * area * qty * gm2 / 1000.0
                e = agg.setdefault(r.rang, {"kg": 0.0, "pantone": r.pantone})
                e["kg"] += kg
    rows = []
    for rang, e in sorted(agg.items(), key=lambda kv: -kv[1]["kg"]):
        turi = frappe.db.get_value("Item", rang, "uz_kraska_turi") or "Асосий"
        retsept = ""
        if turi == "Аралашма":
            ret = frappe.get_all("Uzpolitex Kraska Retsept", filters={"parent": rang},
                                 fields=["baza_rang", "ulush_pct"])
            retsept = " + ".join(f"{x.baza_rang} {x.ulush_pct:.0f}%" for x in ret)
        rows.append({"rang": rang, "turi": turi, "reja_kg": round(e["kg"], 2),
                     "retsept": retsept, "pantone": e["pantone"]})
    return rows
