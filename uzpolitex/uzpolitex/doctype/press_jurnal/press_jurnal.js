// Пресс журнал — kipalash: jonli jami, 09:00 sana qoidasi.

frappe.ui.form.on("Press Jurnal", {
	setup(frm) {
		frm.set_query("xodim", () => ({
			filters: { status: "Active", department: "Конверт - UH" },
		}));
		frm.set_query("kk_jurnal", "qatorlar", () => ({
			filters: { docstatus: 1 },
		}));
		frm.set_query("mahsulot", "qatorlar", () => ({
			filters: { item_group: "Готовый продукт - Конверт" },
		}));
	},
	onload(frm) {
		if (frm.is_new() && !frm.doc.posting_date) {
			let sana = frappe.datetime.nowdate();
			if (frappe.datetime.now_time() < "09:00:00") sana = frappe.datetime.add_days(sana, -1);
			frm.set_value("posting_date", sana);
			frm.set_intro(__("Проверьте дату: ставится день НАЧАЛА смены (09:00)."), "yellow");
		}
	},
});

frappe.ui.form.on("Press Jurnal Qator", {
	async kk_jurnal(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.kk_jurnal) return;
		const r = await frappe.xcall(
			"uzpolitex.uzpolitex.doctype.kk_jurnal.kk_jurnal.kk_malumot",
			{ kk_jurnal: row.kk_jurnal }
		);
		if (r.qoplar && r.qoplar.length === 1) {
			row.mahsulot = r.qoplar[0].mahsulot;
			if (!cint(row.sht)) row.sht = r.qoplar[0].sht;
		}
		frm.refresh_field("qatorlar");
		uz_jami(frm);
	},
	sht: uz_jami,
	kipa_soni: uz_jami,
	lenta_kg: uz_jami,
	qatorlar_remove: uz_jami,
});

function uz_jami(frm) {
	let sht = 0, kipa = 0, lenta = 0;
	(frm.doc.qatorlar || []).forEach((r) => {
		sht += cint(r.sht);
		kipa += cint(r.kipa_soni);
		lenta += flt(r.lenta_kg);
	});
	frm.set_value("jami_sht", sht);
	frm.set_value("jami_kipa", kipa);
	frm.set_value("jami_lenta_kg", flt(lenta, 2));
}
