def pending_item(level=2):
    options = [{"id": "backup:b", "kind": "backup", "actions": [{"type": "drop_place", "place": "b"}], "changed": ["b"],
                "shifted": [], "text": "Thay b bằng c"}]
    if level == 2:
        options.append({"id": "keep:b", "kind": "keep", "actions": [], "changed": [], "shifted": [], "text": "Giữ nguyên lịch"})
    return {"date": "2026-12-12", "place_id": "b", "name": "b", "level": level,
            "cause": {"factor": "rain", "level": level, "text": "mưa 85% · 3 mm 14–17h", "source": "open-meteo",
                      "retrieved_at": None, "key": "rain:b:2026-12-12"}, "options": options}
