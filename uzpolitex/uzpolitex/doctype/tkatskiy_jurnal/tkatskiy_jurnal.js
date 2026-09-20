// Ткацкий журнал — master uchun qulayliklar:
// diapazon (с № ... по №) yozilishi bilan qatorlar ochiladi, har stanokning
// mahsuloti o'tgan smenadan avto to'ladi, 1М(ГР) va jami jonli hisoblanadi.

frappe.ui.form.on("Tkatskiy Jurnal", {
	setup(frm) {
		frm.set_query("xodim", () => ({
			filters: { status: "Active", department: "Ткацкий - UH" },
		}));
		frm.set_query("mahsulot", "qatorlar", () => ({
			filters: { item_group: "Полуфабрикат - Ткацкий" },
		}));
	},

	onload(frm) {
		if (frm.is_new() && !frm.doc.posting_date) {
			// smena 09:00 da boshlanadi: 09:00 gacha kiritilsa — kechagi smena
			let sana = frappe.datetime.nowdate();
			if (frappe.datetime.now_time() < "09:00:00") {
				sana = frappe.datetime.add_days(sana, -1);
			}
			frm.set_value("posting_date", sana);
			frm.set_intro(__("Проверьте дату: ставится день НАЧАЛА смены (09:00)."), "yellow");
		}
	},

	stanok_dan(frm) {
		uz_diapazon(frm);
	},

	stanok_gacha(frm) {
		uz_diapazon(frm);
	},
});

frappe.ui.form.on("Tkatskiy Jurnal Qator", {
	metr(frm, cdt, cdn) {
		uz_qator(frm, cdt, cdn);
	},
	kg(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!flt(row.nitka_kg)) row.nitka_kg = flt(row.kg);
		uz_qator(frm, cdt, cdn);
	},
	nitka_kg(frm) {
		uz_jami(frm);
	},
	qatorlar_remove(frm) {
		uz_jami(frm);
	},
});

async function uz_diapazon(frm) {
	const dan = cint(frm.doc.stanok_dan);
	const gacha = cint(frm.doc.stanok_gacha);
	if (!dan || !gacha || gacha < dan || gacha > 70) return;

	// diapazondan tashqaridagi qatorlar: bo'shlari o'chadi,
	// ma'lumot kiritilganlari saqlanadi (operator yozgani yo'qolmasin)
	const tashqarida = (frm.doc.qatorlar || []).filter((r) => {
		const s = cint(r.stanok);
		return s && (s < dan || s > gacha);
	});
	tashqarida
		.filter((r) => !flt(r.metr) && !flt(r.kg))
		.forEach((r) => frappe.model.clear_doc(r.doctype, r.name));
	const qolganlar = tashqarida.filter((r) => flt(r.metr) || flt(r.kg));
	if (qolganlar.length) {
		frappe.show_alert({
			message: __("Вне диапазона, но с данными — не удалены: {0}", [
				qolganlar.map((r) => "№" + r.stanok).join(", "),
			]),
			indicator: "orange",
		});
	}

	// bo'sh boshlang'ich qatorni olib tashlash
	(frm.doc.qatorlar || [])
		.filter((r) => !r.stanok && !flt(r.metr) && !flt(r.kg))
		.forEach((r) => frappe.model.clear_doc(r.doctype, r.name));

	const bor = new Set((frm.doc.qatorlar || []).map((r) => cint(r.stanok)));
	const yangi = [];
	for (let s = dan; s <= gacha; s++) {
		if (!bor.has(s)) yangi.push(s);
	}

	// har stanok oxirgi to'qigan mahsuloti (97% o'zgarmaydi)
	let oxirgi = {};
	if (yangi.length) {
		try {
			oxirgi = await frappe.xcall(
				"uzpolitex.uzpolitex.doctype.tkatskiy_jurnal.tkatskiy_jurnal.oxirgi_mahsulotlar",
				{ stanoklar: yangi }
			);
		} catch (e) {
			// avto to'ldirish ishlamasa ham qatorlar ochilaveradi
		}
	}

	yangi.forEach((s) => {
		const row = frm.add_child("qatorlar", { stanok: s });
		if (oxirgi[s]) row.mahsulot = oxirgi[s];
	});

	// stanok raqami bo'yicha tartib
	(frm.doc.qatorlar || []).sort((a, b) => cint(a.stanok) - cint(b.stanok));
	(frm.doc.qatorlar || []).forEach((r, i) => (r.idx = i + 1));

	frm.refresh_field("qatorlar");
	uz_jami(frm);
}

function uz_qator(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	row.gr_1m = flt(row.metr) ? (flt(row.kg) / flt(row.metr)) * 1000 : 0;
	frm.refresh_field("qatorlar");
	uz_jami(frm);
	uz_norma_headline(frm);
}

function uz_jami(frm) {
	let metr = 0,
		kg = 0,
		nitka = 0;
	(frm.doc.qatorlar || []).forEach((r) => {
		metr += flt(r.metr);
		kg += flt(r.kg);
		nitka += flt(r.nitka_kg) || flt(r.kg);
	});
	frm.set_value("jami_metr", flt(metr, 2));
	frm.set_value("jami_kg", flt(kg, 2));
	frm.set_value("jami_nitka", flt(nitka, 2));
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
		if (!n || !flt(n.uz_norma_max) || !flt(r.gr_1m)) return false;
		return flt(r.gr_1m) < flt(n.uz_norma_min) || flt(r.gr_1m) > flt(n.uz_norma_max);
	});
	if (buzilgan.length) {
		const raqamlar = buzilgan
			.map((r) => {
				const n = frm._uz_normalar[r.mahsulot];
				const v = flt(r.gr_1m);
				// Excel: Отклонение мин/макс — normadan chetlanish foizi
				const pct =
					v < flt(n.uz_norma_min)
						? `−${((1 - v / flt(n.uz_norma_min)) * 100).toFixed(1)}%`
						: `+${((1 - flt(n.uz_norma_max) / v) * 100).toFixed(1)}%`;
				return `№${r.stanok} (${v.toFixed(1)} г/м, ${pct})`;
			})
			.join(", ");
		frm.dashboard.set_headline(
			`<span class="indicator-pill red">1М(ГР) вне нормы: станки ${raqamlar}</span>`
		);
	} else {
		frm.dashboard.clear_headline();
	}
}
