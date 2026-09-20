"""
Pechat dizayn rasmidan kraska (rang) qoplamasini avtomatik aniqlash — v2.

v2 yangiliklari (26 namuna tahlilidan keyin, 2026-09-15):
- ZICHLIK bilan o'lchangan qoplama: har piksel oqdan qanchalik uzoq (solid'ga qarab)
  bo'lsa, shuncha kraska. Antialiasing halosi, foto-halftone, to'q fon TO'G'RI hisoblanadi.
- Hue-aware klaster moslash: binafsha↔navy↔teal chalkashligi kamayadi.
- Mockup/foto detektori: tekis dizayn bo'lmasa (uzpolitex11 kabi) belgilaydi.
- Eng yaqin Pantone taklifi (operator dizayn faylidan tasdiqlaydi -> Pantone item).
- Chet/ruler/title-block ta'siri zichlik og'irligi bilan tabiiy kamayadi.

g/m² hech kimda yo'q -> bu modul faqat QOPLAMA (solid-ekvivalent %) beradi;
kg ga aylantirish keyingi bosqichda (Pechat Kalibrovka, o'z-o'zini kalibrlash).
"""

import frappe

WHITE = (255, 255, 255)
WHITE_TH = 236  # RGB shu qiymatdan yuqori = oq baza (qog'oz)

# Spot ranglar reference (solid RGB) + taxminiy Pantone kodi.
# Ombordagi mavjud kraska nomi (rang) + Pantone (yangi item uchun taklif).
PALETTE = [
    # (nom, solid_rgb, pantone_taklif)
    ("Қора",        (25, 25, 25),    "Process Black"),
    ("Қизил",       (214, 32, 39),   "PANTONE 485"),
    ("Тўқ қизил",   (150, 24, 30),   "PANTONE 1807"),
    ("Оранжевый",   (241, 106, 24),  "PANTONE 1585"),
    ("Сариқ",       (247, 205, 40),  "PANTONE 116"),
    ("тилла ранг",  (196, 160, 74),  "PANTONE 872 (gold)"),
    ("Яшил",        (35, 140, 62),   "PANTONE 355"),
    ("Teal/Кўк-яшил",(0, 156, 166),  "PANTONE 320"),
    ("Кўк",         (0, 122, 194),   "PANTONE 3005"),
    ("Тўқ кўк",     (32, 44, 110),   "PANTONE 281"),
    ("Фиолетовый",  (126, 55, 160),  "PANTONE 2593"),
    ("Magenta",     (196, 26, 112),  "PANTONE 233"),
    ("Серый",       (130, 130, 130), "PANTONE Cool Gray 8"),
]


def _hue_sat_val(rgb):
    import colorsys
    r, g, b = [x / 255.0 for x in rgb]
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    return h, s, v


def _match_spot(rgb):
    """Pikselni/klaster markazini spot rangga moslash: hue asosiy, keyin masofa.
    Past to'yinganlik (grey) -> Қора yoki Серый."""
    h, s, v = _hue_sat_val(rgb)
    # to'q piksellarda hue ishonchsiz -> qora (aks holda apelsin/qora fon navy'ga chalkashadi)
    if v < 0.30:
        return ("Қора", "Process Black")
    # kam to'yingan: qora yoki kulrang (chegara past — muddy/JPEG ranglar chromatic qoladi)
    if s < 0.12:
        return ("Қора", "Process Black") if v < 0.55 else ("Серый", "PANTONE Cool Gray 8")
    best, bd = None, 1e18
    for name, solid, pantone in PALETTE:
        if name in ("Қора", "Серый"):
            continue
        hh, ss, vv = _hue_sat_val(solid)
        dh = min(abs(h - hh), 1 - abs(h - hh))  # doiraviy hue farqi
        d = (dh * 3.0) ** 2 + (s - ss) ** 2 * 0.3 + (v - vv) ** 2 * 0.2
        if d < bd:
            bd, best = d, (name, pantone)
    return best


def _prep(path, max_side=500):
    import numpy as np
    from PIL import Image
    im = Image.open(path).convert("RGB")
    if max(im.size) > max_side:
        im.thumbnail((max_side, max_side))
    a = np.array(im)
    # chetlarni kesish: oq bo'lmagan kontent bbox (nozik ruler chiziqlarini tashlab)
    nw = ~((a[:, :, 0] > 238) & (a[:, :, 1] > 238) & (a[:, :, 2] > 238))
    ys, xs = np.where(nw)
    if len(xs):
        y0, y1 = int(np.percentile(ys, 0.5)), int(np.percentile(ys, 99.5))
        x0, x1 = int(np.percentile(xs, 0.5)), int(np.percentile(xs, 99.5))
        a = a[y0:y1 + 1, x0:x1 + 1]
    return a


def analyze_path(path, min_pct=1.0):
    import numpy as np
    from scipy.cluster.vq import kmeans2

    a = _prep(path)
    px = a.reshape(-1, 3).astype(float)
    total = len(px)
    if total == 0:
        return {"oq_baza_pct": 100.0, "printed_pct": 0.0, "is_mockup": 0, "warnings": [], "ranglar": []}

    # --- mockup/foto detektori ---
    # 1) kvantlash xatosi (gradient/foto -> katta)
    cen_all, lab_all = kmeans2(px, 8, minit="++", seed=3, iter=20)
    err = np.sqrt(((px - cen_all[lab_all]) ** 2).sum(1)).mean()
    # 2) mid-grey (studio foto foni) ulushi: past to'yingan, oq ham qora ham emas
    mx = px.max(1); mn = px.min(1)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0)
    val = mx / 255.0
    midgrey = ((sat < 0.15) & (val > 0.2) & (val < 0.92))
    midgrey_frac = midgrey.mean()
    is_mockup = 1 if (err > 55 or midgrey_frac > 0.30) else 0

    # --- oq baza ---
    is_white = (px[:, 0] > WHITE_TH) & (px[:, 1] > WHITE_TH) & (px[:, 2] > WHITE_TH)
    white_pct = 100.0 * int(is_white.sum()) / total
    ink = px[~is_white]

    ranglar = []
    printed = 0.0
    if len(ink):
        # spot markazlarni topish
        k = min(8, max(2, len(np.unique(ink.astype(np.uint8).view(np.void), return_index=True)[1])))
        try:
            cen, lab = kmeans2(ink, k, minit="++", seed=1, iter=25)
        except Exception:
            cen, lab = kmeans2(ink, 3, minit="points", seed=1, iter=25)

        solid_map = {name: solid for name, solid, _ in PALETTE}
        wvec = np.array(WHITE, float)
        agg = {}  # ink_nom -> {"dens": float, "rgb": (r,g,b) eng to'q, "pantone":..}
        for j in range(len(cen)):
            m = lab == j
            cnt = int(m.sum())
            if cnt == 0:
                continue
            c = cen[j]
            name, pantone = _match_spot(tuple(int(x) for x in c))
            # zichlik: har piksel oqdan matched ink'ning SOLID (asl) rangiga nisbatan qanchalik uzoq
            # -> och tuslar (foto, antialiasing) kam kraska beradi
            solid = np.array(solid_map.get(name, c), float)
            solid_dist = np.linalg.norm(wvec - solid) or 1.0
            pdist = np.linalg.norm(wvec - ink[m], axis=1)
            dens = np.clip(pdist / solid_dist, 0, 1).sum()  # solid-ekvivalent piksel soni
            e = agg.setdefault(name, {"dens": 0.0, "rgb": tuple(int(x) for x in c),
                                      "pantone": pantone, "vsum": 0.0})
            e["dens"] += dens
            # eng to'q (past value) markazni rgb sifatida saqlash
            if sum(c) < sum(e["rgb"]):
                e["rgb"] = tuple(int(x) for x in c)

        for name, e in sorted(agg.items(), key=lambda kv: -kv[1]["dens"]):
            pct = 100.0 * e["dens"] / total
            printed += pct
            if pct < min_pct:
                continue
            r, g, b = e["rgb"]
            ranglar.append({
                "rang": name,
                "pantone": e["pantone"],
                "qoplama_pct": round(pct, 1),
                "rgb": f"#{r:02x}{g:02x}{b:02x}",
            })

    warnings = []
    if is_mockup:
        warnings.append("Bu rasm tekis dizaynga o'xshamaydi (mahsulot fotosi/render?). "
                        "Aniq natija uchun tekis .cdr/vektor eksportini yuklang.")
    return {
        "oq_baza_pct": round(white_pct, 1),
        "printed_pct": round(printed, 1),
        "is_mockup": is_mockup,
        "warnings": warnings,
        "ranglar": ranglar,
    }


@frappe.whitelist()
def analyze(dizayn):
    """Pechat Dizayn hujjatidagi rasmni tahlil qilib natijani qaytaradi."""
    doc = frappe.get_doc("Pechat Dizayn", dizayn)
    if not doc.rasm:
        frappe.throw("Avval dizayn rasmini biriktiring (Расм).")
    file_doc = frappe.get_doc("File", {"file_url": doc.rasm})
    result = analyze_path(file_doc.get_full_path())

    ink_items = set(frappe.get_all("Item", filters={"item_group": "Сырьё - Печать"}, pluck="name"))
    for row in result["ranglar"]:
        row["mavjud_emas"] = 0 if row["rang"] in ink_items else 1
    return result
