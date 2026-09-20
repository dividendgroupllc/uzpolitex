// Ламинат журнал — qulayliklar: sana 09:00 qoidasi, xodim filtri, rasxod
// mahsulot avto, norma/taqsimot va В 1М(ГР) jonli hisob, qizil ogohlantirish.

frappe.ui.form.on("Laminat Jurnal", {
	setup(frm) {
		frm.set_query("xodim", () => ({
			filters: { status: "Active", department: "Ламинант - UH" },
		}));
		frm.set_query("mahsulot", "qatorlar", () => ({
			filters: { item_group: "Полуфабрикат - Ламинант" },
		}));
		frm.set_query("rasxod_mahsulot", "qatorlar", () => ({
			filters: { item_group: "Полуфабрикат - Ткацкий" },
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

	fakt_siryo(frm) {
		uz_hisobla(frm);
	},

	fakt_dp(frm) {
		uz_hisobla(frm);
	},
});

frappe.ui.form.on("Laminat Jurnal Qator", {
	async mahsulot(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row.mahsulot && !row.rasxod_mahsulot) {
			const r = await frappe.xcall(
				"uzpolitex.uzpolitex.doctype.laminat_jurnal.laminat_jurnal.rasxod_mahsulot",
				{ mahsulot: row.mahsulot }
			);
			if (r) row.rasxod_mahsulot = r;
		}
		uz_hisobla(frm);
	},
	metr(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		// Excelda rasxod metr ≈ chiqqan metr — boshlang'ich qiymat sifatida
		if (!flt(row.rasxod_metr)) row.rasxod_metr = flt(row.metr);
		uz_hisobla(frm);
	},
	kg(frm) {
		uz_hisobla(frm);
	},
	rasxod_kg(frm) {
		uz_hisobla(frm);
	},
	rasxod_metr(frm) {
		uz_hisobla(frm);
	},
	qatorlar_remove(frm) {
		uz_hisobla(frm);
	},
});

function uz_hisobla(frm) {
	let jami_metr = 0,
		jami_kg = 0,
		norma_s = 0,
		norma_d = 0;
	(frm.doc.qatorlar || []).forEach((r) => {
		const qoplama = Math.max(flt(r.kg) - flt(r.rasxod_kg), 0);
		r.norma_siryo = flt(qoplama * 0.82, 2);
		r.norma_dp = flt(qoplama * 0.18, 2);
		r.v_1m = flt(r.metr) ? (flt(r.kg) / flt(r.metr)) * 1000 : 0;
		jami_metr += flt(r.metr);
		jami_kg += flt(r.kg);
		norma_s += r.norma_siryo;
		norma_d += r.norma_dp;
	});
	(frm.doc.qatorlar || []).forEach((r) => {
		r.siryo_kg =
			flt(frm.doc.fakt_siryo) && norma_s
				? flt((r.norma_siryo / norma_s) * flt(frm.doc.fakt_siryo), 2)
				: r.norma_siryo;
		r.dp_kg =
			flt(frm.doc.fakt_dp) && norma_d
				? flt((r.norma_dp / norma_d) * flt(frm.doc.fakt_dp), 2)
				: r.norma_dp;
	});
	frm.refresh_field("qatorlar");
	frm.set_value("jami_metr", flt(jami_metr, 2));
	frm.set_value("jami_kg", flt(jami_kg, 2));
	frm.set_value("norma_siryo_jami", flt(norma_s, 2));
	frm.set_value("norma_dp_jami", flt(norma_d, 2));
	uz_norma_headline(frm);
}

async function uz_norma_headline(frm) {
	const mahsulotlar = [...new Set((frm.doc.qatorlar || []).map((r) => r.mahsulot).filter(Boolean))];
	frm._uz_normalar = frm._uz_normalar || {};
	for (const m of mahsulotlar) {
		if (!(m in frm._uz_normalar)) {
			const r = await frappe.db.get_value("Item", m, ["uz_norma_min", "uz_norma_max"]);
			frm._uz_normalar[m] = (r && r.message) || {};
		}
	}
	const buzilgan = (frm.doc.qatorlar || []).filter((r) => {
		const n = frm._uz_normalar[r.mahsulot];
		if (!n || !flt(n.uz_norma_max) || !flt(r.v_1m)) return false;
		return flt(r.v_1m) < flt(n.uz_norma_min) || flt(r.v_1m) > flt(n.uz_norma_max);
	});
	if (buzilgan.length) {
		const matn = buzilgan
			.map((r) => {
				const n = frm._uz_normalar[r.mahsulot];
				const v = flt(r.v_1m);
				const pct =
					v < flt(n.uz_norma_min)
						? `−${((1 - v / flt(n.uz_norma_min)) * 100).toFixed(1)}%`
						: `+${((1 - flt(n.uz_norma_max) / v) * 100).toFixed(1)}%`;
				return `${r.mahsulot} (${v.toFixed(1)} г/м, ${pct})`;
			})
			.join(", ");
		frm.dashboard.set_headline(
			`<span class="indicator-pill red">В 1М(ГР) вне нормы: ${matn}</span>`
		);
	} else {
		frm.dashboard.clear_headline();
	}
}
