"""Конверт журнал — qop tikish etapi (birinchi DONA hisobidagi etap).

Jarayon (Excel «Конверт» listi tahlilidan):
- Bosilgan rulon (X Печать, Печать - UH skladda) qopga tikiladi
- Kirim: dona (ШТ) + og'irlik (КГ); rasxod rulon metri normadan hisoblanadi:
  Item.uz_metr_10000 — 10 000 dona qopga rulon metri (Excel yon jadvali),
  fakt bilan tekshirilgan: 35х50/40х50/45х50 → 6600, 45х62/50х62 → 8500,
  50х85 → 10000, 55х85/55х110 → 12500
- Rasxod mahsulot avto: nomdagi birinchi son → «Ламинат Рулон-NN Печать»

Submit: har qatorga Stock Entry (Manufacture): rulon Печать - UH dan chiqadi,
qop Конверт - UH ga kiradi (dona).
"""

import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, nowtime

RULON_WAREHOUSE = "Печать - UH"
QOP_WAREHOUSE = "Конверт - UH"
# zakaz qopi uchun rulon sarfi: dona × (bo'yi + zapas). Excel fakti: 50 sm
# qoplar 66 sm rulon oladi (klapan/chok + chiqit) — zapas ≈ 16 sm
ZAPAS_CM = 16


def rasxod_default(mahsulot):
	"""Zakaz qopi → o'zining bosma ruloni; eski umumiy qoplar → nomdagi
	birinchi son bo'yicha 'Ламинат Рулон-NN Печать'."""
	bosma = frappe.db.get_value("Item", mahsulot, "uz_bosma_rulon")
	if bosma and frappe.db.exists("Item", bosma):
		return bosma
	m = re.search(r"\d+", mahsulot or "")
	if not m:
		return None
	rulon = f"Ламинат Рулон-{m.group()} Печать"
	return rulon if frappe.db.exists("Item", rulon) else None


class KonvertJurnal(Document):
	def validate(self):
		self._tozalash()
		self._qatorlarni_tekshir()
		self._hisobla()

	def _tozalash(self):
		fill = [r for r in self.qatorlar if r.mahsulot or cint(r.sht) or flt(r.kg)]
		if not fill:
			frappe.throw(_("Заполните хотя бы одну строку."))
		for i, r in enumerate(fill, 1):
			r.idx = i
		self.qatorlar = fill

	def _qatorlarni_tekshir(self):
		for r in self.qatorlar:
			if r.pechat_jurnal:
				# bosma yozuvidan hammasi avto: qop, topshiriq, bosma rulon
				pj = frappe.get_cached_doc("Pechat Jurnal", r.pechat_jurnal)
				if pj.docstatus != 1:
					frappe.throw(
						_("Строка {0}: «{1}» ҳали тасдиқланмаган (Печать ёзуви).").format(
							r.idx, r.pechat_jurnal
						)
					)
				r.topshiriq = pj.topshiriq
				if not r.mahsulot:
					r.mahsulot = pj.qop_item
				elif r.mahsulot != pj.qop_item:
					frappe.throw(
						_("Строка {0}: «{1}» Печать ёзувидаги қопга мос эмас ({2}).").format(
							r.idx, r.mahsulot, pj.qop_item
						)
					)
				if not r.rasxod_mahsulot:
					r.rasxod_mahsulot = pj.bosma_rulon
			if r.topshiriq:
				t = frappe.get_cached_doc("Pechat Topshiriq", r.topshiriq)
				qoplar = [q.item for q in t.qoplar]
				if not r.mahsulot:
					if len(qoplar) == 1:
						r.mahsulot = qoplar[0]
					else:
						frappe.throw(
							_("Строка {0}: танланг қопни (топшириқда {1} та бор).").format(
								r.idx, len(qoplar)
							)
						)
				elif r.mahsulot not in qoplar:
					frappe.throw(
						_("Строка {0}: «{1}» бу топшириқда йўқ.").format(r.idx, r.mahsulot)
					)
			if not r.mahsulot:
				frappe.throw(_("Строка {0}: укажите мешок.").format(r.idx))
			if not cint(r.sht):
				frappe.throw(_("Строка {0} ({1}): укажите ШТ.").format(r.idx, r.mahsulot))
			if not flt(r.kg):
				frappe.throw(_("Строка {0} ({1}): укажите КГ.").format(r.idx, r.mahsulot))
			if not r.rasxod_mahsulot:
				r.rasxod_mahsulot = rasxod_default(r.mahsulot)
				if not r.rasxod_mahsulot:
					frappe.throw(
						_(
							"Строка {0}: для «{1}» не найден печатный рулон — укажите расход вручную."
						).format(r.idx, r.mahsulot)
					)
			if not flt(r.rasxod_metr):
				norma = flt(frappe.db.get_value("Item", r.mahsulot, "uz_metr_10000"))
				boy = flt(frappe.db.get_value("Item", r.mahsulot, "uz_boy_cm"))
				if norma:
					r.rasxod_metr = flt(cint(r.sht) * norma / 10000, 2)
				elif boy:
					# zakaz qopi: dona × (bo'y + zapas) — taxminiy, tahrirlash mumkin
					r.rasxod_metr = flt(cint(r.sht) * (boy + ZAPAS_CM) / 100, 2)
				else:
					frappe.throw(
						_(
							"Строка {0} ({1}): нет нормы «метр на 10 000 шт» — укажите Расход (М) вручную."
						).format(r.idx, r.mahsulot)
					)

	def _hisobla(self):
		self.jami_sht = self.jami_kg = self.jami_metr = 0
		for r in self.qatorlar:
			r.gr_dona = flt(r.kg) / cint(r.sht) * 1000 if cint(r.sht) else 0
			self.jami_sht += cint(r.sht)
			self.jami_kg += flt(r.kg)
			self.jami_metr += flt(r.rasxod_metr)

	def on_submit(self):
		created = []
		for r in self.qatorlar:
			se = frappe.new_doc("Stock Entry")
			se.stock_entry_type = "Manufacture"
			se.purpose = "Manufacture"
			se.company = self.company
			se.posting_date = self.posting_date
			se.set_posting_time = 1
			se.posting_time = nowtime()
			se.uz_konvert_jurnal = self.name
			se.uz_smena = self.smena
			se.uz_xodim = self.xodim
			se.append(
				"items",
				{
					"item_code": r.rasxod_mahsulot,
					"qty": flt(r.rasxod_metr),
					"s_warehouse": RULON_WAREHOUSE,
				},
			)
			se.append(
				"items",
				{
					"item_code": r.mahsulot,
					"qty": cint(r.sht),
					"t_warehouse": QOP_WAREHOUSE,
					"is_finished_item": 1,
				},
			)
			se.insert()
			# zanjir hali to'liq narxlanmagan bo'lsa — nol narxga ruxsat
			nol = False
			for row in se.items:
				if not flt(row.basic_rate) and not flt(row.allow_zero_valuation_rate):
					row.allow_zero_valuation_rate = 1
					nol = True
			if nol:
				se.save()
			se.submit()
			created.append(se.name)

		self.db_set("stock_entries", ", ".join(created))
		for nom in {r.topshiriq for r in self.qatorlar if r.topshiriq}:
			_tikuv_sync(nom)

	def on_cancel(self):
		for name in frappe.get_all(
			"Stock Entry", filters={"uz_konvert_jurnal": self.name, "docstatus": 1}, pluck="name"
		):
			frappe.get_doc("Stock Entry", name).cancel()
		self.db_set("stock_entries", None)
		for nom in {r.topshiriq for r in self.qatorlar if r.topshiriq}:
			_tikuv_sync(nom)


def _tikuv_sync(topshiriq_name):
	"""Topshiriq qoplariga tikilgan sonni yozadi; hammasi yetsa holat «Тайёр»."""
	t = frappe.get_doc("Pechat Topshiriq", topshiriq_name)
	jurnal_rows = frappe.get_all(
		"Konvert Jurnal Qator",
		filters={"topshiriq": topshiriq_name, "parenttype": "Konvert Jurnal"},
		fields=["parent", "mahsulot", "sht"],
	)
	tikildi = {}
	for jr in jurnal_rows:
		if frappe.db.get_value("Konvert Jurnal", jr.parent, "docstatus") == 1:
			tikildi[jr.mahsulot] = tikildi.get(jr.mahsulot, 0) + cint(jr.sht)

	hammasi = bool(t.qoplar)
	for q in t.qoplar:
		q.tikildi = tikildi.get(q.item, 0)
		if q.tikildi < cint(q.soni):
			hammasi = False

	if hammasi:
		t.holat = "Тайёр"
	elif t.holat == "Тайёр":
		# tikuv bekor qilindi — orqaga qaytadi
		t.holat = "В печати" if t.fakt else "Черновик"
	t.flags.ignore_validate_update_after_submit = True
	t.save(ignore_permissions=True)


@frappe.whitelist()
def qator_malumot(mahsulot):
	"""JS uchun: qopga mos rulon va metr normasi."""
	norma = frappe.db.get_value("Item", mahsulot, ["uz_metr_10000", "uz_boy_cm"], as_dict=True)
	return {
		"rasxod_mahsulot": rasxod_default(mahsulot),
		"metr_10000": flt(norma.uz_metr_10000) if norma else 0,
		"boy_cm": flt(norma.uz_boy_cm) if norma else 0,
		"zapas_cm": ZAPAS_CM,
	}


@frappe.whitelist()
def topshiriq_malumot(topshiriq):
	"""JS uchun: topshiriq qoplari."""
	t = frappe.get_doc("Pechat Topshiriq", topshiriq)
	return {"qoplar": [q.item for q in t.qoplar]}


@frappe.whitelist()
def make_kk(source_name):
	"""«ККга ўтиш» tugmasi: tikuv yozuvidan tayyor qatorli KK Jurnal
	(yaroqli soni tikilgan soniga teng qilib qo'yiladi — brakni operator ajratadi)."""
	from frappe.model.mapper import get_mapped_doc

	def postprocess(source, target):
		for r in source.qatorlar:
			target.append("qatorlar", {
				"konvert_jurnal": source.name,
				"mahsulot": r.mahsulot,
				"yaroqli_sht": cint(r.sht),
			})

	return get_mapped_doc(
		"Konvert Jurnal",
		source_name,
		{
			"Konvert Jurnal": {
				"doctype": "KK Jurnal",
				"field_no_map": ["xodim", "xodim_nomi", "smena", "stock_entries", "posting_date"],
			}
		},
		None,
		postprocess,
	)


@frappe.whitelist()
def konvert_malumot(konvert_jurnal):
	"""JS uchun (KK jurnalida): tikuv yozuvidagi qoplar."""
	kj = frappe.get_doc("Konvert Jurnal", konvert_jurnal)
	return {"qoplar": [{"mahsulot": r.mahsulot, "sht": cint(r.sht)} for r in kj.qatorlar]}


@frappe.whitelist()
def pechat_malumot(pechat_jurnal):
	"""JS uchun: bosma yozuvidan qop/rasxod/norma."""
	pj = frappe.get_doc("Pechat Jurnal", pechat_jurnal)
	boy = flt(frappe.db.get_value("Item", pj.qop_item, "uz_boy_cm"))
	return {
		"mahsulot": pj.qop_item,
		"topshiriq": pj.topshiriq,
		"rasxod_mahsulot": pj.bosma_rulon,
		"bosilgan_metr": flt(pj.metr),
		"boy_cm": boy,
		"zapas_cm": ZAPAS_CM,
	}
