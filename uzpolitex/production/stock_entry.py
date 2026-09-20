"""Stock Entry (Manufacture) — Uzpolitex ishlab chiqarish validatsiyalari.

Excel tahlilidan kelib chiqqan chegaralar:
- В 1 ШТ normasi Item'da saqlanadi (uz_norma_min/uz_norma_max, Нитка: 1.1–1.5)
- Разница uchun Excelda norma yo'q; 95% yozuvlar ±5 kg ichida bo'lgan,
  shuning uchun ±5 kg dan katta chetlanishda ogohlantirish (bloklamaydi).
"""

import frappe
from frappe import _
from frappe.utils import flt

RAZNITSA_WARN_KG = 5.0


def validate(doc, method=None):
	if doc.purpose != "Manufacture":
		return
	if (
		doc.get("uz_jurnal")
		or doc.get("uz_lam_jurnal")
		or doc.get("uz_pechat_jurnal")
		or doc.get("uz_konvert_jurnal")
	):
		# Jurnaldan yaratilgan (Ткацкий/Ламинат/Печать/Конверт): FG metrda/donada — В 1 ШТ
		# va Разница bu yerda ma'nosiz, g/m nazorati jurnalning o'zida bajarilgan
		_allow_zero_rate_for_scrap(doc)
		return
	_compute_v_1_sht(doc)
	_compute_raznitsa(doc)
	_allow_zero_rate_for_scrap(doc)


def _fg_row(doc):
	for row in doc.get("items") or []:
		if row.get("is_finished_item"):
			return row
	return None


def _compute_v_1_sht(doc):
	doc.uz_v_1_sht = 0
	fg = _fg_row(doc)
	if not fg:
		return

	if not doc.get("uz_sht"):
		frappe.msgprint(
			_("ШТ (кол-во намоток) не указано — контроль «В 1 ШТ» не выполняется."),
			indicator="orange",
			alert=True,
		)
		return

	doc.uz_v_1_sht = flt(fg.qty) / doc.uz_sht

	norma = frappe.db.get_value(
		"Item", fg.item_code, ["uz_norma_min", "uz_norma_max"], as_dict=True
	)
	if not norma or not flt(norma.uz_norma_max):
		return

	if not (flt(norma.uz_norma_min) <= doc.uz_v_1_sht <= flt(norma.uz_norma_max)):
		frappe.msgprint(
			_("⚠️ В 1 ШТ = {0} кг — вне нормы ({1}–{2} кг)! Проверьте КГ и ШТ.").format(
				frappe.format(doc.uz_v_1_sht, "Float"),
				frappe.format(flt(norma.uz_norma_min), "Float"),
				frappe.format(flt(norma.uz_norma_max), "Float"),
			),
			indicator="red",
			title=_("В 1 ШТ вне нормы"),
		)


def _compute_raznitsa(doc):
	"""Massa balansi: (GP + otxod) − siryo sarfi.

	Excel formulasi (D − PP − CaCO3 − MB + Отход) bilan bir xil ma'no, farqi —
	bu yerda Вторичка ham sarf sifatida hisobga olinadi (Excelda e'tibordan
	chetda qolgan edi).
	"""
	incoming = 0.0
	outgoing = 0.0
	for row in doc.get("items") or []:
		if row.t_warehouse and not row.s_warehouse:
			incoming += flt(row.transfer_qty or row.qty)
		elif row.s_warehouse and not row.t_warehouse:
			outgoing += flt(row.transfer_qty or row.qty)

	doc.uz_raznitsa = flt(incoming - outgoing, 2)

	if doc.get("items") and abs(doc.uz_raznitsa) > RAZNITSA_WARN_KG:
		frappe.msgprint(
			_(
				"Разница = {0} кг (выход минус расход). Обычно в пределах ±{1} кг — "
				"проверьте расход сырья и отход."
			).format(frappe.format(doc.uz_raznitsa, "Float"), int(RAZNITSA_WARN_KG)),
			indicator="orange",
			title=_("Большая разница"),
		)


def _allow_zero_rate_for_scrap(doc):
	# v16: scrap/secondary qator secondary_item_type bilan belgilanadi;
	# narxi BOM'dagi cost_allocation_per dan hisoblanadi (bizda 0 — otxod bepul)
	for row in doc.get("items") or []:
		if not (row.get("secondary_item_type") or row.get("is_legacy_scrap_item")):
			continue
		if not flt(row.basic_rate):
			row.allow_zero_valuation_rate = 1
		# otxod itemning o'z default skladiga tushsin (masalan, Отход склад),
		# aks holda umumiy to_warehouse'da qolib ketadi
		default_wh = frappe.db.get_value(
			"Item Default",
			{"parent": row.item_code, "company": doc.company},
			"default_warehouse",
		)
		if default_wh:
			row.t_warehouse = default_wh
