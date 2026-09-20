// Резка журнал — rulon tanlanganda lenta avto, metr ×2 jonli, В 1М(ГР) hisobi.

frappe.ui.form.on("Rezka Jurnal", {
	setup(frm) {
		frm.set_query("xodim", () => ({
			filters: { status: "Active", department: "Ламинант - UH" },
		}));
		frm.set_query("kirim_mahsulot", "qatorlar", () => ({
			filters: {
				item_group: "Полуфабрикат - Ламинант",
				name: ["like", "Ламинат Рулон%"],
			},
		}));
		frm.set_query("chiqim_mahsulot", "qatorlar", () => ({
			filters: { item_group: "Полуфабрикат - Ламинант" },
		}));
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
	},
});

frappe.ui.form.on("Rezka Jurnal Qator", {
	async kirim_mahsulot(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row.kirim_mahsulot) {
			const r = await frappe.xcall(
				"uzpolitex.uzpolitex.doctype.rezka_jurnal.rezka_jurnal.chiqim_mahsulot",
				{ kirim_mahsulot: row.kirim_mahsulot }
			);
			if (r) row.chiqim_mahsulot = r;
		}
		uz_hisobla(frm);
	},
	kirim_metr(frm) {
		uz_hisobla(frm);
	},
	kg(frm) {
		uz_hisobla(frm);
	},
	qatorlar_remove(frm) {
		uz_hisobla(frm);
	},
});

function uz_hisobla(frm) {
	let kirim = 0,
		chiqim = 0,
		kg = 0;
	(frm.doc.qatorlar || []).forEach((r) => {
		r.chiqim_metr = flt(r.kirim_metr) * 2;
		r.gr_1m = r.chiqim_metr ? (flt(r.kg) / r.chiqim_metr) * 1000 : 0;
		kirim += flt(r.kirim_metr);
		chiqim += r.chiqim_metr;
		kg += flt(r.kg);
	});
	frm.refresh_field("qatorlar");
	frm.set_value("jami_kirim_metr", flt(kirim, 2));
	frm.set_value("jami_chiqim_metr", flt(chiqim, 2));
	frm.set_value("jami_kg", flt(kg, 2));
}
