"""Sex terminali (planshet) API — /terminal sahifasi uchun.

Pilot: Печать. Har planshet o'z sex useri bilan kiradi; user → etap mapping
shu yerda. Barcha og'ir mantiq mavjud doctype kontrollerlariga tayanadi —
terminal faqat minimal maydonlarni yuboradi, qolganini server to'ldiradi.
"""

import json

import frappe
from frappe import _
from frappe.utils import add_days, flt, nowdate, nowtime

STAGE_BY_USER = {
	"ekstruder@uzpolitex.uz": "ekstruder",
	"tkatskiy@uzpolitex.uz": "tkatskiy",
	"laminat@uzpolitex.uz": "laminat",
	"pechat@uzpolitex.uz": "pechat",
	"konvert@uzpolitex.uz": "konvert",
	"kk@uzpolitex.uz": "kk",
	"press@uzpolitex.uz": "press",
}

RUXSAT_ROLLAR = {"System Manager", "Оператор производства", "Начальник цеха"}


def _rol_tekshir():
	if not set(frappe.get_roles()) & RUXSAT_ROLLAR:
		frappe.throw(_("Терминалга рухсат йўқ."), frappe.PermissionError)


def stage_for_user():
	return STAGE_BY_USER.get(frappe.session.user)


def _smena_sana():
	"""09:00 qoidasi: 09:00 gacha — kechagi smena kuni."""
	sana = nowdate()
	if nowtime() < "09:00:00":
		sana = add_days(sana, -1)
	return sana


def _bin(item, wh):
	return flt(frappe.db.get_value("Bin", {"item_code": item, "warehouse": wh}, "actual_qty"))


def _xodimlar(dept):
	return frappe.get_all(
		"Employee", filters={"department": dept, "status": "Active"},
		fields=["name", "employee_name"], order_by="employee_name", ignore_permissions=True,
	)


@frappe.whitelist()
def holat(stage=None):
	"""Terminal bosh ekrani uchun hamma ma'lumot bitta so'rovda."""
	_rol_tekshir()
	stage = stage or stage_for_user() or "pechat"
	sana = _smena_sana()
	out = {"stage": stage, "sana": sana, "user": frappe.session.user}

	if stage == "konvert":
		return _konvert_holat(out)
	if stage == "kk":
		return _kk_holat(out)
	if stage == "press":
		return _press_holat(out)
	if stage == "tkatskiy":
		return _tkatskiy_holat(out)
	if stage == "laminat":
		return _laminat_holat(out)
	if stage == "ekstruder":
		return _ekstruder_holat(out)
	if stage != "pechat":
		out["tayyor_emas"] = True
		return out

	out["xodimlar"] = _xodimlar("Печать - UH")

	# NAVBAT: ochiq topshiriqlar
	navbat = []
	for t in frappe.get_all(
		"Pechat Topshiriq",
		filters={"docstatus": ["<", 2], "holat": ["!=", "Тайёр"]},
		fields=["name", "customer", "holat", "sana"],
		order_by="creation desc", limit=20, ignore_permissions=True,
	):
		tdoc = frappe.get_doc("Pechat Topshiriq", t.name)
		for q in tdoc.qoplar:
			item = frappe.db.get_value(
				"Item", q.item, ["uz_dizayn_old", "uz_en_cm", "uz_boy_cm", "uz_bosma_rulon"],
				as_dict=True) or frappe._dict()
			rasm = frappe.db.get_value("Pechat Dizayn", item.uz_dizayn_old, "rasm") if item.uz_dizayn_old else None
			kerak_metr = flt(q.soni) * flt(item.uz_boy_cm or 0) / 100
			bosildi = sum(flt(f.metr) for f in tdoc.fakt if f.qop == q.item)
			navbat.append({
				"topshiriq": t.name, "customer": t.customer, "holat": t.holat,
				"qop": q.item, "soni": q.soni, "tikildi": q.tikildi,
				"rasm": rasm, "kerak_metr": round(kerak_metr),
				"bosildi_metr": round(bosildi),
			})
	out["navbat"] = navbat

	# BALANS: laminat rulonlar + kraskalar
	rulonlar = []
	for it in frappe.get_all("Item", filters={"item_group": "Полуфабрикат - Ламинант"},
	                         pluck="name", ignore_permissions=True):
		qty = _bin(it, "Ламинант - UH")
		if qty > 0:
			rulonlar.append({"item": it, "qty": round(qty), "birlik": "м"})
	kraskalar = []
	for b in frappe.get_all("Bin", filters={"warehouse": "Печать - UH", "actual_qty": [">", 0]},
	                        fields=["item_code", "actual_qty"], ignore_permissions=True):
		if frappe.db.get_value("Item", b.item_code, "item_group") == "Сырьё - Печать":
			kraskalar.append({"item": b.item_code, "qty": round(flt(b.actual_qty), 1), "birlik": "кг"})
	out["rulonlar"] = sorted(rulonlar, key=lambda x: x["item"])
	out["kraskalar"] = sorted(kraskalar, key=lambda x: -x["qty"])

	# BUGUN: jurnallar + СМФ
	out["bugun"] = frappe.get_all(
		"Pechat Jurnal",
		filters={"posting_date": sana, "docstatus": ["<", 2]},
		fields=["name", "smena", "qop_item", "metr", "jami_kraska_kg", "docstatus"],
		order_by="creation desc", ignore_permissions=True,
	)
	out["smf_bugun"] = frappe.get_all(
		"Pechat Smena Fakt",
		filters={"posting_date": sana, "docstatus": ["<", 2]},
		fields=["name", "smena", "jami_fakt", "jami_ai", "docstatus"],
		ignore_permissions=True,
	)
	return out


def _rasm(qop_item):
	dz = frappe.db.get_value("Item", qop_item, "uz_dizayn_old")
	return frappe.db.get_value("Pechat Dizayn", dz, "rasm") if dz else None


def _bugun_jurnal(doctype, sana, child_dt, child_map):
	"""Bugungi hujjatlar + qatorlar qisqacha."""
	docs = frappe.get_all(
		doctype, filters={"posting_date": sana, "docstatus": ["<", 2]},
		fields=["name", "smena", "docstatus"], order_by="creation desc",
		ignore_permissions=True,
	)
	for d in docs:
		rows = frappe.get_all(child_dt, filters={"parent": d.name},
		                      fields=list(child_map), ignore_permissions=True)
		d["izoh"] = "; ".join(
			" ".join(str(r.get(f) or "") for f in child_map) for r in rows[:3])
	return docs


def _konvert_holat(out):
	out["xodimlar"] = _xodimlar("Конверт - UH")
	navbat, korilgan = [], set()
	for pj in frappe.get_all(
		"Pechat Jurnal", filters={"docstatus": 1},
		fields=["name", "qop_item", "bosma_rulon", "metr", "topshiriq", "customer"],
		order_by="creation desc", limit=40, ignore_permissions=True,
	):
		if not pj.bosma_rulon or pj.bosma_rulon in korilgan:
			continue
		korilgan.add(pj.bosma_rulon)
		qoldiq = _bin(pj.bosma_rulon, "Печать - UH")
		if qoldiq <= 0:
			continue
		boy = flt(frappe.db.get_value("Item", pj.qop_item, "uz_boy_cm"))
		navbat.append({
			"pechat_jurnal": pj.name, "qop": pj.qop_item, "customer": pj.customer,
			"qoldiq_metr": round(qoldiq), "rasm": _rasm(pj.qop_item),
			"taxmin_dona": int(qoldiq / ((boy + 16) / 100)) if boy else 0,
		})
	out["navbat"] = navbat
	out["balans"] = [
		{"item": b.item_code, "qty": round(flt(b.actual_qty)), "birlik": "м"}
		for b in frappe.get_all("Bin", filters={"warehouse": "Печать - UH", "actual_qty": [">", 0]},
		                        fields=["item_code", "actual_qty"], ignore_permissions=True)
		if b.item_code != "Брак коп"
		and frappe.db.get_value("Item", b.item_code, "item_group") == "Полуфабрикат - Печать"
	]
	out["bugun"] = _bugun_jurnal("Konvert Jurnal", out["sana"],
	                             "Konvert Jurnal Qator", ["mahsulot", "sht"])
	return out


def _kk_holat(out):
	out["xodimlar"] = _xodimlar("Контроль качества - UH") or _xodimlar("Конверт - UH")
	navbat = []
	for kj in frappe.get_all(
		"Konvert Jurnal", filters={"docstatus": 1}, fields=["name"],
		order_by="creation desc", limit=25, ignore_permissions=True,
	):
		for r in frappe.get_all("Konvert Jurnal Qator", filters={"parent": kj.name},
		                        fields=["mahsulot", "sht"], ignore_permissions=True):
			stok = _bin(r.mahsulot, "Конверт - UH")
			if stok <= 0:
				continue
			navbat.append({
				"konvert_jurnal": kj.name, "qop": r.mahsulot,
				"tikildi": r.sht, "stok": round(stok), "rasm": _rasm(r.mahsulot),
			})
	out["navbat"] = navbat[:20]
	out["balans"] = [
		{"item": b.item_code, "qty": round(flt(b.actual_qty)), "birlik": "шт"}
		for b in frappe.get_all("Bin", filters={"warehouse": "Конверт - UH", "actual_qty": [">", 0]},
		                        fields=["item_code", "actual_qty"], ignore_permissions=True)
		if frappe.db.get_value("Item", b.item_code, "item_group") == "Готовый продукт - Конверт"
	]
	out["bugun"] = _bugun_jurnal("KK Jurnal", out["sana"],
	                             "KK Jurnal Qator", ["mahsulot", "yaroqli_sht", "brak_sht"])
	return out


def _press_holat(out):
	out["xodimlar"] = _xodimlar("Конверт - UH")
	navbat = []
	for kk in frappe.get_all(
		"KK Jurnal", filters={"docstatus": 1}, fields=["name"],
		order_by="creation desc", limit=25, ignore_permissions=True,
	):
		for r in frappe.get_all("KK Jurnal Qator", filters={"parent": kk.name},
		                        fields=["mahsulot", "yaroqli_sht"], ignore_permissions=True):
			if not flt(r.yaroqli_sht):
				continue
			stok = _bin(r.mahsulot, "Пресс - UH")
			if stok <= 0:
				continue
			navbat.append({
				"kk_jurnal": kk.name, "qop": r.mahsulot,
				"yaroqli": r.yaroqli_sht, "stok": round(stok), "rasm": _rasm(r.mahsulot),
			})
	out["navbat"] = navbat[:20]
	balans = [
		{"item": b.item_code, "qty": round(flt(b.actual_qty)), "birlik": "шт"}
		for b in frappe.get_all("Bin", filters={"warehouse": "Пресс - UH", "actual_qty": [">", 0]},
		                        fields=["item_code", "actual_qty"], ignore_permissions=True)
	]
	balans.append({"item": "Пресс лента", "qty": round(_bin("Пресс лента", "Конверт - UH"), 1), "birlik": "кг"})
	out["balans"] = balans
	out["bugun"] = _bugun_jurnal("Press Jurnal", out["sana"],
	                             "Press Jurnal Qator", ["mahsulot", "sht", "kipa_soni"])
	return out


def _tkatskiy_holat(out):
	out["xodimlar"] = _xodimlar("Ткацкий - UH")
	out["balans"] = [{"item": "Нитка", "qty": round(_bin("Нитка", "Экструдор - UH")), "birlik": "кг"}]
	out["mahsulotlar"] = frappe.get_all(
		"Item", filters={"item_group": "Полуфабрикат - Ткацкий"}, pluck="name",
		order_by="name", ignore_permissions=True)
	out["bugun"] = frappe.get_all(
		"Tkatskiy Jurnal", filters={"posting_date": out["sana"], "docstatus": ["<", 2]},
		fields=["name", "smena", "docstatus", "jami_metr", "jami_kg"],
		order_by="creation desc", ignore_permissions=True)
	for d in out["bugun"]:
		d["izoh"] = f"{round(flt(d.jami_metr))} м · {round(flt(d.jami_kg))} кг"
	return out


def _laminat_holat(out):
	from uzpolitex.uzpolitex.doctype.laminat_jurnal.laminat_jurnal import rasxod_default

	out["xodimlar"] = _xodimlar("Ламинант - UH")
	navbat = []
	for it in frappe.get_all("Item", filters={"item_group": "Полуфабрикат - Ламинант"},
	                         pluck="name", order_by="name", ignore_permissions=True):
		src = rasxod_default(it)
		navbat.append({
			"qop": it, "src": src,
			"src_stok": round(_bin(src, "Ткацкий - UH")) if src else 0,
		})
	out["navbat"] = navbat
	out["balans"] = [
		{"item": "Сырьё ламинат", "qty": round(_bin("Сырьё ламинат", "Ламинант - UH") + _bin("Сырьё ламинат", "Сырьевой склад - UH")), "birlik": "кг"},
		{"item": "Добавочный.сырье", "qty": round(_bin("Добавочный.сырье", "Ламинант - UH") + _bin("Добавочный.сырье", "Сырьевой склад - UH")), "birlik": "кг"},
	] + [
		{"item": b.item_code, "qty": round(flt(b.actual_qty)), "birlik": "м"}
		for b in frappe.get_all("Bin", filters={"warehouse": "Ткацкий - UH", "actual_qty": [">", 0]},
		                        fields=["item_code", "actual_qty"], ignore_permissions=True)
	]
	out["bugun"] = _bugun_jurnal("Laminat Jurnal", out["sana"],
	                             "Laminat Jurnal Qator", ["mahsulot", "metr"])
	return out


def _ekstruder_holat(out):
	out["xodimlar"] = _xodimlar("Экструдор - UH")
	out["navbat"] = [
		{"stanok": w.name, "warehouse": w.warehouse}
		for w in frappe.get_all("Workstation", filters={"uz_bolim": "Экструдор - UH"},
		                        fields=["name", "warehouse"], order_by="name", ignore_permissions=True)
	]
	balans = []
	for it in frappe.get_all("Item", filters={"item_group": "Сырьё - Экструдор"},
	                         pluck="name", ignore_permissions=True):
		q = _bin(it, "Экструдор - UH") + _bin(it, "Сырьевой склад - UH")
		if q > 0:
			balans.append({"item": it, "qty": round(q), "birlik": "кг"})
	balans.append({"item": "Нитка (тайёр)", "qty": round(_bin("Нитка", "Экструдор - UH")), "birlik": "кг"})
	out["balans"] = balans
	out["bugun"] = frappe.get_all(
		"Stock Entry",
		filters={"posting_date": out["sana"], "purpose": "Manufacture",
		         "docstatus": ["<", 2], "uz_stanok": ["is", "set"]},
		fields=["name", "uz_smena as smena", "uz_stanok", "fg_completed_qty", "uz_sht", "docstatus"],
		order_by="creation desc", ignore_permissions=True)
	for d in out["bugun"]:
		d["izoh"] = f"{d.uz_stanok} · {round(flt(d.fg_completed_qty))} кг · {d.uz_sht or 0} шт"
	return out


@frappe.whitelist()
def tkatskiy_qatorlar(dan, gacha):
	"""Diapazon uchun qatorlar + har stanokning oxirgi mahsuloti."""
	_rol_tekshir()
	from uzpolitex.uzpolitex.doctype.tkatskiy_jurnal.tkatskiy_jurnal import oxirgi_mahsulotlar

	dan, gacha = int(dan), int(gacha)
	if not (0 < dan <= gacha <= 70):
		frappe.throw(_("Диапазон нотўғри (1–70)."))
	stanoklar = list(range(dan, gacha + 1))
	oxirgi = oxirgi_mahsulotlar(stanoklar) or {}
	return [{"stanok": s, "mahsulot": oxirgi.get(s) or oxirgi.get(str(s)) or ""} for s in stanoklar]


@frappe.whitelist()
def tkatskiy_yoz(smena, xodim, qatorlar):
	"""Ткацкий smena jurnali (qoralama) — to'ldirilgan qatorlargina olinadi."""
	_rol_tekshir()
	if isinstance(qatorlar, str):
		qatorlar = json.loads(qatorlar)
	rows = [q for q in qatorlar if flt(q.get("metr")) or flt(q.get("kg"))]
	if not rows:
		frappe.throw(_("Ҳеч бўлмаса битта станокка метр/кг киритинг."))
	doc = frappe.get_doc({
		"doctype": "Tkatskiy Jurnal", "posting_date": _smena_sana(),
		"smena": smena, "xodim": xodim,
		"qatorlar": [{"stanok": int(q["stanok"]), "mahsulot": q.get("mahsulot"),
		              "metr": flt(q.get("metr")), "kg": flt(q.get("kg")),
		              "nitka_kg": flt(q.get("kg")),
		              "vyrabotka_pm": flt(q.get("vyrabotka_pm"))} for q in rows],
	})
	doc.insert()
	return {"name": doc.name, "qatorlar": len(doc.qatorlar),
	        "jami_metr": doc.jami_metr, "jami_kg": doc.jami_kg}


@frappe.whitelist()
def laminat_yoz(mahsulot, metr, kg, rasxod_kg, smena, xodim, rasxod_metr=None):
	"""Ламинат yozuvi (qoralama). rasxod_metr bo'sh bo'lsa = metr (1:1)."""
	_rol_tekshir()
	doc = frappe.get_doc({
		"doctype": "Laminat Jurnal", "posting_date": _smena_sana(),
		"smena": smena, "xodim": xodim,
		"qatorlar": [{"mahsulot": mahsulot, "metr": flt(metr), "kg": flt(kg),
		              "rasxod_kg": flt(rasxod_kg),
		              "rasxod_metr": flt(rasxod_metr) or flt(metr)}],
	})
	doc.insert()
	r = doc.qatorlar[0]
	return {"name": doc.name, "qop": r.mahsulot, "rasxod": r.rasxod_mahsulot,
	        "rasxod_metr": r.rasxod_metr, "siryo": round(flt(r.siryo_kg), 1),
	        "dp": round(flt(r.dp_kg), 1), "v_1m": round(flt(r.v_1m), 1)}


@frappe.whitelist()
def ekstruder_yoz(stanok, kg, sht, namotka, smena, xodim):
	"""Экструдор yozuvi (qoralama SE): BOM'dan materiallar avto, boshliq faktga
	tuzatib submit qiladi."""
	_rol_tekshir()
	bom = frappe.db.get_value("BOM", {"item": "Нитка", "is_active": 1, "docstatus": 1}, "name")
	wh = frappe.db.get_value("Workstation", stanok, "warehouse") or "Экструдор - UH"
	se = frappe.new_doc("Stock Entry")
	se.stock_entry_type = "Manufacture"
	se.purpose = "Manufacture"
	se.company = "Uzpolitex Holding"
	se.posting_date = _smena_sana()
	se.set_posting_time = 1
	se.posting_time = nowtime()
	se.from_bom = 1
	se.bom_no = bom
	se.fg_completed_qty = flt(kg)
	se.from_warehouse = wh
	se.to_warehouse = wh
	se.uz_stanok = stanok
	se.uz_smena = smena
	se.uz_xodim = xodim
	se.uz_sht = int(flt(sht))
	se.uz_namotka = flt(namotka)
	se.get_items()
	se.insert()
	return {"name": se.name, "kg": flt(kg), "sht": int(flt(sht)),
	        "materiallar": [{"item": i.item_code, "qty": round(flt(i.qty), 1)}
	                        for i in se.items if not i.is_finished_item]}


@frappe.whitelist()
def konvert_yoz(pechat_jurnal, sht, kg, smena, xodim):
	"""Tikuv yozuvi (qoralama) — bosma yozuvidan."""
	_rol_tekshir()
	doc = frappe.get_doc({
		"doctype": "Konvert Jurnal", "posting_date": _smena_sana(),
		"smena": smena, "xodim": xodim,
		"qatorlar": [{"pechat_jurnal": pechat_jurnal, "sht": int(flt(sht)), "kg": flt(kg)}],
	})
	doc.insert()
	r = doc.qatorlar[0]
	return {"name": doc.name, "qop": r.mahsulot, "rasxod": r.rasxod_mahsulot,
	        "rasxod_metr": r.rasxod_metr, "gr_dona": round(flt(r.gr_dona), 1)}


@frappe.whitelist()
def kk_yoz(konvert_jurnal, yaroqli_sht, brak_sht, brak_kg, smena, xodim, mahsulot=None):
	"""Saralash yozuvi (qoralama)."""
	_rol_tekshir()
	doc = frappe.get_doc({
		"doctype": "KK Jurnal", "posting_date": _smena_sana(),
		"smena": smena, "xodim": xodim,
		"qatorlar": [{"konvert_jurnal": konvert_jurnal, "mahsulot": mahsulot,
		              "yaroqli_sht": int(flt(yaroqli_sht)), "brak_sht": int(flt(brak_sht)),
		              "brak_kg": flt(brak_kg)}],
	})
	doc.insert()
	r = doc.qatorlar[0]
	return {"name": doc.name, "qop": r.mahsulot, "yaroqli": r.yaroqli_sht,
	        "brak": r.brak_sht, "brak_kg": r.brak_kg}


@frappe.whitelist()
def press_yoz(kk_jurnal, sht, kipa_soni, lenta_kg, smena, xodim, mahsulot=None):
	"""Kipalash yozuvi (qoralama)."""
	_rol_tekshir()
	doc = frappe.get_doc({
		"doctype": "Press Jurnal", "posting_date": _smena_sana(),
		"smena": smena, "xodim": xodim,
		"qatorlar": [{"kk_jurnal": kk_jurnal, "mahsulot": mahsulot,
		              "sht": int(flt(sht)), "kipa_soni": int(flt(kipa_soni)),
		              "lenta_kg": flt(lenta_kg)}],
	})
	doc.insert()
	r = doc.qatorlar[0]
	return {"name": doc.name, "qop": r.mahsulot, "sht": r.sht,
	        "kipa": r.kipa_soni, "lenta": r.lenta_kg}


@frappe.whitelist()
def pechat_yoz(topshiriq, metr, smena, xodim, qop_item=None):
	"""Bosma yozuvi (qoralama) — server qolganini to'ldiradi.
	Submit'ni Начальник Desk'da qiladi."""
	_rol_tekshir()
	doc = frappe.get_doc({
		"doctype": "Pechat Jurnal",
		"posting_date": _smena_sana(),
		"smena": smena,
		"xodim": xodim,
		"topshiriq": topshiriq,
		"qop_item": qop_item,
		"metr": flt(metr),
	})
	doc.insert()
	return {
		"name": doc.name,
		"qop": doc.qop_item,
		"rasxod": doc.rasxod_mahsulot,
		"bosma": doc.bosma_rulon,
		"kraskalar": [{"rang": k.rang, "kg": k.kg} for k in doc.kraskalar],
	}


@frappe.whitelist()
def smf_ai(smena):
	"""СМФ formasi uchun: shu smena AI jami."""
	_rol_tekshir()
	from uzpolitex.uzpolitex.doctype.pechat_smena_fakt.pechat_smena_fakt import ai_jami

	agg = ai_jami(_smena_sana(), smena)
	return [{"rang": r, "ai_kg": round(k, 2)} for r, k in sorted(agg.items(), key=lambda kv: -kv[1])]


@frappe.whitelist()
def smf_yoz(smena, ranglar):
	"""Smena kraska fakti (qoralama)."""
	_rol_tekshir()
	if isinstance(ranglar, str):
		ranglar = json.loads(ranglar)
	doc = frappe.get_doc({
		"doctype": "Pechat Smena Fakt",
		"posting_date": _smena_sana(),
		"smena": smena,
		"ranglar": [{"rang": r["rang"], "fakt_kg": flt(r["fakt_kg"])} for r in ranglar if flt(r.get("fakt_kg"))],
	})
	doc.insert()
	return {
		"name": doc.name,
		"qatorlar": [{"rang": r.rang, "fakt_kg": r.fakt_kg, "ai_kg": r.ai_kg, "farq": r.farq}
		             for r in doc.ranglar],
	}
