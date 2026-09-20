// Конверт журнал — topshiriq tanlanganda qop avto, rulon va metr avto, jonli jami.

frappe.ui.form.on("Konvert Jurnal", {
	setup(frm) {
		frm._uz_qoplar = {};
		frm.set_query("xodim", () => ({
			filters: { status: "Active", department: "Конверт - UH" },
		}));
		frm.set_query("pechat_jurnal", "qatorlar", () => ({
			filters: { docstatus: 1 },
		}));
		frm.set_query("topshiriq", "qatorlar", () => ({
			filters: { docstatus: ["<", 2] },
		}));
		frm.set_query("mahsulot", "qatorlar", (doc, cdt, cdn) => {
			const row = locals[cdt][cdn];
			if (row.topshiriq) {
				return { filters: { name: ["in", frm._uz_qoplar[row.topshiriq] || []] } };
			}
			return { filters: { item_group: "Готовый продукт - Конверт" } };
		});
		frm.set_query("rasxod_mahsulot", "qatorlar", () => ({
			filters: { item_group: "Полуфабрикат - Печать" },
		}));
	},

	refresh(frm) {
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__("ККга ўтиш (саралаш)"), () => {
				frappe.model.open_mapped_doc({
					method: "uzpolitex.uzpolitex.doctype.konvert_jurnal.konvert_jurnal.make_kk",
					frm: frm,
				});
			}).addClass("btn-primary");
		}
	},

	onload(frm) {
		if (frm.is_new() && !frm.doc.posting_date) {
			let sana = frappe.datetime.nowdate();
			if (frappe.datetime.now_time() < "09:00:00") {
				sana = frappe.datetime.add_days(sana, -1);
			}
			frm.set_value("posting_date", sana);
			frm.set_intro(__("Проверьте дату: ставится день НАЧАЛА смены (09:00)."), "yellow");
		}
		(frm.doc.qatorlar || []).forEach((r) => {
			if (r.topshiriq) uz_qoplar(frm, r.topshiriq);
		});
	},
});

async function uz_qoplar(frm, topshiriq) {
	if (frm._uz_qoplar[topshiriq]) return frm._uz_qoplar[topshiriq];
	const r = await frappe.xcall(
		"uzpolitex.uzpolitex.doctype.konvert_jurnal.konvert_jurnal.topshiriq_malumot",
		{ topshiriq }
	);
	frm._uz_qoplar[topshiriq] = r.qoplar || [];
	return frm._uz_qoplar[topshiriq];
}

frappe.ui.form.on("Konvert Jurnal Qator", {
	async pechat_jurnal(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.pechat_jurnal) return;
		const r = await frappe.xcall(
			"uzpolitex.uzpolitex.doctype.konvert_jurnal.konvert_jurnal.pechat_malumot",
			{ pechat_jurnal: row.pechat_jurnal }
		);
		row.mahsulot = r.mahsulot;
		row.topshiriq = r.topshiriq;
		row.rasxod_mahsulot = r.rasxod_mahsulot;
		row._boy_cm = r.boy_cm;
		row._zapas_cm = r.zapas_cm;
		row._metr_10000 = 0;
		uz_metr(row);
		frm.refresh_field("qatorlar");
		uz_hisobla(frm);
	},
	async topshiriq(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.topshiriq) return;
		const qoplar = await uz_qoplar(frm, row.topshiriq);
		row.mahsulot = qoplar.length === 1 ? qoplar[0] : null;
		if (row.mahsulot) await uz_malumot(frm, row);
		frm.refresh_field("qatorlar");
		uz_hisobla(frm);
	},
	async mahsulot(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row.mahsulot) await uz_malumot(frm, row);
		uz_hisobla(frm);
	},
	sht(frm, cdt, cdn) {
		uz_metr(locals[cdt][cdn]);
		uz_hisobla(frm);
	},
	kg(frm) {
		uz_hisobla(frm);
	},
	qatorlar_remove(frm) {
		uz_hisobla(frm);
	},
});

async function uz_malumot(frm, row) {
	const r = await frappe.xcall(
		"uzpolitex.uzpolitex.doctype.konvert_jurnal.konvert_jurnal.qator_malumot",
		{ mahsulot: row.mahsulot }
	);
	if (r.rasxod_mahsulot) row.rasxod_mahsulot = r.rasxod_mahsulot;
	row._metr_10000 = r.metr_10000;
	row._boy_cm = r.boy_cm;
	row._zapas_cm = r.zapas_cm;
	uz_metr(row);
	frm.refresh_field("qatorlar");
}

function uz_metr(row) {
	if (!cint(row.sht)) return;
	if (row._metr_10000) {
		row.rasxod_metr = flt((cint(row.sht) * row._metr_10000) / 10000, 2);
	} else if (row._boy_cm) {
		// zakaz qopi: dona × (bo'y + zapas) — taxminiy
		row.rasxod_metr = flt((cint(row.sht) * (row._boy_cm + (row._zapas_cm || 16))) / 100, 2);
	}
}

function uz_hisobla(frm) {
	let sht = 0,
		kg = 0,
		metr = 0;
	(frm.doc.qatorlar || []).forEach((r) => {
		r.gr_dona = cint(r.sht) ? (flt(r.kg) / cint(r.sht)) * 1000 : 0;
		sht += cint(r.sht);
		kg += flt(r.kg);
		metr += flt(r.rasxod_metr);
	});
	frm.refresh_field("qatorlar");
	frm.set_value("jami_sht", sht);
	frm.set_value("jami_kg", flt(kg, 2));
	frm.set_value("jami_metr", flt(metr, 2));
}
