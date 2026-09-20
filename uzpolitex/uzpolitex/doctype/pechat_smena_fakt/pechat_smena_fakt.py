"""Печать смена факт — kraska sarfi SMENA uchun BIR MARTA yoziladigan joy.

Zavod fakti: kraska zakaz kesimida o'lchanmaydi, smena oxirida jami yoziladi.
Bu hujjat:
- shu (sana, smena) dagi jurnallarning AI hisobini jamlab ko'rsatadi (AI КГ),
- operator haqiqiy sarfni yozadi (Факт КГ), farq darhol ko'rinadi,
- submit'da g/m² kalibr HAQIQIY faktdan qayta hisoblanadi — keyingi
  zakazlarning AI normasi aniqlashib boradi.

Sklad jurnal SElari orqali AI qiymatlar bilan yuritiladi; bu hujjat nazorat
va kalibrovka uchun (sklad hujjati yaratmaydi).
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from uzpolitex.pechat import kalibr


def ai_jami(posting_date, smena, tashqari=None):
	"""Shu smenadagi submitted jurnallarning AI kraska jami {rang: kg}."""
	jurnallar = frappe.get_all(
		"Pechat Jurnal",
		filters={"posting_date": posting_date, "smena": smena, "docstatus": 1},
		pluck="name",
	)
	agg = {}
	if jurnallar:
		for r in frappe.get_all(
			"Pechat Jurnal Kraska",
			filters={"parent": ["in", jurnallar]},
			fields=["rang", "kg"],
		):
			agg[r.rang] = agg.get(r.rang, 0) + flt(r.kg)
	return agg


class PechatSmenaFakt(Document):
	def validate(self):
		self._yagona_smena()
		self._tozalash()
		self._ai_solishtir()
		self._hisobla()

	def _yagona_smena(self):
		bor = frappe.db.exists(
			"Pechat Smena Fakt",
			{
				"posting_date": self.posting_date,
				"smena": self.smena,
				"docstatus": ["<", 2],
				"name": ["!=", self.name],
			},
		)
		if bor:
			frappe.throw(
				_("Бу смена учун факт аллақачон киритилган: {0}").format(bor)
			)

	def _tozalash(self):
		fill = [r for r in self.ranglar if r.rang or flt(r.fakt_kg)]
		if not fill:
			frappe.throw(_("Камида битта ранг киритинг."))
		korilgan = set()
		for i, r in enumerate(fill, 1):
			r.idx = i
			if not r.rang:
				frappe.throw(_("Строка {0}: укажите краску.").format(i))
			if r.rang in korilgan:
				frappe.throw(
					_("Краска «{0}» указана дважды — объедините в одну строку.").format(r.rang)
				)
			korilgan.add(r.rang)
		self.ranglar = fill

	def _ai_solishtir(self):
		agg = ai_jami(self.posting_date, self.smena)
		borlar = set()
		for r in self.ranglar:
			r.ai_kg = flt(agg.get(r.rang, 0), 2)
			r.farq = flt(flt(r.fakt_kg) - r.ai_kg, 2)
			borlar.add(r.rang)
		# AI ishlatgan, operator yozmagan ranglar ham ko'rinsin
		for rang, kg in agg.items():
			if rang not in borlar:
				self.append("ranglar", {"rang": rang, "fakt_kg": 0,
				                        "ai_kg": flt(kg, 2), "farq": flt(-kg, 2)})
		if not agg:
			frappe.msgprint(
				_("Бу смена ({0}, {1}) учун журнал топилмади — AI устуни бўш.").format(
					frappe.format(self.posting_date, "Date"), self.smena
				),
				indicator="orange",
				alert=True,
			)

	def _hisobla(self):
		self.jami_fakt = sum(flt(r.fakt_kg) for r in self.ranglar)
		self.jami_ai = sum(flt(r.ai_kg) for r in self.ranglar)

	def on_submit(self):
		kalibr.recompute()

	def on_cancel(self):
		kalibr.recompute()


@frappe.whitelist()
def ai_hisob(posting_date, smena):
	"""JS: smena uchun AI kraska jami — jadvalni oldindan to'ldirish."""
	agg = ai_jami(posting_date, smena)
	return [{"rang": rang, "ai_kg": round(kg, 2)}
	        for rang, kg in sorted(agg.items(), key=lambda kv: -kv[1])]
