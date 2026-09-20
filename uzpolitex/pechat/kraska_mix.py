"""Nostandart (spot) rangni asosiy kraskalardan aralashtirish retsepti.

Foydalanuvchi qarori (2026-09-15): on-the-fly aralashtirish (omborda baza sarfi),
AI 1-2 asosiy rangning optimal nisbatini taklif qiladi, texnolog tasdiqlaydi.

Model: kraska aralashuvi SUBTRAKTIV. Reflektans D = -ln(R/255) (Beer-Lambert kabi);
aralashma zichligi = Σ ulush × baza_zichligi; keyin RGB ga qaytariladi.
1-2 baza (ixtiyoriy Оқ 3-komponent) ustidan qidiruv, targetga eng yaqin + eng kam komponentli.
"""

import math
import frappe


def _hex_to_rgb(h):
    h = (h or "").strip().lstrip("#")
    if len(h) != 6:
        return None
    try:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None


def _rgb_to_hex(rgb):
    return "#%02x%02x%02x" % tuple(int(max(0, min(255, round(c)))) for c in rgb)


def _density(rgb):
    return [-math.log(max(c, 1) / 255.0) for c in rgb]


def _mix(weights, densities):
    """Ulushlar (Σ=1) va baza zichliklaridan aralashma RGB."""
    d = [0.0, 0.0, 0.0]
    for w, dens in zip(weights, densities):
        for i in range(3):
            d[i] += w * dens[i]
    return [255.0 * math.exp(-d[i]) for i in range(3)]


def _dist(a, b):
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))


def suggest_recipe(target_rgb, bases, max_comp=2, step=0.05):
    """bases = [(nom, rgb), ...]. Eng yaxshi 1-2 (ixtiyoriy +Оқ) retsept.
    Qaytadi: {"components": [(nom, ulush%)...], "mix_rgb": rgb, "delta": xato}."""
    dens = {nom: _density(rgb) for nom, rgb in bases}
    names = [n for n, _ in bases]
    best = None

    def consider(combo):
        nonlocal best
        # combo ulushlari ustidan grid
        n = len(combo)
        if n == 1:
            cand = [(1.0,)]
        elif n == 2:
            cand = [(w, 1 - w) for w in [round(i * step, 3) for i in range(1, int(1 / step))]]
        else:  # 3
            cand = []
            rng = [round(i * step, 3) for i in range(1, int(1 / step))]
            for w1 in rng:
                for w2 in rng:
                    if w1 + w2 < 1:
                        cand.append((w1, w2, 1 - w1 - w2))
        for ws in cand:
            rgb = _mix(ws, [dens[c] for c in combo])
            d = _dist(rgb, target_rgb)
            # kam komponentga ozgina imtiyoz (soddalik uchun)
            score = d + (n - 1) * 2.0
            if best is None or score < best["score"]:
                best = {"score": score, "delta": round(d, 1), "mix_rgb": rgb,
                        "components": [(combo[i], round(ws[i] * 100, 1)) for i in range(n)]}

    # 1 va 2 komponent
    for i in range(len(names)):
        consider((names[i],))
        for j in range(i + 1, len(names)):
            consider((names[i], names[j]))
    # 3-komponent faqat Оқ bilan (ochroq tuslar uchun), agar mavjud bo'lsa
    if max_comp >= 3 and "Оқ" in names:
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                if "Оқ" in (names[i], names[j]):
                    continue
                consider((names[i], names[j], "Оқ"))
    return best


def _get_bases():
    """Асосий kraska itemlari (RGB belgilangan)."""
    rows = frappe.get_all("Item",
                          filters={"item_group": "Сырьё - Печать", "uz_kraska_turi": "Асосий"},
                          fields=["name", "uz_rgb"])
    bases = []
    for r in rows:
        rgb = _hex_to_rgb(r.uz_rgb)
        if rgb:
            bases.append((r.name, rgb))
    return bases


@frappe.whitelist()
def suggest(item, allow_white=1):
    """Item.uz_rgb (target) uchun retsept taklif qiladi -> child qatorlar."""
    doc = frappe.get_doc("Item", item)
    target = _hex_to_rgb(doc.get("uz_rgb"))
    if not target:
        frappe.throw("Аввал «Ранг (HEX)» майдонига мақсадли рангни киритинг (масалан #08afad).")
    bases = [(n, rgb) for n, rgb in _get_bases() if n != doc.name]
    if not bases:
        frappe.throw("Асосий (RGB белгиланган) краска топилмади. Аввал асосий ранглар RGB сини киритинг.")
    res = suggest_recipe(target, bases, max_comp=3 if int(allow_white) else 2)
    if not res:
        frappe.throw("Ретсепт топилмади.")
    return {
        "components": [{"baza_rang": n, "ulush_pct": p} for n, p in res["components"]],
        "mix_hex": _rgb_to_hex(res["mix_rgb"]),
        "delta": res["delta"],
    }


def expand_to_bases(rang, kg):
    """Aralashma rangni asosiy kraskalarga yoyadi. [(baza_nom, kg)...] qaytaradi.
    Asosiy rang bo'lsa yoki retseptsiz bo'lsa o'zini qaytaradi."""
    turi = frappe.db.get_value("Item", rang, "uz_kraska_turi")
    if turi != "Аралашма":
        return [(rang, kg)]
    ret = frappe.get_all("Uzpolitex Kraska Retsept", filters={"parent": rang},
                         fields=["baza_rang", "ulush_pct"])
    total = sum((r.ulush_pct or 0) for r in ret)
    if not ret or total <= 0:
        return [(rang, kg)]  # retsept yo'q -> yoyilmaydi (ogoh order_ink'da)
    out = []
    for r in ret:
        out.append((r.baza_rang, kg * (r.ulush_pct or 0) / total))
    return out
