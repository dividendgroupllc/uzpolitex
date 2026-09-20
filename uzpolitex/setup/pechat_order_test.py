"""E2E test: 7 zakaz uchun qop Item + Sales Order + kraska norma hisobi."""
import frappe
from uzpolitex.pechat import order_ink

# (item nomi, dizayn (old), en_cm, boy_cm)
QOPLAR = [
    ("QOP Veltora наливной пол 35x48", "Veltora наливной пол — Олд", 35, 48),
    ("QOP Vertex клей 35x48", "Vertex клей — Олд", 35, 48),
    ("QOP Vertex Plaster 40x50", "Vertex Plaster — Олд", 40, 50),
    ("QOP Oltin Asr клей 35x49", "Oltin Asr клей — Олд", 35, 49),
    ("QOP Oltin Asr Evrobond 40x48", "Oltin Asr Evrobond — Олд", 40, 48),
    ("QOP Grander клей 35x48", "Grander клей — Олд", 35, 48),
    ("QOP Osiyo наливной пол 35x48", "Osiyo наливной пол — Олд", 35, 48),
]


def run():
    # 1) qop itemlar
    for nom, dizayn, en, boy in QOPLAR:
        if frappe.db.exists("Item", nom):
            frappe.delete_doc("Item", nom, force=1)
        it = frappe.new_doc("Item")
        it.item_code = nom
        it.item_name = nom
        it.item_group = "Готовый продукт - Конверт"
        it.stock_uom = "Unit"
        it.is_stock_item = 1
        it.is_sales_item = 1
        it.uz_qop = 1
        it.uz_dizayn_old = dizayn
        it.uz_en_cm = en
        it.uz_boy_cm = boy
        it.insert(ignore_permissions=True)

    # 2) Sales Order
    cust = frappe.get_all("Customer", limit=1, pluck="name")[0]
    comp = "Uzpolitex Holding"
    if frappe.db.exists("Sales Order", {"customer": cust, "po_no": "TEST-PECHAT"}):
        for n in frappe.get_all("Sales Order", filters={"po_no": "TEST-PECHAT"}, pluck="name"):
            frappe.delete_doc("Sales Order", n, force=1)
    cur = frappe.get_cached_value("Company", comp, "default_currency")
    so = frappe.new_doc("Sales Order")
    so.customer = cust
    so.company = comp
    so.po_no = "TEST-PECHAT"
    so.delivery_date = frappe.utils.nowdate()
    so.currency = cur
    so.conversion_rate = 1
    so.selling_price_list = "Standard Selling"
    so.price_list_currency = cur
    so.plc_conversion_rate = 1
    so.uz_kraska_gm2 = 2.0
    for nom, *_ in QOPLAR:
        so.append("items", {"item_code": nom, "qty": 5000, "rate": 0,
                            "delivery_date": frappe.utils.nowdate()})
    so.insert(ignore_permissions=True)

    # 3) hisobla
    res = order_ink.compute(so.name)
    frappe.db.commit()

    so.reload()
    print(f"\n=== Sales Order {so.name} — КРАСКА НОРМАСИ (g/m²={so.uz_kraska_gm2}) ===")
    jami = 0
    for r in so.uz_kraska_normasi:
        print(f"   {r.rang:32s} {r.kg:8.2f} кг   {r.pantone or ''}")
        jami += r.kg
    print(f"   {'ЖАМИ':32s} {jami:8.2f} кг")
    if res.get("ogohlar"):
        print("\nОгоҳлантиришлар:")
        for w in res["ogohlar"]:
            print("   -", w)
