// КК журнал — saralash: jonli jami, 09:00 sana qoidasi.

frappe.ui.form.on("KK Jurnal", {
	setup(frm) {
		frm.set_query("xodim", () => ({
			filters: { status: "Active", department: "Контроль качества - UH" },
		}));
		frm.set_query("konvert_jurnal", "qatorlar", () => ({
			filters: { docstatus: 1 },
		}));
		frm.set_query("mahsulot", "qatorlar", () => ({
			filters: { item_group: "Готовый продукт - Конверт" },
		}));
	},
	refresh(frm) {
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__("Прессга ўтиш (кипалаш)"), () => {
				frappe.model.open_mapped_doc({
					method: "uzpolitex.uzpolitex.doctype.kk_jurnal.kk_jurnal.make_press",
					frm: frm,
				});
			}).addClass("btn-primary");
		}
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

frappe.ui.form.on("KK Jurnal Qator", {
	async konvert_jurnal(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.konvert_jurnal) return;
		const r = await frappe.xcall(
			"uzpolitex.uzpolitex.doctype.konvert_jurnal.konvert_jurnal.konvert_malumot",
			{ konvert_jurnal: row.konvert_jurnal }
		);
		if (r.qoplar && r.qoplar.length === 1) {
			row.mahsulot = r.qoplar[0].mahsulot;
			if (!cint(row.yaroqli_sht)) row.yaroqli_sht = r.qoplar[0].sht;
		}
		frm.refresh_field("qatorlar");
		uz_jami(frm);
	},
	yaroqli_sht: uz_jami,
	brak_sht: uz_jami,
	brak_kg: uz_jami,
	qatorlar_remove: uz_jami,
});

function uz_jami(frm) {
	let y = 0, bs = 0, bk = 0;
	(frm.doc.qatorlar || []).forEach((r) => {
		r.tekshirildi_sht = cint(r.yaroqli_sht) + cint(r.brak_sht);
		y += cint(r.yaroqli_sht);
		bs += cint(r.brak_sht);
		bk += flt(r.brak_kg);
	});
	frm.refresh_field("qatorlar");
	frm.set_value("jami_yaroqli", y);
	frm.set_value("jami_brak_sht", bs);
	frm.set_value("jami_brak_kg", flt(bk, 2));
}
