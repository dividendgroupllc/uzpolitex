"""Test: barcha real namuna dizaynlarini v2 analizatori bilan kutubxonaga kiritadi."""
import os, glob
import frappe
from uzpolitex.pechat import ink_analyzer

DOCDIR = "/home/user/Documents"
# fayl -> ko'rinadigan nom
NAMES = {
    "zakaz1": "Veltora наливной пол", "zakaz2": "Vertex клей", "zakaz3": "Vertex Plaster",
    "zakaz4": "Oltin Asr клей", "zakaz5": "Oltin Asr Evrobond", "zakaz6": "Grander клей",
    "zakaz7": "Osiyo наливной пол", "uzpolitex1": "BAYTEX Gipssand", "uzpolitex2": "WORK клей",
    "uzpolitex3": "KLEBER Monolit", "uzploitex4": "DARMIX Базовый", "uzpolitex5": "DARMIX Усиленный",
    "uzpolitex6": "БАРАКАТ газоблок", "uzpolitex7": "БАРАКАТ кафель", "uzpolitex8": "ASSYL Universal",
    "uzpolitex9": "GRANT Standart", "uzpolitex10": "GRANT газоблок", "uzpolitex11": "BEKO MIX (render)",
    "uzpolitex12": "CLASS Monolit", "uzpolitex13": "TEX MIX 401", "uzpolitex15": "KAZmix клей",
    "uzpolitex16": "BAYTEX наливной пол", "uzpolitex17": "BAYTEX Universal клей",
    "uzpolitex18": "R MIX усиленный", "uzpolitex19": "BAYMIX Gyps Plaster",
    "meshok akmix gips.cdr.jpg": "AKMIX Гипс", "meshok kalsit kz.cdr.jpg": "KALSIT Universal",
}


def run():
    from frappe.utils.file_manager import save_file

    files = sorted(glob.glob(os.path.join(DOCDIR, "zakaz*"))) + \
        sorted(glob.glob(os.path.join(DOCDIR, "uzp*"))) + \
        sorted(glob.glob(os.path.join(DOCDIR, "meshok*")))
    ok = mock = 0
    for path in files:
        fn = os.path.basename(path)
        nomi = NAMES.get(fn, fn) + " — Олд"
        if frappe.db.exists("Pechat Dizayn", nomi):
            frappe.delete_doc("Pechat Dizayn", nomi, force=1)
        doc = frappe.new_doc("Pechat Dizayn")
        doc.dizayn_nomi = nomi
        doc.komponent = "Олд"
        doc.izoh = f"Намуна: {fn}"
        doc.insert()
        with open(path, "rb") as fh:
            f = save_file(fn if fn.endswith(".jpg") else fn + ".jpg", fh.read(),
                          "Pechat Dizayn", doc.name, is_private=0)
        doc.db_set("rasm", f.file_url)
        res = ink_analyzer.analyze(doc.name)
        doc.reload()
        doc.oq_baza_pct = res["oq_baza_pct"]
        if res.get("is_mockup"):
            doc.izoh += "  ⚠ MOCKUP/фото — текис дизайн эмас, аниқ .cdr керак."
            mock += 1
        for row in res["ranglar"]:
            doc.append("ranglar", {
                "rang": "" if row.get("mavjud_emas") else row["rang"],
                "pantone": row.get("pantone", ""),
                "qoplama_pct": row["qoplama_pct"],
                "rgb": row["rgb"] + (f" ({row['rang']}?)" if row.get("mavjud_emas") else ""),
                "avto": 1,
            })
        doc.save()
        ok += 1
    frappe.db.commit()
    print(f"Kiritildi: {ok} dizayn ({mock} ta mockup belgilandi). Jami: {frappe.db.count('Pechat Dizayn')}")
