"""Sales Order sahifasida «Печать» bog'lanishlarini ko'rsatish (Connections panel)."""


def sales_order_dashboard(data):
	data.setdefault("non_standard_fieldnames", {})["Pechat Topshiriq"] = "sales_order"
	data["transactions"].insert(0, {"label": "Печать", "items": ["Pechat Topshiriq"]})
	return data
