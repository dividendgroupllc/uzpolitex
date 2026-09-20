"""Sales Order «Қоп заказлар» jadvalidan qop Item + Pechat Dizayn AVTO yaratish.

Foydalanuvchi qarori (2026-09-15): har zakaz noyob. Sales Order'da rasm+o'lcham bilan
kiritiladi -> qop Item avto yaratiladi va DARHOL standart items jadvaliga tushadi
(client `prepare` chaqiradi), items majburiy qoladi. before_validate — server tarafida
zaxira (API/darhol submit uchun).
"""

import json
import os

import frappe
from frappe import _

from uzpolitex.pechat import ink_analyzer, order_ink

QOP_GROUP = "Готовый продукт - Конверт"
SSMES_DESIGN = "S.S.Smes — Лента (умумий)"

# qop o'lchami sm da kiritiladi; bundan katta qiymat — mm kiritilgan (500 = 5 metr!)
MAX_CM = 150
MIN_CM = 5


def _check_olcham(nomi, en, boy):
    for label, v in (("Эни", en), ("Бўйи", boy)):
        v = float(v or 0)
        if v > MAX_CM:
            frappe.throw(
                _("«{0}»: {1} {2} см — бу {3} метр! Ўлчам СМ да киритилади (масалан 50, 500 эмас).").format(
                    nomi, label, frappe.format(v, "Float"), frappe.format(v / 100, "Float")
                )
            )
        if 0 < v < MIN_CM:
            frappe.throw(
                _("«{0}»: {1} {2} см — жуда кичик, СМ да киритинг.").format(
                    nomi, label, frappe.format(v, "Float")
                )
            )


def _file_path(url):
    fd = frappe.get_all("File", filters={"file_url": url}, fields=["name"], limit=1)
    return frappe.get_doc("File", fd[0].name).get_full_path() if fd else None


def _num(v):
    v = v or 0
    return int(v) if float(v) == int(v) else v


def _item_code(nomi, en, boy):
    return f"{(nomi or '').strip()} {_num(en)}x{_num(boy)}"


def _create_or_get_item(code):
    """(code, yangi_yaratildi)"""
    if frappe.db.exists("Item", code):
        return code, False
    it = frappe.new_doc("Item")
    it.item_code = it.item_name = code
    it.item_group = QOP_GROUP
    it.stock_uom = "Unit"
    it.is_stock_item = 1
    it.is_sales_item = 1
    it.uz_qop = 1
    it.insert(ignore_permissions=True)
    return code, True


def _content_hash(file_url):
    if not file_url:
        return None
    return frappe.db.get_value("File", {"file_url": file_url}, "content_hash")


def _attach_and_analyze(d, image_url):
    """Rasmni dizaynga biriktirib AI tahlilini o'tkazadi (ranglar QAYTA yoziladi)."""
    path = _file_path(image_url)
    if not path:
        return
    from frappe.utils.file_manager import save_file

    with open(path, "rb") as fh:
        f = save_file(os.path.basename(path), fh.read(), "Pechat Dizayn", d.name, is_private=0)
    d.db_set("rasm", f.file_url)
    try:
        res = ink_analyzer.analyze(d.name)
        d.reload()
        d.oq_baza_pct = res["oq_baza_pct"]
        inks = set(frappe.get_all("Item", filters={"item_group": "Сырьё - Печать"}, pluck="name"))
        # «Серый» — zavodda mavjud bo'lmagan bo'yoq (0 zaxira, 0 harakat):
        # AI antialiasing/foto shovqinini shunga moslaydi. Rang BO'SH qoladi —
        # operator haqiqiy rang bo'lsa o'zi tanlaydi, hisob-kitoblarga kirmaydi.
        SHOVQIN = {"Серый"}
        d.set("ranglar", [])
        for r in res["ranglar"]:
            mos = r["rang"] if r["rang"] in inks and r["rang"] not in SHOVQIN else ""
            d.append("ranglar", {
                "rang": mos,
                "pantone": r.get("pantone", ""), "qoplama_pct": r["qoplama_pct"],
                "rgb": r["rgb"], "avto": 1})
        if res.get("is_mockup"):
            d.izoh = "⚠ Mockup/фото — текис .cdr керак."
        d.save(ignore_permissions=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Pechat Dizayn AI tahlil xatosi")


def _create_or_get_design(name, image_url, komp):
    """(name, yangilandi) — mavjud dizaynda rasm O'ZGARGAN bo'lsa yangilaydi
    (takror zakaz, mijoz dizaynni yangilagan holat)."""
    if frappe.db.exists("Pechat Dizayn", name):
        if image_url:
            d = frappe.get_doc("Pechat Dizayn", name)
            yangi, eski = _content_hash(image_url), _content_hash(d.rasm)
            if yangi and yangi != eski:
                _attach_and_analyze(d, image_url)
                d.db_set("izoh", "⚠ Расм янгиланди (такрор заказ) — рангларни текширинг.")
                return name, True
        return name, False
    d = frappe.new_doc("Pechat Dizayn")
    d.dizayn_nomi = name
    d.komponent = komp
    d.insert(ignore_permissions=True)
    if image_url:
        _attach_and_analyze(d, image_url)
    return name, False


def _shared_ssmes():
    if not frappe.db.exists("Pechat Dizayn", SSMES_DESIGN):
        d = frappe.new_doc("Pechat Dizayn")
        d.dizayn_nomi = SSMES_DESIGN
        d.komponent = "Лента"
        d.izoh = "Умумий S.S.Smes ён ленталар. Ранглар/қопламани техноlog тўлдиради."
        d.insert(ignore_permissions=True)
    return SSMES_DESIGN


def process_row(row):
    """row — obyekt/dict (nomi, en_cm, boy_cm, soni, old_rasm, orqa_turi, orqa_rasm,
    lenta_turi, lenta_rasm). Item+dizayn yaratadi/yangilaydi. (item_code, holat) qaytaradi.
    Idempotent — item bor qatorda ham chaqirsa bo'ladi (rasm o'zgargan bo'lsa dizayn yangilanadi)."""
    g = row.get if hasattr(row, "get") else lambda k, d=None: getattr(row, k, d)
    nomi, en, boy = g("nomi"), g("en_cm"), g("boy_cm")
    if not (nomi and en and boy and g("old_rasm")):
        return None, "Тўлиқ эмас: номи/ўлчам/ОЛД расм керак."
    _check_olcham(nomi, en, boy)
    code = _item_code(nomi, en, boy)
    _, item_yangi = _create_or_get_item(code)
    yangilangan = []
    old_d, upd = _create_or_get_design(f"{code} — Олд", g("old_rasm"), "Олд")
    if upd:
        yangilangan.append("Олд")
    orqa_d = None
    if g("orqa_turi") == "Ўзиники" and g("orqa_rasm"):
        orqa_d, upd = _create_or_get_design(f"{code} — Орқа", g("orqa_rasm"), "Орқа")
        if upd:
            yangilangan.append("Орқа")
    lenta_d = None
    if g("lenta_turi") == "S.S.Smes":
        lenta_d = _shared_ssmes()
    elif g("lenta_turi") == "Ўзиники" and g("lenta_rasm"):
        lenta_d, upd = _create_or_get_design(f"{code} — Лента", g("lenta_rasm"), "Лента")
        if upd:
            yangilangan.append("Лента")
    frappe.db.set_value("Item", code, {
        "uz_qop": 1, "uz_dizayn_old": old_d, "uz_dizayn_orqa": orqa_d,
        "uz_dizayn_lenta": lenta_d, "uz_en_cm": en, "uz_boy_cm": boy})
    if item_yangi:
        holat = "✓ Item ва дизайн яратилди."
    elif yangilangan:
        holat = "⚠ Такрор заказ, расм ўзгарган — {0} дизайн ЯНГИЛАНДИ, рангларни текширинг.".format(
            "/".join(yangilangan))
    else:
        holat = "✓ Мавжуд item ишлатилди (такрор заказ)."
    return code, holat


@frappe.whitelist()
def prepare(rows):
    """Client chaqiradi: qator ma'lumotlaridan Item+dizayn yaratadi, item kodlarini qaytaradi.
    rows = JSON ro'yxat. Qaytadi: [{name, item, soni, holat}] — client items jadvalini to'ldiradi."""
    if isinstance(rows, str):
        rows = json.loads(rows)
    out = []
    for r in rows:
        r = frappe._dict(r)
        # item bor qatorda ham process_row: rasm o'zgargan bo'lsa dizayn yangilanadi
        code, holat = process_row(r)
        out.append({"name": r.get("name"), "item": code or r.get("item"),
                    "soni": r.get("soni"), "holat": holat if code else r.get("holat")})
    frappe.db.commit()
    return out


def _sync_line(doc, code, soni):
    for it in doc.get("items"):
        if it.item_code == code:
            it.qty = soni or it.qty or 1
            return
    doc.append("items", {"item_code": code, "qty": soni or 1, "uom": "Unit",
                         "conversion_factor": 1, "rate": 0,
                         "delivery_date": doc.get("delivery_date") or frappe.utils.nowdate()})


def before_validate(doc, method=None):
    """Server zaxira: item'siz qator kelsa yaratadi; rasm o'zgargan bo'lsa dizayn
    yangilanadi; items miqdori = shu itemli BARCHA zakaz qatorlari yig'indisi."""
    if not doc.get("uz_qop_zakazlar"):
        return
    jami = {}  # item -> Σ soni (bitta mahsulot bir necha qatorda kelishi mumkin)
    for row in doc.uz_qop_zakazlar:
        code, holat = process_row(row)
        if code:
            row.item = code
            row.holat = holat
            jami[code] = jami.get(code, 0) + (row.soni or 0)
    for code, soni in jami.items():
        _sync_line(doc, code, soni)
    # bo'sh items qatorlari (kodsiz) olib tashlanadi — zakaz 1-qatordan boshlanadi
    toza = [r for r in doc.get("items") if r.item_code]
    for i, r in enumerate(toza, 1):
        r.idx = i
    doc.set("items", toza)
    try:
        order_ink.compute_doc(doc)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Kraska norma hisoblash xatosi")
