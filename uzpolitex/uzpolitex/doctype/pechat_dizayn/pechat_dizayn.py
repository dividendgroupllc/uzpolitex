import frappe
from frappe.model.document import Document


class PechatDizayn(Document):
	def validate(self):
		# Qoplama % yig'indisi + oq baza 100% dan oshmasligi kerak (ogohlantirish)
		jami = sum((r.qoplama_pct or 0) for r in self.ranglar)
		if jami + (self.oq_baza_pct or 0) > 100.5:
			frappe.msgprint(
				f"Диққат: қоплама йиғиндиси ({jami:.1f}%) + оқ база ({self.oq_baza_pct or 0:.1f}%) "
				f"= {jami + (self.oq_baza_pct or 0):.1f}% — 100% дан ошди. Текширинг.",
				indicator="orange",
				title="Қоплама текшируви",
			)
