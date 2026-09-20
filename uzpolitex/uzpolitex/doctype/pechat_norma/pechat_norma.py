"""Печать норма — mahsulot uchun rang retsepti (gr / 1000 metr).

Boshlang'ich qiymatlar 14 oylik Excel tarixidan regressiya bilan hisoblangan
(taxminiy!), texnolog aniqlashtirib boradi. Pechat Jurnal smena faktini shu
normalar asosida norma×metr proporsiyasida mahsulotlarga taqsimlaydi.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class PechatNorma(Document):
	def validate(self):
		korilgan = set()
		for r in self.ranglar:
			if not flt(r.gr_1000m):
				frappe.throw(
					_("Строка {0} ({1}): укажите грамм на 1000 м.").format(r.idx, r.rang)
				)
			if r.rang in korilgan:
				frappe.throw(_("Краска «{0}» указана дважды.").format(r.rang))
			korilgan.add(r.rang)


def norma_map(mahsulot):
	"""{rang: gr_1000m} yoki bo'sh dict."""
	if not frappe.db.exists("Pechat Norma", mahsulot):
		return {}
	doc = frappe.get_cached_doc("Pechat Norma", mahsulot)
	return {r.rang: flt(r.gr_1000m) for r in doc.ranglar}
