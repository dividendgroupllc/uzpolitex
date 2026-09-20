"""Печать журнал — bitta zakaz-qop bosmasi (Sales Order/Топшириқ asosida).

Kraska bu yerda AI/dizayn bo'yicha AVTO hisoblanadi (operator xohlasa
tuzatadi) — sklad shu qiymatlar bilan yuritiladi. HAQIQIY smena sarfi
alohida «Pechat Smena Fakt» hujjatida BIR MARTA yoziladi va shu smenadagi
jurnallarning AI jamisi bilan solishtiriladi; g/m² kalibr ham o'sha real
faktdan hisoblanadi.

Submit: SE Manufacture: laminat rulon (Ламинант - UH, metr 1:1) + kraska
(Печать - UH) → shu zakazning BOSMA RULONI (Печать - UH). Topshiriqqa fakt
yoziladi, holat «В печати».
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowtime

from uzpolitex.pechat import kalibr, rulon

LAM_WAREHOUSE = "Ламинант - UH"
PECHAT_WAREHOUSE = "Печать - UH"


def rang_kutilgan(qop_item, metr):
	"""Zakazning har rangga kutilgan sarfi (kg): dizayn qoplamasi ×
	metrdagi qop soni × kalibrlangan g/m²."""
	from uzpolitex.pechat.order_ink import _component_area_m2

	item = frappe.get_cached_doc("Item", qop_item)
	boy_m = flt(item.get("uz_boy_cm")) / 100.0
	if not boy_m or not flt(metr):
		return {}
	qoplar_soni = flt(metr) / boy_m
	gm2 = kalibr.get_gm2()
	agg = {}
	for komp, dizayn in (("Олд", item.get("uz_dizayn_old")),
	                     ("Орқа", item.get("uz_dizayn_orqa")),
	                     ("Лента", item.get("uz_dizayn_lenta"))):
		if not dizayn:
			continue
		area = _component_area_m2(item, komp)
		if area <= 0:
			continue
		d = frappe.get_cached_doc("Pechat Dizayn", dizayn)
		for r in d.ranglar:
			if r.rang:
				agg[r.rang] = agg.get(r.rang, 0) + \
					flt(r.qoplama_pct) / 100.0 * area * qoplar_soni * gm2 / 1000.0
	return agg


class PechatJurnal(Document):
	def validate(self):
		self._topshiriqni_tekshir()
		self._rulonlarni_toldir()
		self._kraskalarni_toldir()
		self._hisobla()

	def _topshiriqni_tekshir(self):
		t = frappe.get_doc("Pechat Topshiriq", self.topshiriq)
		qoplar = [q.item for q in t.qoplar]
		if not self.qop_item:
			if len(qoplar) == 1:
				self.qop_item = qoplar[0]
			else:
				frappe.throw(_("Қопни танланг (топшириқда {0} та қоп бор).").format(len(qoplar)))
		if self.qop_item not in qoplar:
			frappe.throw(
				_("«{0}» бу топшириқда йўқ. Топшириқ қоплари: {1}").format(
					self.qop_item, ", ".join(qoplar)
				)
			)
		# metr buyurtma ehtiyojidan oshib ketmasin (metr ≠ dona chalkashuvi!)
		soni = next((q.soni for q in t.qoplar if q.item == self.qop_item), 0)
		boy = flt(frappe.db.get_value("Item", self.qop_item, "uz_boy_cm"))
		if soni and boy and flt(self.metr):
			kerak = soni * boy / 100
			bosildi = sum(flt(j.metr) for j in frappe.get_all(
				"Pechat Jurnal",
				filters={"topshiriq": self.topshiriq, "qop_item": self.qop_item,
				         "docstatus": 1, "name": ["!=", self.name]},
				fields=["metr"]))
			if bosildi + flt(self.metr) > kerak * 1.25:
				frappe.msgprint(
					_("⚠️ Буюртма {0} дона × {1} см ≈ {2} м рулон талаб қилади "
					  "(босилгани {3} м + сиз киритган {4} м). МЕТР киритилаётганига "
					  "ишонч ҳосил қилинг — дона эмас!").format(
						soni, frappe.format(boy, "Float"),
						frappe.format(flt(kerak, 0), "Float"),
						frappe.format(bosildi, "Float"),
						frappe.format(flt(self.metr), "Float")),
					indicator="red",
					title=_("Метр буюртмадан кўп"),
				)

	def _rulonlarni_toldir(self):
		if not flt(self.metr):
			frappe.throw(_("Босилган метрни киритинг."))
		self.rasxod_metr = flt(self.metr)
		if not self.rasxod_mahsulot:
			en = frappe.db.get_value("Item", self.qop_item, "uz_en_cm")
			self.rasxod_mahsulot = rulon.laminat_rulon(en)
			if not self.rasxod_mahsulot:
				frappe.throw(
					_("«{0}» учун ламинат рулон топилмади — расходни қўлда танланг.").format(
						self.qop_item
					)
				)
		self.bosma_rulon = rulon.bosma_rulon(self.qop_item)

	def _kraskalarni_toldir(self):
		# bo'sh bo'lsa — AI/dizayndan avto (server zaxira; JS ham to'ldiradi)
		if not self.kraskalar:
			for rang, kg in sorted(rang_kutilgan(self.qop_item, self.metr).items(),
			                       key=lambda kv: -kv[1]):
				if kg >= 0.005:
					self.append("kraskalar", {"rang": rang, "kg": flt(kg, 2)})
		korilgan = set()
		for k in self.kraskalar:
			if not k.rang:
				frappe.throw(_("Краска, строка {0}: укажите краску.").format(k.idx))
			if not flt(k.kg):
				frappe.throw(_("Краска, строка {0} ({1}): укажите КГ.").format(k.idx, k.rang))
			if k.rang in korilgan:
				frappe.throw(
					_("Краска «{0}» указана дважды — объедините в одну строку.").format(k.rang)
				)
			korilgan.add(k.rang)
		# QOIDA: jurnal jadvali = sklad chiqimi. Skladda yetmagan rang jadvalda
		# QOLMAYDI (aks holda jurnal bilan sklad farqlanadi)
		qoldi, chiqdi = [], []
		for k in self.kraskalar:
			bor = flt(frappe.db.get_value(
				"Bin", {"item_code": k.rang, "warehouse": PECHAT_WAREHOUSE}, "actual_qty"))
			if bor < flt(k.kg):
				chiqdi.append(f"{k.rang} (керак {flt(k.kg)}, бор {bor})")
			else:
				qoldi.append(k)
		if chiqdi:
			for i, k in enumerate(qoldi, 1):
				k.idx = i
			self.kraskalar = qoldi
			frappe.msgprint(
				_("Печать складда етарли бўлмагани учун жадвалдан чиқарилди: {0}. "
				  "Керак бўлса складчи кирим қилсин ва журнални қайта сақланг.").format(
					", ".join(chiqdi)),
				indicator="orange",
			)

	def _hisobla(self):
		self.jami_kraska_kg = sum(flt(k.kg) for k in self.kraskalar)

	def on_submit(self):
		se = frappe.new_doc("Stock Entry")
		se.stock_entry_type = "Manufacture"
		se.purpose = "Manufacture"
		se.company = self.company
		se.posting_date = self.posting_date
		se.set_posting_time = 1
		se.posting_time = nowtime()
		se.uz_pechat_jurnal = self.name
		se.uz_smena = self.smena
		se.uz_xodim = self.xodim
		se.append(
			"items",
			{
				"item_code": self.rasxod_mahsulot,
				"qty": flt(self.rasxod_metr),
				"s_warehouse": LAM_WAREHOUSE,
			},
		)
		for k in self.kraskalar:
			# validate skladda yetmaganlarni chiqargan — jadval = sklad chiqimi
			se.append(
				"items",
				{"item_code": k.rang, "qty": flt(k.kg), "s_warehouse": PECHAT_WAREHOUSE},
			)
		se.append(
			"items",
			{
				"item_code": self.bosma_rulon,
				"qty": flt(self.metr),
				"t_warehouse": PECHAT_WAREHOUSE,
				"is_finished_item": 1,
			},
		)
		se.insert()
		nol = False
		for row in se.items:
			if not flt(row.basic_rate) and not flt(row.allow_zero_valuation_rate):
				row.allow_zero_valuation_rate = 1
				nol = True
		if nol:
			se.save()
		se.submit()
		self.db_set("stock_entries", se.name)

		_topshiriq_sync(self.topshiriq)
		kalibr.recompute()

	def on_cancel(self):
		for name in frappe.get_all(
			"Stock Entry", filters={"uz_pechat_jurnal": self.name, "docstatus": 1}, pluck="name"
		):
			frappe.get_doc("Stock Entry", name).cancel()
		self.db_set("stock_entries", None)
		_topshiriq_sync(self.topshiriq)
		kalibr.recompute()


def _topshiriq_sync(topshiriq_name):
	"""Topshiriq faktini submitted jurnallardan to'liq qayta quradi (idempotent)."""
	t = frappe.get_doc("Pechat Topshiriq", topshiriq_name)
	jurnallar = frappe.get_all(
		"Pechat Jurnal",
		filters={"topshiriq": topshiriq_name, "docstatus": 1},
		fields=["name", "posting_date", "smena", "qop_item", "metr", "jami_kraska_kg"],
		order_by="posting_date, creation",
	)
	t.set("fakt", [])
	for j in jurnallar:
		t.append("fakt", {
			"jurnal": j.name, "sana": j.posting_date, "smena": j.smena,
			"qop": j.qop_item, "metr": j.metr, "kraska_kg": j.jami_kraska_kg})

	fakt_rang = {}
	if jurnallar:
		for r in frappe.get_all(
			"Pechat Jurnal Kraska",
			filters={"parent": ["in", [j.name for j in jurnallar]]},
			fields=["rang", "kg"],
		):
			fakt_rang[r.rang] = fakt_rang.get(r.rang, 0) + flt(r.kg)

	borlar = set()
	for row in t.kraska_reja:
		row.fakt_kg = flt(fakt_rang.get(row.rang, 0), 2)
		borlar.add(row.rang)
	for rang, kg in fakt_rang.items():
		if rang not in borlar:
			t.append("kraska_reja", {"rang": rang, "turi": "Режадан ташқари",
			                         "reja_kg": 0, "fakt_kg": flt(kg, 2)})

	if jurnallar and t.holat == "Черновик":
		t.holat = "В печати"
	elif not jurnallar and t.holat == "В печати":
		t.holat = "Черновик"
	t.flags.ignore_validate_update_after_submit = True
	t.save(ignore_permissions=True)


@frappe.whitelist()
def topshiriq_malumot(topshiriq):
	"""JS: topshiriq qoplari ro'yxati."""
	t = frappe.get_doc("Pechat Topshiriq", topshiriq)
	return {"qoplar": [q.item for q in t.qoplar]}


@frappe.whitelist()
def qop_malumot(qop_item):
	"""JS: qop tanlanganda rulon takliflari."""
	en = frappe.db.get_value("Item", qop_item, "uz_en_cm")
	return {
		"rasxod_mahsulot": rulon.laminat_rulon(en),
		"bosma_rulon": frappe.db.get_value("Item", qop_item, "uz_bosma_rulon"),
	}


@frappe.whitelist()
def make_konvert(source_name):
	"""«Конвертга ўтиш» tugmasi: bosma yozuvidan tayyor qatorli Konvert Jurnal."""
	from frappe.model.mapper import get_mapped_doc

	def postprocess(source, target):
		target.append("qatorlar", {
			"pechat_jurnal": source.name,
			"topshiriq": source.topshiriq,
			"mahsulot": source.qop_item,
			"rasxod_mahsulot": source.bosma_rulon,
		})

	return get_mapped_doc(
		"Pechat Jurnal",
		source_name,
		{
			"Pechat Jurnal": {
				"doctype": "Konvert Jurnal",
				"field_no_map": ["xodim", "xodim_nomi", "smena", "stock_entries", "posting_date"],
			}
		},
		None,
		postprocess,
	)


@frappe.whitelist()
def kraska_default(qop_item, metr):
	"""JS: bosilgan metr uchun AI/dizayn bo'yicha kutilgan kraska."""
	return [{"rang": rang, "kg": round(kg, 2)}
	        for rang, kg in sorted(rang_kutilgan(qop_item, metr).items(), key=lambda kv: -kv[1])
	        if kg >= 0.005]
