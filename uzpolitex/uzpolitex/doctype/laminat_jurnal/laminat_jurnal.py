"""Ламинат журнал — Excel «Ламинат» listining o'rni. Bitta hujjat = bitta smena.

Excel formulalari (2026-09-06 tekshirilgan):
- Норма qoplama = (КГ chiqdi − Расх. КГ) → 82% Сырьё ламинат + 18% Добавочный
- Fakt (smenaga bir marta) mahsulotlarga NORMA proporsiyasida taqsimlanadi:
  fakt_i = norma_i / Σnorma × Σfakt; fakt kiritilmasa norma o'zi olinadi
- В 1 М(ГР) = КГ / Метр × 1000, norma Item.uz_norma_min/max (g/m)

Submit: har qatorga Stock Entry (Manufacture): rulon Ткацкий skladdan (metr),
qoplama siryosi Ламинант skladdan (kg), tayyor ламинат Ламинант skladga.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowtime

SIRYO_ULUSH = 0.82  # Excel: (G−J)×0.82
DP_ULUSH = 0.18

LAM_WAREHOUSE = "Ламинант - UH"
TK_WAREHOUSE = "Ткацкий - UH"
SIRYO_ITEM = "Сырьё ламинат"
DP_ITEM = "Добавочный.сырье"


def rasxod_default(mahsulot):
	"""'Ламинат Рулон-40' → 'Рулон-40'; 'Ламинат Лента рулон 50' → 'Лента-50'."""
	nom = (mahsulot or "").replace("Ламинат ", "", 1).strip()
	if nom.startswith("Лента рулон "):
		nom = "Лента-" + nom.replace("Лента рулон ", "", 1)
	return nom if frappe.db.exists("Item", nom) else None


class LaminatJurnal(Document):
	def validate(self):
		self._tozalash()
		self._qatorlarni_tekshir()
		self._hisobla()
		self._norma_nazorati()

	def _tozalash(self):
		fill = [r for r in self.qatorlar if flt(r.metr) or flt(r.kg)]
		if not fill:
			frappe.throw(_("Заполните хотя бы одну строку (Метр и КГ)."))
		for i, r in enumerate(fill, 1):
			r.idx = i
		self.qatorlar = fill

	def _qatorlarni_tekshir(self):
		for r in self.qatorlar:
			if not flt(r.kg):
				frappe.throw(_("Строка {0} ({1}): укажите КГ.").format(r.idx, r.mahsulot))
			if not flt(r.metr) and _metrda(r.mahsulot):
				frappe.throw(_("Строка {0} ({1}): укажите Метр.").format(r.idx, r.mahsulot))
			if not r.rasxod_mahsulot:
				r.rasxod_mahsulot = rasxod_default(r.mahsulot)
				if not r.rasxod_mahsulot:
					frappe.throw(
						_("Строка {0} ({1}): укажите расходуемый продукт.").format(r.idx, r.mahsulot)
					)
			else:
				# mahsulot keyin o'zgartirilsa rasxod eski holicha qolishi mumkin —
				# Excelda ataylab boshqa juftlik ham uchraydi (Лента рулон 50 ← Рулон-50),
				# shuning uchun bloklamaymiz, faqat ogohlantiramiz
				kutilgan = rasxod_default(r.mahsulot)
				if kutilgan and r.rasxod_mahsulot != kutilgan:
					frappe.msgprint(
						_("Строка {0}: для «{1}» обычно расходуется «{2}», выбрано «{3}» — проверьте.").format(
							r.idx, r.mahsulot, kutilgan, r.rasxod_mahsulot
						),
						indicator="orange",
						alert=True,
					)
			if not flt(r.rasxod_kg):
				frappe.throw(
					_("Строка {0} ({1}): укажите Расх. КГ (вес рулона).").format(r.idx, r.mahsulot)
				)
			if not flt(r.rasxod_metr) and _metrda(r.rasxod_mahsulot):
				frappe.throw(
					_("Строка {0} ({1}): укажите Расх. метр.").format(r.idx, r.mahsulot)
				)
			if flt(r.kg) < flt(r.rasxod_kg):
				frappe.msgprint(
					_("Строка {0}: КГ ({1}) меньше веса рулона ({2}) — покрытие отрицательное, проверьте.").format(
						r.idx, flt(r.kg), flt(r.rasxod_kg)
					),
					indicator="orange",
					alert=True,
				)

	def _hisobla(self):
		self.jami_metr = self.jami_kg = 0
		for r in self.qatorlar:
			qoplama = max(flt(r.kg) - flt(r.rasxod_kg), 0)
			r.norma_siryo = qoplama * SIRYO_ULUSH
			r.norma_dp = qoplama * DP_ULUSH
			r.v_1m = flt(r.kg) / flt(r.metr) * 1000 if flt(r.metr) else 0
			self.jami_metr += flt(r.metr)
			self.jami_kg += flt(r.kg)

		self.norma_siryo_jami = sum(flt(r.norma_siryo) for r in self.qatorlar)
		self.norma_dp_jami = sum(flt(r.norma_dp) for r in self.qatorlar)

		# fakt kiritilgan bo'lsa norma proporsiyasida taqsim, aks holda norma o'zi
		for r in self.qatorlar:
			r.siryo_kg = (
				flt(r.norma_siryo) / self.norma_siryo_jami * flt(self.fakt_siryo)
				if flt(self.fakt_siryo) and self.norma_siryo_jami
				else flt(r.norma_siryo)
			)
			r.dp_kg = (
				flt(r.norma_dp) / self.norma_dp_jami * flt(self.fakt_dp)
				if flt(self.fakt_dp) and self.norma_dp_jami
				else flt(r.norma_dp)
			)

		if not flt(self.fakt_siryo):
			frappe.msgprint(
				_("Факт Сырьё ламинат не введён — расход списан по норме ({0} кг).").format(
					frappe.format(self.norma_siryo_jami, "Float")
				),
				indicator="orange",
				alert=True,
			)

	def _norma_nazorati(self):
		normalar = {}
		buzilgan = []
		for r in self.qatorlar:
			if r.mahsulot not in normalar:
				normalar[r.mahsulot] = frappe.db.get_value(
					"Item", r.mahsulot, ["uz_norma_min", "uz_norma_max"], as_dict=True
				)
			n = normalar[r.mahsulot]
			if not n or not flt(n.uz_norma_max) or not flt(r.v_1m):
				continue
			mn, mx = flt(n.uz_norma_min), flt(n.uz_norma_max)
			if mn <= r.v_1m <= mx:
				continue
			if r.v_1m < mn:
				chetlanish = _("ниже нормы на {0}%").format(flt((1 - r.v_1m / mn) * 100, 1))
			else:
				chetlanish = _("выше нормы на {0}%").format(flt((1 - mx / r.v_1m) * 100, 1))
			buzilgan.append(
				_("{0}: В 1М = {1} г/м — {2} (норма {3}–{4})").format(
					r.mahsulot,
					frappe.format(r.v_1m, "Float"),
					chetlanish,
					frappe.format(mn, "Float"),
					frappe.format(mx, "Float"),
				)
			)
		if buzilgan:
			frappe.msgprint(
				"⚠️ " + "<br>".join(buzilgan), indicator="red", title=_("В 1 М(ГР) вне нормы")
			)

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
			se.uz_lam_jurnal = self.name
			se.uz_smena = self.smena
			se.uz_xodim = self.xodim
			fg_qty = flt(r.metr) if _metrda(r.mahsulot) else flt(r.kg)
			se.fg_completed_qty = fg_qty
			rasxod_qty = flt(r.rasxod_metr) if _metrda(r.rasxod_mahsulot) else flt(r.rasxod_kg)
			se.append(
				"items",
				{"item_code": r.rasxod_mahsulot, "qty": rasxod_qty, "s_warehouse": TK_WAREHOUSE},
			)
			for item, qty in ((SIRYO_ITEM, r.siryo_kg), (DP_ITEM, r.dp_kg)):
				if flt(qty):
					se.append(
						"items",
						{"item_code": item, "qty": flt(qty, 2), "s_warehouse": LAM_WAREHOUSE},
					)
			se.append(
				"items",
				{
					"item_code": r.mahsulot,
					"qty": fg_qty,
					"t_warehouse": LAM_WAREHOUSE,
					"is_finished_item": 1,
				},
			)
			se.insert()
			se.submit()
			created.append(se.name)

		self.db_set("stock_entries", ", ".join(created))

	def on_cancel(self):
		for name in frappe.get_all(
			"Stock Entry", filters={"uz_lam_jurnal": self.name, "docstatus": 1}, pluck="name"
		):
			frappe.get_doc("Stock Entry", name).cancel()
		self.db_set("stock_entries", None)


def _metrda(item_code):
	return frappe.db.get_value("Item", item_code, "stock_uom") == "Meter"


@frappe.whitelist()
def rasxod_mahsulot(mahsulot):
	"""JS uchun: mahsulotga mos rasxod itemi."""
	return rasxod_default(mahsulot)
