"""Ткацкий журнал — smena mastri kiritadigan hujjat (Excel jurnalining o'rnini bosadi).

Bitta hujjat = bitta xodim-smena. Ichida stanok qatorlari (№, mahsulot, metr, kg,
nitka). Submit bo'lganda mahsulot boshiga standart Stock Entry (Manufacture)
avtomatik yaratiladi va submit qilinadi: Нитка Ткацкий skladdan chiqadi,
mahsulot metrda Ткацкий skladga kiradi.

Nazoratlar (Excel bilan bir xil):
- 1М(ГР) = КГ / Метр × 1000, mahsulot normasi Item.uz_norma_min/max (g/m)
- normadan chiqsa stanok raqami bilan qizil ogohlantirish (bloklamaydi)
- nitka bo'sh bo'lsa avtomatik = КГ (Excel formulasi I=H)
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowtime

STANOK_MAX = 70
TK_WAREHOUSE = "Ткацкий - UH"
NITKA_ITEM = "Нитка"
# Excelda sexlararo transfer yo'q (Перемещ. listida 0 ta nitka yozuvi) —
# nitka Экструдорда yotadi, Ткацкий to'g'ridan-to'g'ri sarflaydi (user 2026-09-06)
NITKA_WAREHOUSE = "Экструдор - UH"


class TkatskiyJurnal(Document):
	def validate(self):
		self._tozalash()
		self._qatorlarni_tekshir()
		self._hisobla()
		self._norma_nazorati()

	def _tozalash(self):
		"""Diapazon bilan ochilgan, lekin to'ldirilmagan qatorlarni olib tashlash."""
		fill = [r for r in self.qatorlar if flt(r.metr) or flt(r.kg) or flt(r.nitka_kg)]
		if not fill:
			frappe.throw(_("Заполните хотя бы один станок (Метр и КГ)."))
		for i, r in enumerate(fill, 1):
			r.idx = i
		self.qatorlar = fill

	def _qatorlarni_tekshir(self):
		seen = set()
		for r in self.qatorlar:
			if not (1 <= (r.stanok or 0) <= STANOK_MAX):
				frappe.throw(_("Строка {0}: № станка должен быть от 1 до {1}.").format(r.idx, STANOK_MAX))
			if r.stanok in seen:
				frappe.throw(_("Станок {0} указан дважды.").format(r.stanok))
			seen.add(r.stanok)
			if not flt(r.metr) or not flt(r.kg):
				frappe.throw(
					_("Станок {0}: укажите и Метр, и КГ (сейчас: {1} м / {2} кг).").format(
						r.stanok, flt(r.metr), flt(r.kg)
					)
				)
			if not flt(r.nitka_kg):
				r.nitka_kg = flt(r.kg)  # Excel: Нитка = КГ (1:1)

	def _hisobla(self):
		self.jami_metr = self.jami_kg = self.jami_nitka = 0
		for r in self.qatorlar:
			r.gr_1m = flt(r.kg) / flt(r.metr) * 1000 if flt(r.metr) else 0
			self.jami_metr += flt(r.metr)
			self.jami_kg += flt(r.kg)
			self.jami_nitka += flt(r.nitka_kg)

	def _norma_nazorati(self):
		normalar = {}
		buzilgan = []
		for r in self.qatorlar:
			if r.mahsulot not in normalar:
				normalar[r.mahsulot] = frappe.db.get_value(
					"Item", r.mahsulot, ["uz_norma_min", "uz_norma_max"], as_dict=True
				)
			n = normalar[r.mahsulot]
			if not n or not flt(n.uz_norma_max):
				continue
			mn, mx = flt(n.uz_norma_min), flt(n.uz_norma_max)
			if mn <= r.gr_1m <= mx:
				continue
			# Excel: Отклонение мин = 1 − M/min; Отклонение макс = 1 − max/M
			if r.gr_1m < mn:
				chetlanish = _("ниже нормы на {0}%").format(flt((1 - r.gr_1m / mn) * 100, 1))
			else:
				chetlanish = _("выше нормы на {0}%").format(flt((1 - mx / r.gr_1m) * 100, 1))
			buzilgan.append(
				_("Станок {0}: {1} = {2} г/м — {3} (норма {4}–{5})").format(
					r.stanok,
					r.mahsulot,
					frappe.format(r.gr_1m, "Float"),
					chetlanish,
					frappe.format(mn, "Float"),
					frappe.format(mx, "Float"),
				)
			)
		if buzilgan:
			frappe.msgprint(
				"⚠️ " + "<br>".join(buzilgan),
				indicator="red",
				title=_("1М (ГР) вне нормы"),
			)

	def on_submit(self):
		created = []
		for mahsulot in sorted({r.mahsulot for r in self.qatorlar}):
			rows = [r for r in self.qatorlar if r.mahsulot == mahsulot]
			se = frappe.new_doc("Stock Entry")
			se.stock_entry_type = "Manufacture"
			se.purpose = "Manufacture"
			se.company = self.company
			se.posting_date = self.posting_date
			se.set_posting_time = 1
			se.posting_time = nowtime()
			se.uz_jurnal = self.name
			se.uz_smena = self.smena
			se.uz_xodim = self.xodim
			se.fg_completed_qty = sum(flt(r.metr) for r in rows)
			se.append(
				"items",
				{
					"item_code": NITKA_ITEM,
					"qty": sum(flt(r.nitka_kg) for r in rows),
					"s_warehouse": NITKA_WAREHOUSE,
				},
			)
			se.append(
				"items",
				{
					"item_code": mahsulot,
					"qty": sum(flt(r.metr) for r in rows),
					"t_warehouse": TK_WAREHOUSE,
					"is_finished_item": 1,
				},
			)
			se.insert()
			se.submit()
			created.append(se.name)

		self.db_set("stock_entries", ", ".join(created))

	def on_cancel(self):
		for name in frappe.get_all(
			"Stock Entry", filters={"uz_jurnal": self.name, "docstatus": 1}, pluck="name"
		):
			frappe.get_doc("Stock Entry", name).cancel()
		self.db_set("stock_entries", None)


@frappe.whitelist()
def oxirgi_mahsulotlar(stanoklar):
	"""Har stanok oxirgi marta qaysi mahsulotni to'qiganini qaytaradi
	(97% hollarda mahsulot o'zgarmaydi — avto to'ldirish uchun)."""
	import json

	if isinstance(stanoklar, str):
		stanoklar = json.loads(stanoklar)
	if not stanoklar:
		return {}
	rows = frappe.db.sql(
		"""
		select q.stanok, q.mahsulot
		from `tabTkatskiy Jurnal Qator` q
		join `tabTkatskiy Jurnal` j on j.name = q.parent
		where j.docstatus < 2 and q.stanok in %(stanoklar)s
		order by j.posting_date desc, j.creation desc
		""",
		{"stanoklar": tuple(stanoklar)},
		as_dict=True,
	)
	result = {}
	for r in rows:
		if r.stanok not in result:
			result[r.stanok] = r.mahsulot
	return result
