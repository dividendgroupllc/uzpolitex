// Печать Топшириқ — AI rejani joriy dizayn/kalibr bilan yangilash tugmasi.

frappe.ui.form.on("Pechat Topshiriq", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("AI режани янгилаш"), () => {
			frappe.call({
				method: "uzpolitex.pechat.topshiriq.reja_yangila",
				args: { name: frm.doc.name },
				freeze: true,
				freeze_message: __("Режа қайта ҳисобланяпти..."),
				callback: (r) => {
					frm.reload_doc();
					if (r.message)
						frappe.show_alert({
							message: __("Режа янгиланди: {0} ранг", [r.message.qatorlar]),
							indicator: "orange",
						});
				},
			});
		});
	},
});
