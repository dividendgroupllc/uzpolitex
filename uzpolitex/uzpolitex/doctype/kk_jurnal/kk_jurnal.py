"""КК журнал — sifat nazorati (saralash). Excelda bu etap yuritilmagan —
jarayon foydalanuvchi ta'rifi bo'yicha (2026-09-19):
- Конверт - UH dagi tikilgan qop tekshiriladi;
- yaroqli → Пресс - UH (press uchastkasi skladi), Material Transfer;
- brak → dona hisobdan chiqib, «Брак коп» itemiga KG bilan kiradi (Repack,
  Отход склад - UH) — qiymati brak qop tannarxidan o'tadi.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, nowtime

KIRIM_WH = "Конверт - UH"
YAROQLI_WH = "Пресс - UH"
BRAK_ITEM = "Брак коп"
BRAK_WH = "Отход склад - UH"


class KKJurnal(Document):
	def validate(self):
		fill = [r for r in self.qatorlar if r.mahsulot or cint(r.yaroqli_sht) or cint(r.brak_sht)]
		if not fill:
			frappe.throw(_("Заполните хотя бы одну строку."))
		for i, r in enumerate(fill, 1):
			r.idx = i
			if r.konvert_jurnal:
				kj = frappe.get_cached_doc("Konvert Jurnal", r.konvert_jurnal)
				if kj.docstatus != 1:
					frappe.throw(
						_("Строка {0}: «{1}» ҳали тасдиқланмаган (Конверт ёзуви).").format(
							i, r.konvert_jurnal
						)
					)
				qoplar = [q.mahsulot for q in kj.qatorlar]
				if not r.mahsulot:
					if len(qoplar) == 1:
						r.mahsulot = qoplar[0]
					else:
						frappe.throw(
							_("Строка {0}: танланг қопни (Конверт ёзувида {1} та бор).").format(
								i, len(qoplar)
							)
						)
				elif r.mahsulot not in qoplar:
					frappe.throw(
						_("Строка {0}: «{1}» бу Конверт ёзувида йўқ.").format(i, r.mahsulot)
					)
			if not r.mahsulot:
				frappe.throw(_("Строка {0}: укажите қоп.").format(i))
			if not cint(r.yaroqli_sht) and not cint(r.brak_sht):
				frappe.throw(_("Строка {0} ({1}): яроқли ёки брак сонини киритинг.").format(i, r.mahsulot))
			if cint(r.brak_sht) and not flt(r.brak_kg):
				frappe.throw(_("Строка {0} ({1}): брак КГ ни киритинг.").format(i, r.mahsulot))
			r.tekshirildi_sht = cint(r.yaroqli_sht) + cint(r.brak_sht)
		self.qatorlar = fill
		self.jami_yaroqli = sum(cint(r.yaroqli_sht) for r in self.qatorlar)
		self.jami_brak_sht = sum(cint(r.brak_sht) for r in self.qatorlar)
		self.jami_brak_kg = flt(sum(flt(r.brak_kg) for r in self.qatorlar), 2)

	def on_submit(self):
		created = []
		# 1) yaroqli — bitta Material Transfer (Конверт -> Пресс)
		yaroqli = [r for r in self.qatorlar if cint(r.yaroqli_sht)]
		if yaroqli:
			se = self._se("Material Transfer")
			for r in yaroqli:
				se.append("items", {"item_code": r.mahsulot, "qty": cint(r.yaroqli_sht),
				                    "s_warehouse": KIRIM_WH, "t_warehouse": YAROQLI_WH})
			created.append(self._submit_se(se))
		# 2) brak — bitta Repack (qop dona -> Брак коп kg)
		brak = [r for r in self.qatorlar if cint(r.brak_sht)]
		if brak:
			se = self._se("Repack")
			for r in brak:
				se.append("items", {"item_code": r.mahsulot, "qty": cint(r.brak_sht),
				                    "s_warehouse": KIRIM_WH})
			se.append("items", {"item_code": BRAK_ITEM, "qty": flt(self.jami_brak_kg),
			                    "t_warehouse": BRAK_WH, "is_finished_item": 1})
			created.append(self._submit_se(se))
		self.db_set("stock_entries", ", ".join(created))

	def _se(self, turi):
		se = frappe.new_doc("Stock Entry")
		se.stock_entry_type = turi
		se.purpose = turi
		se.company = self.company
		se.posting_date = self.posting_date
		se.set_posting_time = 1
		se.posting_time = nowtime()
		se.uz_kk_jurnal = self.name
		se.uz_smena = self.smena
		se.uz_xodim = self.xodim
		return se

	def _submit_se(self, se):
		se.insert()
		nol = False
		for row in se.items:
			if not flt(row.basic_rate) and not flt(row.allow_zero_valuation_rate):
				row.allow_zero_valuation_rate = 1
				nol = True
		if nol:
			se.save()
		se.submit()
		return se.name

	def on_cancel(self):
		for name in frappe.get_all(
			"Stock Entry", filters={"uz_kk_jurnal": self.name, "docstatus": 1}, pluck="name"
		):
			frappe.get_doc("Stock Entry", name).cancel()
		self.db_set("stock_entries", None)


@frappe.whitelist()
def make_press(source_name):
	"""«Прессга ўтиш» tugmasi: saralash yozuvidan tayyor qatorli Press Jurnal
	(faqat yaroqli soni o'tadi)."""
	from frappe.model.mapper import get_mapped_doc

	def postprocess(source, target):
		for r in source.qatorlar:
			if cint(r.yaroqli_sht):
				target.append("qatorlar", {
					"kk_jurnal": source.name,
					"mahsulot": r.mahsulot,
					"sht": cint(r.yaroqli_sht),
				})

	return get_mapped_doc(
		"KK Jurnal",
		source_name,
		{
			"KK Jurnal": {
				"doctype": "Press Jurnal",
				"field_no_map": ["xodim", "xodim_nomi", "smena", "stock_entries", "posting_date"],
			}
		},
		None,
		postprocess,
	)


@frappe.whitelist()
def kk_malumot(kk_jurnal):
	"""JS uchun (Press jurnalida): saralash yozuvidagi yaroqli qoplar."""
	kk = frappe.get_doc("KK Jurnal", kk_jurnal)
	return {"qoplar": [{"mahsulot": r.mahsulot, "sht": cint(r.yaroqli_sht)}
	                   for r in kk.qatorlar if cint(r.yaroqli_sht)]}
