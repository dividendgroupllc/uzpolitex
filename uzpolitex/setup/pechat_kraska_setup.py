"""Asosiy kraskalarga RGB + tur beradi; teal'ni aralashma qilib AI retsept tuzadi."""
import frappe
from uzpolitex.pechat import kraska_mix

# ombordagi asosiy kraska -> HEX (aralashtirish uchun)
BASE_RGB = {
    "Кўк": "#007ac2", "Қизил": "#d62027", "Қора": "#1a1a1a", "Оқ": "#ffffff",
    "Оранжевый": "#f16a18", "Сариқ": "#f7cd28", "Яшил": "#238c3e",
    "Magenta": "#c41a70", "Фиолетовый": "#7e37a0", "Тўқ кўк": "#202c6e",
    "Тўқ қизил": "#96181e", "тилла ранг": "#c4a04a",
}


def apply():
    n_base = 0
    for nom, hexv in BASE_RGB.items():
        if frappe.db.exists("Item", nom):
            frappe.db.set_value("Item", nom, {"uz_kraska_turi": "Асосий", "uz_rgb": hexv})
            n_base += 1
    frappe.db.commit()
    print(f"Асосий краска белгиланди: {n_base}")

    # teal -> aralashma + AI retsept
    teal = "Краска Teal (PANTONE 320)"
    if frappe.db.exists("Item", teal):
        d = frappe.get_doc("Item", teal)
        d.uz_kraska_turi = "Аралашма"
        d.uz_rgb = "#009ca6"
        d.save(ignore_permissions=True)
        res = kraska_mix.suggest(teal)
        d.reload()
        d.set("uz_retsept", [])
        for c in res["components"]:
            d.append("uz_retsept", c)
        d.save(ignore_permissions=True)
        frappe.db.commit()
        print(f"Teal ретсепти (≈{res['mix_hex']}, Δ={res['delta']}):")
        for c in res["components"]:
            print(f"   {c['baza_rang']:14s} {c['ulush_pct']}%")
