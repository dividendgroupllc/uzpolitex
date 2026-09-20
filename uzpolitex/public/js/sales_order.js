// Қоп заказлардан Item авто яратиб, стандарт items жадвалига қўшади.

const UZ_MAX_CM = 150;

function olchamXato(row) {
	// мм киритилган бўлса дарҳол огоҳлантирамиз (500 см = 5 метр!)
	for (const [label, v] of [["Эни", row.en_cm], ["Бўйи", row.boy_cm]]) {
		if (flt(v) > UZ_MAX_CM) {
			frappe.msgprint({
				title: __("Ўлчам хато"),
				message: __("«{0}»: {1} {2} см — бу {3} метр! Ўлчам СМ да киритилади (масалан 50, 500 эмас).",
					[row.nomi || "?", label, v, (v / 100).toFixed(1)]),
				indicator: "red",
			});
			return true;
		}
	}
	return false;
}

function prepareQop(frm, silent, force) {
	const rows = (frm.doc.uz_qop_zakazlar || []).map((r) => ({
		name: r.name, nomi: r.nomi, en_cm: r.en_cm, boy_cm: r.boy_cm, soni: r.soni,
		old_rasm: r.old_rasm, orqa_turi: r.orqa_turi, orqa_rasm: r.orqa_rasm,
		lenta_turi: r.lenta_turi, lenta_rasm: r.lenta_rasm, item: r.item,
	}));
	if (!rows.length) return;
	if (rows.some((r) => flt(r.en_cm) > UZ_MAX_CM || flt(r.boy_cm) > UZ_MAX_CM)) return;
	// камида битта тайёр қатор борми (force — расм ўзгарган, item бор бўлса ҳам қайта ишлаймиз)
	const ready = rows.some((r) => r.nomi && r.en_cm && r.boy_cm && r.old_rasm && (force || !r.item));
	if (!ready && silent) return;
	frappe.call({
		method: "uzpolitex.pechat.order_intake.prepare",
		args: { rows: JSON.stringify(rows) },
		freeze: !silent,
		freeze_message: __("Item яратиляпти..."),
		callback: (r) => {
			if (!r.message) return;
			// бўш items қаторларини олиб ташлаймиз — заказ 1-қатордан бошлансин
			(frm.doc.items || [])
				.filter((x) => !x.item_code)
				.forEach((x) => frappe.model.clear_doc(x.doctype, x.name));
			r.message.forEach((res) => {
				if (!res.item) return;
				// қоп заказ қаторига item/ҳолат ёзиш
				const zrow = (frm.doc.uz_qop_zakazlar || []).find((x) => x.name === res.name);
				if (zrow) {
					frappe.model.set_value(zrow.doctype, zrow.name, "item", res.item);
					if (res.holat)
						frappe.model.set_value(zrow.doctype, zrow.name, "holat", res.holat);
					if (res.holat && res.holat.startsWith("⚠"))
						frappe.show_alert({ message: res.holat, indicator: "orange" });
				}
				// стандарт items жадвалига қўшиш (йўқ бўлса)
				let it = (frm.doc.items || []).find((x) => x.item_code === res.item);
				if (!it) {
					it = frm.add_child("items", { item_code: res.item, qty: res.soni || 1 });
					frm.script_manager.trigger("item_code", it.doctype, it.name);
				}
			});
			// миқдор = шу itemли БАРЧА заказ қаторлари йиғиндиси (бир маҳсулот 2 қаторда бўлиши мумкин)
			const jami = {};
			(frm.doc.uz_qop_zakazlar || []).forEach((z) => {
				if (z.item) jami[z.item] = (jami[z.item] || 0) + cint(z.soni);
			});
			(frm.doc.items || []).forEach((it) => {
				if (jami[it.item_code]) it.qty = jami[it.item_code];
			});
			(frm.doc.items || []).forEach((it, i) => (it.idx = i + 1));
			frm.refresh_field("items");
			frm.refresh_field("uz_qop_zakazlar");
			if (!silent)
				frappe.show_alert({ message: __("Item(лар) items жадвалига қўшилди."), indicator: "green" });
		},
	});
}

frappe.ui.form.on("Sales Order", {
	refresh(frm) {
		frm.add_custom_button(__("Заказлардан Item тайёрла"), () => prepareQop(frm, false, true));
		if (!frm.is_new())
			frm.add_custom_button(__("Краска нормасини ҳисобла"), () => {
				frappe.call({
					method: "uzpolitex.pechat.order_ink.compute",
					args: { sales_order: frm.doc.name }, freeze: true,
					callback: (r) => { frm.reload_doc(); if (r.message)
						frappe.show_alert({ message: __("Норма: {0} ранг", [r.message.qatorlar]), indicator: "green" }); },
				});
			});
	},
});

// қатор тўлганда авто тайёрлаш; расм ўзгарса item бор қаторда ҳам қайта ишлов
function maybePrepare(frm, cdt, cdn, force) {
	const row = locals[cdt][cdn];
	if (olchamXato(row)) return;
	if (row.old_rasm && row.nomi && row.en_cm && row.boy_cm && (force || !row.item))
		prepareQop(frm, true, force);
}
function soniSync(frm) {
	// заказ қаторлари сонидан items миқдорини локал янгилаш (сервер чақирмасдан)
	const jami = {};
	(frm.doc.uz_qop_zakazlar || []).forEach((z) => {
		if (z.item) jami[z.item] = (jami[z.item] || 0) + cint(z.soni);
	});
	let ozgardi = false;
	(frm.doc.items || []).forEach((it) => {
		if (jami[it.item_code] && it.qty !== jami[it.item_code]) {
			it.qty = jami[it.item_code];
			ozgardi = true;
		}
	});
	if (ozgardi) frm.refresh_field("items");
}

frappe.ui.form.on("Uzpolitex Qop Zakaz", {
	old_rasm: (frm, cdt, cdn) => maybePrepare(frm, cdt, cdn, true),
	orqa_rasm: (frm, cdt, cdn) => maybePrepare(frm, cdt, cdn, true),
	lenta_rasm: (frm, cdt, cdn) => maybePrepare(frm, cdt, cdn, true),
	nomi: maybePrepare,
	en_cm: maybePrepare,
	boy_cm: maybePrepare,
	soni(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row.item) soniSync(frm);
		else maybePrepare(frm, cdt, cdn);
	},
	uz_qop_zakazlar_remove: soniSync,
});
