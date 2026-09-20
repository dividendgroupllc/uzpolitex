frappe.ui.form.on("Pechat Dizayn", {
	refresh(frm) {
		frm.add_custom_button(__("AI: расмни таҳлил қил"), () => run_ai(frm)).addClass(
			"btn-primary"
		);
	},
});

function run_ai(frm) {
	if (!frm.doc.rasm) {
		frappe.msgprint(__("Аввал дизайн расмини бириктиринг."));
		return;
	}
	frappe.dom.freeze(__("AI расмни таҳлил қиляпти..."));
	frappe.call({
		method: "uzpolitex.pechat.ink_analyzer.analyze",
		args: { dizayn: frm.doc.name },
		callback: (r) => {
			frappe.dom.unfreeze();
			if (!r.message) return;
			frm.set_value("oq_baza_pct", r.message.oq_baza_pct);
			frm.clear_table("ranglar");
			(r.message.ranglar || []).forEach((row) => {
				const c = frm.add_child("ranglar");
				c.rang = row.mavjud_emas ? "" : row.rang;
				c.pantone = row.pantone;
				c.qoplama_pct = row.qoplama_pct;
				c.rgb = row.rgb + (row.mavjud_emas ? " (" + row.rang + "?)" : "");
				c.avto = 1;
			});
			frm.refresh_field("ranglar");
			frm.refresh_field("oq_baza_pct");
			(r.message.warnings || []).forEach((w) =>
				frappe.msgprint({ message: w, title: __("Диққат"), indicator: "orange" })
			);
			frappe.show_alert({
				message: __("AI таклиф қилди. Текширинг ва керак бўлса тузатинг."),
				indicator: "green",
			});
		},
		error: () => frappe.dom.unfreeze(),
	});
}
