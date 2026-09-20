"""Резка журнал — ikkiga bo'lish etapi (Excelda alohida list yo'q edi).

Jarayon (foydalanuvchi 2026-09-06 tasdiqlagan):
- Laminatlangan rulon (Ламинат Рулон-X) ikkiga kesiladi → Ламинат Лента рулон X
- Metr ×2 bo'ladi, og'irlik (kg) o'zgarmaydi, otxod chiqmaydi
- Ламинат sexida bajariladi, smena operatori kiritadi

Submit: har qatorga Stock Entry (Repack): rulon Ламинант skladdan chiqadi,
lenta 2× metr bilan shu skladga kiradi. Qiymat zanjiri saqlanadi (rulon
qiymati lentaga o'tadi; hozircha zanjir $0 — Нитка tannarxi kiritilmagan).
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowtime

WAREHOUSE = "Ламинант - UH"
KESISH_KOEF = 2  # bitta rulon -> ikki lenta


def chiqim_default(kirim_mahsulot):
	"""'Ламинат Рулон-50' → 'Ламинат Лента рулон 50'."""
	nom = (kirim_mahsulot or "").strip()
	prefix = "Ламинат Рулон-"
	if not nom.startswith(prefix):
		return None
	lenta = "Ламинат Лента рулон " + nom.removeprefix(prefix)
	return lenta if frappe.db.exists("Item", lenta) else None


class RezkaJurnal(Document):
	def validate(self):
		self._tozalash()
		self._qatorlarni_tekshir()
		self._hisobla()

	def _tozalash(self):
		fill = [r for r in self.qatorlar if r.kirim_mahsulot or flt(r.kirim_metr) or flt(r.kg)]
		if not fill:
			frappe.throw(_("Заполните хотя бы одну строку."))
		for i, r in enumerate(fill, 1):
			r.idx = i
		self.qatorlar = fill

	def _qatorlarni_tekshir(self):
		for r in self.qatorlar:
			if not r.kirim_mahsulot:
				frappe.throw(_("Строка {0}: укажите порезанный рулон.").format(r.idx))
			if not flt(r.kirim_metr):
				frappe.throw(
					_("Строка {0} ({1}): укажите Метр.").format(r.idx, r.kirim_mahsulot)
				)
			if not flt(r.kg):
				frappe.throw(_("Строка {0} ({1}): укажите КГ.").format(r.idx, r.kirim_mahsulot))
			if not r.chiqim_mahsulot:
				r.chiqim_mahsulot = chiqim_default(r.kirim_mahsulot)
				if not r.chiqim_mahsulot:
					frappe.throw(
						_(
							"Строка {0}: для «{1}» не найдена лента — укажите полученную ленту вручную."
						).format(r.idx, r.kirim_mahsulot)
					)
			if r.chiqim_mahsulot == r.kirim_mahsulot:
				frappe.throw(
					_("Строка {0}: рулон и лента не могут совпадать.").format(r.idx)
				)

	def _hisobla(self):
		self.jami_kirim_metr = self.jami_chiqim_metr = self.jami_kg = 0
		for r in self.qatorlar:
			r.chiqim_metr = flt(r.kirim_metr) * KESISH_KOEF
			r.gr_1m = flt(r.kg) / r.chiqim_metr * 1000 if r.chiqim_metr else 0
			self.jami_kirim_metr += flt(r.kirim_metr)
			self.jami_chiqim_metr += r.chiqim_metr
			self.jami_kg += flt(r.kg)

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
			se.uz_rezka_jurnal = self.name
			se.uz_smena = self.smena
			se.uz_xodim = self.xodim
			se.append(
				"items",
				{"item_code": r.kirim_mahsulot, "qty": flt(r.kirim_metr), "s_warehouse": WAREHOUSE},
			)
			se.append(
				"items",
				{
					"item_code": r.chiqim_mahsulot,
					"qty": flt(r.chiqim_metr),
					"t_warehouse": WAREHOUSE,
					"is_finished_item": 1,
				},
			)
			se.insert()
			# qiymat zanjiri hozircha $0 (Нитка tannarxsiz) — nol narxga ruxsat
			nol = False
			for row in se.items:
				if not flt(row.basic_rate):
					row.allow_zero_valuation_rate = 1
					nol = True
			if nol:
				se.save()
			se.submit()
			created.append(se.name)

		self.db_set("stock_entries", ", ".join(created))

	def on_cancel(self):
		for name in frappe.get_all(
			"Stock Entry", filters={"uz_rezka_jurnal": self.name, "docstatus": 1}, pluck="name"
		):
			frappe.get_doc("Stock Entry", name).cancel()
		self.db_set("stock_entries", None)


@frappe.whitelist()
def chiqim_mahsulot(kirim_mahsulot):
	"""JS uchun: rulonga mos lenta."""
	return chiqim_default(kirim_mahsulot)
