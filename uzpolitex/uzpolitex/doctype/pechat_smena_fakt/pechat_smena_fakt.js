// Печать смена факт — AI устуни авто, факт киритилади, фарқ жонли.

frappe.ui.form.on("Pechat Smena Fakt", {
	setup(frm) {
		frm.set_query("rang", "ranglar", () => ({
			filters: { item_group: "Сырьё - Печать" },
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

	posting_date(frm) {
		uz_ai(frm);
	},
	smena(frm) {
		uz_ai(frm);
	},
});

// AI ustuni: shu smena jurnallaridan; jadval bo'sh bo'lsa ranglar avto ochiladi
async function uz_ai(frm) {
	if (!frm.doc.posting_date || !frm.doc.smena) return;
	const rows = await frappe.xcall(
		"uzpolitex.uzpolitex.doctype.pechat_smena_fakt.pechat_smena_fakt.ai_hisob",
		{ posting_date: frm.doc.posting_date, smena: frm.doc.smena }
	);
	const bosh = !(frm.doc.ranglar || []).some((r) => r.rang || flt(r.fakt_kg));
	if (bosh) {
		frm.clear_table("ranglar");
		(rows || []).forEach((r) => frm.add_child("ranglar", r));
	} else {
		const ai = {};
		(rows || []).forEach((r) => (ai[r.rang] = r.ai_kg));
		(frm.doc.ranglar || []).forEach((r) => {
			r.ai_kg = ai[r.rang] || 0;
			r.farq = flt(flt(r.fakt_kg) - r.ai_kg, 2);
		});
	}
	frm.refresh_field("ranglar");
	uz_jami(frm);
}

frappe.ui.form.on("Pechat Smena Fakt Qator", {
	fakt_kg(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		row.farq = flt(flt(row.fakt_kg) - flt(row.ai_kg), 2);
		frm.refresh_field("ranglar");
		uz_jami(frm);
	},
	ranglar_remove(frm) {
		uz_jami(frm);
	},
});

function uz_jami(frm) {
	let fakt = 0,
		ai = 0;
	(frm.doc.ranglar || []).forEach((r) => {
		fakt += flt(r.fakt_kg);
		ai += flt(r.ai_kg);
	});
	frm.set_value("jami_fakt", flt(fakt, 2));
	frm.set_value("jami_ai", flt(ai, 2));
}
