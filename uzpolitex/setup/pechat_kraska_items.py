"""Pechat dizaynlarida aniqlangan, ammo omborda yo'q Pantone ranglar uchun
kraska Item yaratadi va bo'sh qatorlarni bog'laydi (foydalanuvchi: Pantone bo'yicha yangi item)."""
import frappe

GROUP = "Сырьё - Печать"
DEFAULT_WH = "Печать - UH"

# Pantone -> item nomi (aniqlangan ranglar)
PANTONE_ITEMS = {
    "PANTONE 320": "Краска Teal (PANTONE 320)",
}


def apply():
    created = linked = 0
    # 1) yetishmayotgan Pantone qiymatlar (bo'sh rangli qatorlardan)
    pantones = frappe.db.sql_list("""SELECT DISTINCT pantone FROM `tabPechat Dizayn Rang`
        WHERE (rang='' OR rang IS NULL) AND pantone IS NOT NULL AND pantone!=''""")
    for p in pantones:
        item_name = PANTONE_ITEMS.get(p, f"Краска {p}")
        if not frappe.db.exists("Item", item_name):
            it = frappe.new_doc("Item")
            it.item_code = item_name
            it.item_name = item_name
            it.item_group = GROUP
            it.stock_uom = "Kg"
            it.is_stock_item = 1
            it.append("item_defaults", {"company": frappe.defaults.get_defaults().get("company"),
                                        "default_warehouse": DEFAULT_WH})
            it.insert(ignore_permissions=True)
            created += 1
        # 2) shu pantone'li bo'sh qatorlarni bog'lash
        n = frappe.db.sql("""UPDATE `tabPechat Dizayn Rang` SET rang=%s
            WHERE (rang='' OR rang IS NULL) AND pantone=%s""", (item_name, p))
        linked += frappe.db.sql("""SELECT ROW_COUNT()""")[0][0]
    frappe.db.commit()
    print(f"Yaratilgan Pantone item: {created} | bog'langan qator: {linked}")
    return created, linked
