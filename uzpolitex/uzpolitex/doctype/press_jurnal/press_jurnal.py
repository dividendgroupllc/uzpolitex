"""Пресс журнал — saralangan qoplarni kipalash. Excelda bu etap yuritilmagan
(Пресс лента faqat xarid qilingan, sarfi yozilmagan) — norma yo'q, operator
lenta sarfini o'zi kiritadi.

Submit: har qatorga SE Repack: qop (Пресс - UH) + Пресс лента (Конверт - UH)
→ o'sha qop ГП склад - UH ga (lenta qiymati qop tannarxiga qo'shiladi).
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, nowtime

KIRIM_WH = "Пресс - UH"
GP_WH = "ГП склад - UH"
LENTA_ITEM = "Пресс лента"
LENTA_WH = "Конверт - UH"


class PressJurnal(Document):
	def validate(self):
		fill = [r for r in self.qatorlar if r.mahsulot or cint(r.sht)]
		if not fill:
			frappe.throw(_("Заполните хотя бы одну строку."))
		for i, r in enumerate(fill, 1):
			r.idx = i
			if r.kk_jurnal:
				kk = frappe.get_cached_doc("KK Jurnal", r.kk_jurnal)
				if kk.docstatus != 1:
					frappe.throw(
						_("Строка {0}: «{1}» ҳали тасдиқланмаган (КК ёзуви).").format(i, r.kk_jurnal)
					)
				qoplar = [q.mahsulot for q in kk.qatorlar if cint(q.yaroqli_sht)]
				if not r.mahsulot:
					if len(qoplar) == 1:
						r.mahsulot = qoplar[0]
					else:
						frappe.throw(
							_("Строка {0}: танланг қопни (КК ёзувида {1} та бор).").format(
								i, len(qoplar)
							)
						)
				elif r.mahsulot not in qoplar:
					frappe.throw(
						_("Строка {0}: «{1}» бу КК ёзувида йўқ (ёки яроқлиси 0).").format(
							i, r.mahsulot
						)
					)
			if not r.mahsulot:
				frappe.throw(_("Строка {0}: укажите қоп.").format(i))
			if not cint(r.sht):
				frappe.throw(_("Строка {0} ({1}): укажите ШТ.").format(i, r.mahsulot))
		self.qatorlar = fill
		self.jami_sht = sum(cint(r.sht) for r in self.qatorlar)
		self.jami_kipa = sum(cint(r.kipa_soni) for r in self.qatorlar)
		self.jami_lenta_kg = flt(sum(flt(r.lenta_kg) for r in self.qatorlar), 2)

	def on_submit(self):
		created = []
		for r in self.qatorlar:
			se = frappe.new_doc("Stock Entry")
			se.stock_entry_type = "Repack"
			se.purpose = "Repack"
			se.company = self.company
			se.posting_date = self.posting_date
			se.set_posting_time = 1
			se.posting_time = nowtime()
			se.uz_press_jurnal = self.name
			se.uz_smena = self.smena
			se.uz_xodim = self.xodim
			se.append("items", {"item_code": r.mahsulot, "qty": cint(r.sht),
			                    "s_warehouse": KIRIM_WH})
			if flt(r.lenta_kg):
				se.append("items", {"item_code": LENTA_ITEM, "qty": flt(r.lenta_kg),
				                    "s_warehouse": LENTA_WH})
			se.append("items", {"item_code": r.mahsulot, "qty": cint(r.sht),
			                    "t_warehouse": GP_WH, "is_finished_item": 1})
			se.insert()
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

	def on_cancel(self):
		for name in frappe.get_all(
			"Stock Entry", filters={"uz_press_jurnal": self.name, "docstatus": 1}, pluck="name"
		):
			frappe.get_doc("Stock Entry", name).cancel()
		self.db_set("stock_entries", None)
