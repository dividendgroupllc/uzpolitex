// Печать журнал — топшириқ танланади, рулонлар авто, краска AI дан авто.

frappe.ui.form.on("Pechat Jurnal", {
	setup(frm) {
		frm.set_query("xodim", () => ({
			filters: { status: "Active", department: "Печать - UH" },
		}));
		frm.set_query("topshiriq", () => ({
			filters: { docstatus: ["<", 2], holat: ["!=", "Тайёр"] },
		}));
		frm.set_query("qop_item", () => ({
			filters: { name: ["in", frm._uz_qoplar || []] },
		}));
		frm.set_query("rasxod_mahsulot", () => ({
			filters: { item_group: "Полуфабрикат - Ламинант" },
		}));
		frm.set_query("rang", "kraskalar", () => ({
			filters: { item_group: "Сырьё - Печать" },
		}));
	},

	refresh(frm) {
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__("Конвертга ўтиш (тикув)"), () => {
				frappe.model.open_mapped_doc({
					method: "uzpolitex.uzpolitex.doctype.pechat_jurnal.pechat_jurnal.make_konvert",
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
		if (frm.doc.topshiriq) uz_topshiriq(frm);
	},

	async topshiriq(frm) {
		await uz_topshiriq(frm, true);
	},

	async qop_item(frm) {
		if (!frm.doc.qop_item) return;
		const r = await frappe.xcall(
			"uzpolitex.uzpolitex.doctype.pechat_jurnal.pechat_jurnal.qop_malumot",
			{ qop_item: frm.doc.qop_item }
		);
		if (r.rasxod_mahsulot) frm.set_value("rasxod_mahsulot", r.rasxod_mahsulot);
		if (r.bosma_rulon) frm.set_value("bosma_rulon", r.bosma_rulon);
		await uz_kraska_default(frm);
	},

	async metr(frm) {
		frm.set_value("rasxod_metr", flt(frm.doc.metr));
		await uz_kraska_default(frm);
	},
});

async function uz_topshiriq(frm, tanlash) {
	if (!frm.doc.topshiriq) return;
	const r = await frappe.xcall(
		"uzpolitex.uzpolitex.doctype.pechat_jurnal.pechat_jurnal.topshiriq_malumot",
		{ topshiriq: frm.doc.topshiriq }
	);
	frm._uz_qoplar = r.qoplar || [];
	if (tanlash) {
		if (frm._uz_qoplar.length === 1) {
			frm.set_value("qop_item", frm._uz_qoplar[0]);
		} else {
			frm.set_value("qop_item", null);
		}
	}
}

// краска — AI/дизайн бўйича авто (бўш бўлса тўлади, метр ўзгарса янгиланмайди
// агар оператор қўлда киритган бўлса)
async function uz_kraska_default(frm) {
	if (!frm.doc.qop_item || !flt(frm.doc.metr)) return;
	if ((frm.doc.kraskalar || []).some((k) => k.rang || flt(k.kg))) return;
	const rows = await frappe.xcall(
		"uzpolitex.uzpolitex.doctype.pechat_jurnal.pechat_jurnal.kraska_default",
		{ qop_item: frm.doc.qop_item, metr: frm.doc.metr }
	);
	if (!rows || !rows.length) return;
	frm.clear_table("kraskalar");
	rows.forEach((r) => frm.add_child("kraskalar", r));
	frm.refresh_field("kraskalar");
	uz_jami(frm);
}

frappe.ui.form.on("Pechat Jurnal Kraska", {
	kg(frm) {
		uz_jami(frm);
	},
	kraskalar_remove(frm) {
		uz_jami(frm);
	},
});

function uz_jami(frm) {
	let kg = 0;
	(frm.doc.kraskalar || []).forEach((k) => (kg += flt(k.kg)));
	frm.set_value("jami_kraska_kg", flt(kg, 2));
}
