frappe.ui.form.on("Item", {
	refresh(frm) {
		if (frm.doc.item_group !== "Сырьё - Печать") return;
		if (frm.doc.uz_kraska_turi !== "Аралашма") return;
		frm.add_custom_button(__("AI: аралашма ретсептини таклиф қил"), () => {
			if (!frm.doc.uz_rgb) {
				frappe.msgprint(__("Аввал «Ранг (HEX)» майдонини тўлдиринг."));
				return;
			}
			frappe.call({
				method: "uzpolitex.pechat.kraska_mix.suggest",
				args: { item: frm.doc.name },
				freeze: true,
				callback: (r) => {
					if (!r.message) return;
					frm.clear_table("uz_retsept");
					r.message.components.forEach((c) => {
						const row = frm.add_child("uz_retsept");
						row.baza_rang = c.baza_rang;
						row.ulush_pct = c.ulush_pct;
					});
					frm.refresh_field("uz_retsept");
					frappe.msgprint({
						title: __("AI ретсепт таклифи"),
						indicator: "green",
						message: __("Аралашма ранги ≈ {0} (хато Δ={1}). Текшириб тасдиқланг.",
							[r.message.mix_hex, r.message.delta]),
					});
				},
			});
		});
	},
});
