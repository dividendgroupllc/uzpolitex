// Uzpolitex — Stock Entry (Manufacture) uchun operator qulayliklari:
// stanokdan sklad/bo'lim avto, xodimlar bo'lim bo'yicha filtr,
// В 1 ШТ hisoblash, norma buzilsa qizil ogohlantirish.

frappe.ui.form.on("Stock Entry", {
	setup(frm) {
		frm.set_query("uz_xodim", () => {
			const filters = { status: "Active" };
			if (frm._uz_bolim) {
				filters.department = frm._uz_bolim;
			} else if (frm.doc.purpose === "Manufacture") {
				// qo'lda Manufacture faqat Экструдорда (qolgan etaplar jurnal orqali)
				filters.department = "Экструдор - UH";
			}
			return { filters };
		});
	},

	refresh(frm) {
		uz_manufacture_defaults(frm);
		uz_load_stanok_info(frm);
		uz_headline(frm);
		uz_raznitsa_calc(frm);
	},

	purpose(frm) {
		uz_manufacture_defaults(frm);
	},

	uz_stanok(frm) {
		uz_load_stanok_info(frm, true);
	},

	fg_completed_qty(frm) {
		uz_update_v1sht(frm);
		// core get_items materiallarni serverdan qayta to'ldiradi — tugagach hisoblash
		setTimeout(() => uz_raznitsa_calc(frm), 1500);
	},

	uz_sht(frm) {
		uz_update_v1sht(frm);
	},

	items_remove(frm) {
		uz_raznitsa_calc(frm);
	},
});

// Разница jonli hisoblanadi (Excel: =D-I-J-K+M) — operator jadvalda fakt
// sarfni o'zgartirishi bilan yangilanadi, saqlaganda server qayta tekshiradi.
frappe.ui.form.on("Stock Entry Detail", {
	qty(frm) {
		uz_raznitsa_calc(frm);
	},
	s_warehouse(frm) {
		uz_raznitsa_calc(frm);
	},
	t_warehouse(frm) {
		uz_raznitsa_calc(frm);
	},
});

function uz_manufacture_defaults(frm) {
	if (!frm.is_new() || frm.doc.purpose !== "Manufacture") return;

	if (!frm.doc.from_bom) frm.set_value("from_bom", 1);

	// sana tahrirlanadigan bo'lsin — operator smenani ertasiga ham kiritadi
	if (!frm.doc.set_posting_time) frm.set_value("set_posting_time", 1);

	// smena 09:00 da boshlanadi: 09:00 gacha kiritilayotgan bo'lsa bu hali
	// KECHA boshlangan smena — sanani kechaga qo'yamiz. Boshqa holatda operator
	// sanani o'zi tekshiradi (intro eslatma).
	if (!frm._uz_date_set) {
		frm._uz_date_set = true;
		if (frappe.datetime.now_time() < "09:00:00") {
			frm.set_value(
				"posting_date",
				frappe.datetime.add_days(frappe.datetime.nowdate(), -1)
			);
		}
		frm.set_intro(
			__("Проверьте дату: ставится день НАЧАЛА смены (09:00)."),
			"yellow"
		);
	}

	uz_default_bom(frm);
}

function uz_default_bom(frm) {
	// hozircha bitta retsept (Нитка) — operator qidirmasin, avto tanlansin;
	// retseptlar ko'payganda operator o'zi tanlaydi
	if (frm.doc.bom_no) return;
	frappe.db
		.get_list("BOM", { filters: { is_active: 1, is_default: 1, docstatus: 1 }, limit: 2 })
		.then((rows) => {
			if (rows.length === 1 && !frm.doc.bom_no) {
				frm.set_value("bom_no", rows[0].name);
			}
		});
}

function uz_load_stanok_info(frm, set_warehouses) {
	frm._uz_bolim = null;
	if (!frm.doc.uz_stanok) return;
	frappe.db
		.get_value("Workstation", frm.doc.uz_stanok, ["warehouse", "uz_bolim"])
		.then((r) => {
			const d = (r && r.message) || {};
			frm._uz_bolim = d.uz_bolim || null;
			if (set_warehouses && d.warehouse && frm.doc.docstatus === 0) {
				if (!frm.doc.from_warehouse) frm.set_value("from_warehouse", d.warehouse);
				if (!frm.doc.to_warehouse) frm.set_value("to_warehouse", d.warehouse);
			}
		});
}

function uz_raznitsa_calc(frm) {
	// Excel: Разница = КГ − ПП − Кальций − МБ + Отход, ya'ni kirim − chiqim
	// (skladga kirayotgan qatorlar minus skladdan chiqayotgan qatorlar)
	if (frm.doc.purpose !== "Manufacture" || frm.doc.docstatus !== 0) return;
	let incoming = 0,
		outgoing = 0;
	(frm.doc.items || []).forEach((r) => {
		if (r.t_warehouse && !r.s_warehouse) incoming += flt(r.qty);
		else if (r.s_warehouse && !r.t_warehouse) outgoing += flt(r.qty);
	});
	const value = flt(incoming - outgoing, 2);
	if (flt(frm.doc.uz_raznitsa) !== value) {
		frm.set_value("uz_raznitsa", value);
	}
}

function uz_update_v1sht(frm) {
	if (frm.doc.purpose !== "Manufacture") return;
	const kg = flt(frm.doc.fg_completed_qty);
	const sht = cint(frm.doc.uz_sht);
	frm.set_value("uz_v_1_sht", sht ? kg / sht : 0).then(() => uz_headline(frm));
}

async function uz_headline(frm) {
	if (frm.doc.purpose !== "Manufacture" || !flt(frm.doc.uz_v_1_sht)) return;

	const item_code = await uz_fg_item(frm);
	if (!item_code) return;

	if (!frm._uz_norma || frm._uz_norma.item !== item_code) {
		const r = await frappe.db.get_value("Item", item_code, [
			"uz_norma_min",
			"uz_norma_max",
		]);
		frm._uz_norma = Object.assign({ item: item_code }, (r && r.message) || {});
	}

	const n = frm._uz_norma;
	if (!flt(n.uz_norma_max)) return;

	const v = flt(frm.doc.uz_v_1_sht);
	if (v < flt(n.uz_norma_min) || v > flt(n.uz_norma_max)) {
		frm.dashboard.set_headline(
			`<span class="indicator-pill red">В 1 ШТ = ${v.toFixed(3)} кг — вне нормы (${n.uz_norma_min}–${n.uz_norma_max} кг)!</span>`
		);
	} else {
		frm.dashboard.clear_headline();
	}
}

async function uz_fg_item(frm) {
	const fg = (frm.doc.items || []).find((r) => r.is_finished_item);
	if (fg) return fg.item_code;
	if (frm.doc.bom_no) {
		if (!frm._uz_bom_item || frm._uz_bom_item.bom !== frm.doc.bom_no) {
			const r = await frappe.db.get_value("BOM", frm.doc.bom_no, "item");
			frm._uz_bom_item = { bom: frm.doc.bom_no, item: r?.message?.item };
		}
		return frm._uz_bom_item.item;
	}
	return null;
}
