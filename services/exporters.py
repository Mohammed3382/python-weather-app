import io
import unicodedata
import zipfile
from datetime import datetime, timezone
from html import escape as xml_escape
from textwrap import wrap


def build_csv_export(bundle):
    buffer = io.StringIO()

    def write_row(values):
        escaped = []
        for value in values:
            text = "" if value is None else str(value)
            if any(char in text for char in [",", '"', "\n"]):
                text = '"' + text.replace('"', '""') + '"'
            escaped.append(text)
        buffer.write(",".join(escaped) + "\n")

    write_row(["SKYLINE FORECAST"])
    write_row(["Weather Export"])
    write_row(["City", bundle["city"]])
    write_row(["Range", bundle["range_label"]])
    write_row(["Generated At", bundle["generated_at"]])
    write_row(["Temperature Unit", bundle["temperature_unit"]])
    write_row(["Wind Unit", bundle["wind_unit"]])
    write_row([])

    write_row(["Current Conditions"])
    write_row(list(bundle["current"].keys()))
    write_row(list(bundle["current"].values()))
    write_row([])

    write_row(["Advisory Snapshot"])
    write_row(["Primary Insight", bundle["primary_insight"]["title"]])
    write_row(["Insight Summary", bundle["primary_insight"]["body"]])
    write_row(["Alerts", " | ".join(alert["title"] for alert in bundle["alerts"])])
    write_row(
        [
            "Scores",
            " | ".join(
                f'{score["label"]}: {score["value"]}/10'
                for score in bundle["scores"]
            ),
        ]
    )
    write_row([])

    write_row(["Selected Weather Window"])
    forecast_headers = [
        "Date",
        "Day",
        "Condition",
        "Low",
        "High",
        "Rain Chance",
        "Rain Total",
        "UV Index",
        "Sunrise",
        "Sunset",
    ]
    write_row(forecast_headers)
    for row in bundle["forecast_rows"]:
        write_row([row[header] for header in forecast_headers])

    return buffer.getvalue().encode("utf-8-sig")


def build_excel_export(bundle):
    workbook_bytes = io.BytesIO()
    with zipfile.ZipFile(workbook_bytes, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _build_content_types_xml())
        archive.writestr("_rels/.rels", _build_root_relationships_xml())
        archive.writestr("docProps/app.xml", _build_app_properties_xml())
        archive.writestr("docProps/core.xml", _build_core_properties_xml())
        archive.writestr("xl/workbook.xml", _build_workbook_xml())
        archive.writestr("xl/_rels/workbook.xml.rels", _build_workbook_relationships_xml())
        archive.writestr("xl/styles.xml", _build_styles_xml())
        archive.writestr("xl/worksheets/sheet1.xml", _build_overview_sheet_xml(bundle))
        archive.writestr("xl/worksheets/sheet2.xml", _build_forecast_sheet_xml(bundle))

    return workbook_bytes.getvalue()


def build_pdf_export(bundle):
    return _build_pdf_export_v2(bundle)

    page_width = 612
    page_height = 792
    commands = []

    def page_y(top_offset):
        return page_height - top_offset

    def draw_rect(x, top, width, height, fill_rgb, stroke_rgb=None, line_width=1):
        y = page_height - top - height
        fill = f"{fill_rgb[0]:.3f} {fill_rgb[1]:.3f} {fill_rgb[2]:.3f} rg"
        if stroke_rgb is None:
            commands.append(f"{fill}\n{x:.2f} {y:.2f} {width:.2f} {height:.2f} re f")
            return
        stroke = f"{stroke_rgb[0]:.3f} {stroke_rgb[1]:.3f} {stroke_rgb[2]:.3f} RG"
        commands.append(
            f"{line_width:.2f} w\n{fill}\n{stroke}\n{x:.2f} {y:.2f} {width:.2f} {height:.2f} re B"
        )

    def draw_text(x, top, text, font_name="F1", size=11, rgb=(0.12, 0.2, 0.3)):
        safe_text = _pdf_escape(text)
        commands.append(
            "BT\n"
            f"/{font_name} {size} Tf\n"
            f"{rgb[0]:.3f} {rgb[1]:.3f} {rgb[2]:.3f} rg\n"
            f"1 0 0 1 {x:.2f} {page_y(top):.2f} Tm\n"
            f"({safe_text}) Tj\n"
            "ET"
        )

    def draw_line(x1, top1, x2, top2, stroke_rgb, line_width=1):
        commands.append(
            f"{line_width:.2f} w\n"
            f"{stroke_rgb[0]:.3f} {stroke_rgb[1]:.3f} {stroke_rgb[2]:.3f} RG\n"
            f"{x1:.2f} {page_y(top1):.2f} m\n"
            f"{x2:.2f} {page_y(top2):.2f} l S"
        )

    def draw_wrapped_text(x, top, text, max_chars, font_name="F1", size=10, rgb=(0.2, 0.27, 0.36), line_gap=13):
        lines = wrap(_pdf_plain(text), width=max_chars) or [""]
        for index, line in enumerate(lines):
            draw_text(x, top + (index * line_gap), line, font_name=font_name, size=size, rgb=rgb)
        return top + (len(lines) * line_gap)

    draw_rect(36, 34, 540, 84, (0.13, 0.25, 0.42))
    draw_rect(54, 52, 56, 42, (0.92, 0.97, 1.0), (0.82, 0.9, 0.96), 0.6)
    draw_line(66, 92, 98, 92, (0.68, 0.82, 0.9), 2.2)
    draw_line(74, 92, 74, 72, (0.72, 0.86, 0.94), 3.2)
    draw_line(84, 92, 84, 64, (0.8, 0.91, 0.97), 4.1)
    draw_line(94, 92, 94, 76, (0.72, 0.86, 0.94), 3.2)
    draw_text(128, 61, "SKYLINE", font_name="F2", size=20, rgb=(1, 1, 1))
    draw_text(128, 82, "FORECAST", font_name="F2", size=11, rgb=(0.86, 0.93, 0.98))
    draw_text(290, 67, "Weather Export", font_name="F2", size=18, rgb=(1, 1, 1))
    draw_line(128, 92, 210, 92, (0.82, 0.92, 0.98), 1.4)
    draw_text(
        54,
        105,
        f'{bundle["city"]} | {bundle["range_label"]} | Generated {bundle["generated_at"]}',
        font_name="F1",
        size=10,
        rgb=(0.92, 0.96, 1.0),
    )
    draw_text(
        54,
        122,
        f'Temperature Unit: {bundle["temperature_unit"]}   Wind Unit: {bundle["wind_unit"]}',
        font_name="F1",
        size=9,
        rgb=(0.86, 0.92, 0.98),
    )

    stat_cards = [
        ("Condition", bundle["current"]["Condition"]),
        ("Temperature", bundle["current"]["Temperature"]),
        ("Feels Like", bundle["current"]["Feels Like"]),
        ("Wind", bundle["current"]["Wind"]),
    ]
    card_width = 124
    card_gap = 12
    for index, (label, value) in enumerate(stat_cards):
        x_position = 36 + (index * (card_width + card_gap))
        draw_rect(x_position, 154, card_width, 72, (0.93, 0.96, 0.99), (0.82, 0.88, 0.94), 0.8)
        draw_text(x_position + 14, 176, label, font_name="F2", size=9, rgb=(0.32, 0.42, 0.55))
        draw_text(x_position + 14, 201, value, font_name="F2", size=13, rgb=(0.11, 0.2, 0.31))

    draw_rect(36, 244, 540, 108, (0.96, 0.98, 1.0), (0.82, 0.88, 0.94), 0.8)
    draw_text(54, 268, "Advisory Snapshot", font_name="F2", size=12, rgb=(0.11, 0.2, 0.31))
    next_top = draw_wrapped_text(
        54,
        292,
        "Alerts: " + " | ".join(alert["title"] for alert in bundle["alerts"]),
        max_chars=88,
        font_name="F1",
        size=9,
        rgb=(0.2, 0.27, 0.36),
        line_gap=12,
    )
    next_top = draw_wrapped_text(
        54,
        next_top + 6,
        f'Insight: {bundle["primary_insight"]["title"]}. {bundle["primary_insight"]["body"]}',
        max_chars=88,
        font_name="F1",
        size=9,
        rgb=(0.2, 0.27, 0.36),
        line_gap=12,
    )
    draw_wrapped_text(
        54,
        next_top + 6,
        "Scores: "
        + " | ".join(
            f'{score["label"]} {score["value"]}/10'
            for score in bundle["scores"]
        ),
        max_chars=88,
        font_name="F1",
        size=9,
        rgb=(0.2, 0.27, 0.36),
        line_gap=12,
    )

    table_top = 372
    draw_rect(36, table_top, 540, 28, (0.36, 0.49, 0.65))
    draw_text(52, table_top + 18, "Selected Date Window", font_name="F2", size=12, rgb=(1, 1, 1))

    headers = [
        ("Date", 36, 72),
        ("Condition", 108, 100),
        ("Low", 208, 54),
        ("High", 262, 54),
        ("Rain %", 316, 56),
        ("Rain Total", 372, 64),
        ("UV", 436, 38),
        ("Sunrise / Sunset", 474, 102),
    ]
    header_top = table_top + 38
    draw_rect(36, header_top, 540, 26, (0.88, 0.92, 0.97), (0.82, 0.88, 0.94), 0.6)
    for title, x_position, _ in headers:
        draw_text(x_position + 6, header_top + 17, title, font_name="F2", size=8, rgb=(0.18, 0.27, 0.38))

    row_top = header_top + 26
    available_table_height = 322
    row_count = max(1, len(bundle["forecast_rows"]))
    row_height = 26 if row_count <= 12 else max(16, int(available_table_height / row_count))
    row_text_offset = 17 if row_height >= 22 else max(11, row_height - 5)
    row_font_size = 8 if row_height >= 20 else 7
    for index, row in enumerate(bundle["forecast_rows"]):
        fill_color = (0.97, 0.98, 1.0) if index % 2 == 0 else (0.94, 0.97, 0.995)
        current_row_top = row_top + (index * row_height)
        draw_rect(36, current_row_top, 540, row_height, fill_color, (0.86, 0.9, 0.95), 0.4)
        values = [
            row["Date"],
            row["Condition"],
            row["Low"],
            row["High"],
            row["Rain Chance"],
            row["Rain Total"],
            row["UV Index"],
            f'{row["Sunrise"]} / {row["Sunset"]}',
        ]
        for (title, x_position, width), value in zip(headers, values):
            wrapped = wrap(_pdf_plain(value), width=max(8, int(width / 5.8))) or [""]
            draw_text(
                x_position + 6,
                current_row_top + row_text_offset,
                wrapped[0],
                font_name="F1",
                size=row_font_size,
                rgb=(0.2, 0.27, 0.36),
            )

    footer_text = "Export includes the current snapshot and the selected weather window."
    footer_top = min(756, row_top + (row_count * row_height) + 18)
    draw_text(36, footer_top, footer_text, font_name="F1", size=8, rgb=(0.42, 0.5, 0.6))

    return _build_pdf_bytes("\n".join(commands).encode("latin-1", errors="replace"), page_width, page_height)


def build_trip_plan_pdf(bundle):
    return _build_trip_plan_pdf_v2(bundle)

    page_width = 612
    page_height = 792
    pages = []
    point_palette = {
        "origin": {"fill": (0.16, 0.31, 0.49), "soft": (0.9, 0.94, 0.99), "stroke": (0.26, 0.4, 0.58)},
        "destination": {"fill": (0.89, 0.47, 0.35), "soft": (0.99, 0.93, 0.9), "stroke": (0.79, 0.38, 0.28)},
        "outdoor": {"fill": (0.33, 0.63, 0.47), "soft": (0.9, 0.97, 0.93), "stroke": (0.23, 0.52, 0.37)},
        "indoor": {"fill": (0.82, 0.61, 0.24), "soft": (0.99, 0.96, 0.89), "stroke": (0.68, 0.49, 0.16)},
        "evening": {"fill": (0.45, 0.5, 0.67), "soft": (0.93, 0.94, 0.99), "stroke": (0.34, 0.39, 0.56)},
    }

    def new_page():
        commands = []
        pages.append(commands)
        return commands

    def page_y(top_offset):
        return page_height - top_offset

    def draw_rect(page, x, top, width, height, fill_rgb, stroke_rgb=None, line_width=1):
        y = page_height - top - height
        fill = f"{fill_rgb[0]:.3f} {fill_rgb[1]:.3f} {fill_rgb[2]:.3f} rg"
        if stroke_rgb is None:
            page.append(f"{fill}\n{x:.2f} {y:.2f} {width:.2f} {height:.2f} re f")
            return
        stroke = f"{stroke_rgb[0]:.3f} {stroke_rgb[1]:.3f} {stroke_rgb[2]:.3f} RG"
        page.append(
            f"{line_width:.2f} w\n{fill}\n{stroke}\n{x:.2f} {y:.2f} {width:.2f} {height:.2f} re B"
        )

    def draw_text(page, x, top, text, font_name="F1", size=11, rgb=(0.12, 0.2, 0.3)):
        safe_text = _pdf_escape(text)
        page.append(
            "BT\n"
            f"/{font_name} {size} Tf\n"
            f"{rgb[0]:.3f} {rgb[1]:.3f} {rgb[2]:.3f} rg\n"
            f"1 0 0 1 {x:.2f} {page_y(top):.2f} Tm\n"
            f"({safe_text}) Tj\n"
            "ET"
        )

    def draw_wrapped_text(page, x, top, text, max_chars, font_name="F1", size=10, rgb=(0.2, 0.27, 0.36), line_gap=13):
        lines = wrap(_pdf_plain(text), width=max_chars) or [""]
        for index, line in enumerate(lines):
            draw_text(page, x, top + (index * line_gap), line, font_name=font_name, size=size, rgb=rgb)
        return top + (len(lines) * line_gap)

    def draw_line(page, x1, top1, x2, top2, stroke_rgb, line_width=1, dash=None):
        dash_command = "[] 0 d"
        if dash:
            dash_command = f"[{dash[0]:.2f} {dash[1]:.2f}] 0 d"
        page.append(
            f"{line_width:.2f} w\n"
            f"{stroke_rgb[0]:.3f} {stroke_rgb[1]:.3f} {stroke_rgb[2]:.3f} RG\n"
            f"{dash_command}\n"
            f"{x1:.2f} {page_y(top1):.2f} m\n"
            f"{x2:.2f} {page_y(top2):.2f} l S"
        )

    def draw_circle(page, center_x, top_center, radius, fill_rgb, stroke_rgb=None, line_width=1):
        kappa = 0.5522847498
        control = radius * kappa
        center_y = page_y(top_center)
        path = (
            f"{center_x + radius:.2f} {center_y:.2f} m\n"
            f"{center_x + radius:.2f} {center_y + control:.2f} {center_x + control:.2f} {center_y + radius:.2f} {center_x:.2f} {center_y + radius:.2f} c\n"
            f"{center_x - control:.2f} {center_y + radius:.2f} {center_x - radius:.2f} {center_y + control:.2f} {center_x - radius:.2f} {center_y:.2f} c\n"
            f"{center_x - radius:.2f} {center_y - control:.2f} {center_x - control:.2f} {center_y - radius:.2f} {center_x:.2f} {center_y - radius:.2f} c\n"
            f"{center_x + control:.2f} {center_y - radius:.2f} {center_x + radius:.2f} {center_y - control:.2f} {center_x + radius:.2f} {center_y:.2f} c"
        )
        fill = f"{fill_rgb[0]:.3f} {fill_rgb[1]:.3f} {fill_rgb[2]:.3f} rg"
        if stroke_rgb is None:
            page.append(f"{fill}\n{path}\nf")
            return
        stroke = f"{stroke_rgb[0]:.3f} {stroke_rgb[1]:.3f} {stroke_rgb[2]:.3f} RG"
        page.append(f"{line_width:.2f} w\n{fill}\n{stroke}\n{path}\nB")

    def draw_info_card(page, x, top, width, height, label, value, body):
        draw_rect(page, x, top, width, height, (0.95, 0.97, 1.0), (0.82, 0.88, 0.94), 0.7)
        draw_text(page, x + 14, top + 18, label, font_name="F2", size=8, rgb=(0.36, 0.46, 0.58))
        next_top = draw_wrapped_text(
            page,
            x + 14,
            top + 38,
            value,
            max_chars=max(18, int(width / 7.0)),
            font_name="F2",
            size=12,
            rgb=(0.11, 0.2, 0.31),
            line_gap=13,
        )
        draw_wrapped_text(
            page,
            x + 14,
            next_top + 2,
            body,
            max_chars=max(24, int(width / 6.0)),
            font_name="F1",
            size=8,
            rgb=(0.23, 0.31, 0.41),
            line_gap=10,
        )

    def draw_map_label(page, x, top, width, title, subtitle, fill_rgb, stroke_rgb):
        draw_rect(page, x, top, width, 44, fill_rgb, stroke_rgb, 0.6)
        draw_text(page, x + 10, top + 14, title, font_name="F2", size=8, rgb=(0.14, 0.21, 0.31))
        draw_wrapped_text(
            page,
            x + 10,
            top + 27,
            subtitle,
            max_chars=max(12, int((width - 20) / 4.8)),
            font_name="F1",
            size=7,
            rgb=(0.28, 0.36, 0.46),
            line_gap=8,
        )

    def simplify_location_label(value):
        text = _pdf_plain(value)
        primary = text.split(",")[0].strip()
        return primary or "Destination"

    pdf_from_city = simplify_location_label(bundle.get("from_city", ""))
    pdf_to_city = simplify_location_label(bundle.get("to_city", ""))
    has_origin = bool(bundle.get("from_city")) and bundle.get("from_city") != "Not specified"
    route_display = f"{pdf_from_city} to {pdf_to_city}" if has_origin else f"Trip plan to {pdf_to_city}"

    page_one = new_page()
    draw_rect(page_one, 36, 34, 540, 92, (0.13, 0.25, 0.42))
    draw_rect(page_one, 54, 52, 56, 42, (0.92, 0.97, 1.0), (0.82, 0.9, 0.96), 0.6)
    draw_line(page_one, 66, 92, 98, 92, (0.68, 0.82, 0.9), 2.2)
    draw_line(page_one, 74, 92, 74, 72, (0.72, 0.86, 0.94), 3.2)
    draw_line(page_one, 84, 92, 84, 64, (0.8, 0.91, 0.97), 4.1)
    draw_line(page_one, 94, 92, 94, 76, (0.72, 0.86, 0.94), 3.2)
    draw_text(page_one, 128, 61, "SKYLINE", font_name="F2", size=20, rgb=(1, 1, 1))
    draw_text(page_one, 128, 82, "FORECAST", font_name="F2", size=11, rgb=(0.86, 0.93, 0.98))
    draw_text(page_one, 290, 67, "Trip Plan", font_name="F2", size=18, rgb=(1, 1, 1))
    draw_line(page_one, 128, 92, 210, 92, (0.82, 0.92, 0.98), 1.4)
    route_top = draw_wrapped_text(
        page_one,
        54,
        105,
        route_display,
        max_chars=68,
        font_name="F2",
        size=14,
        rgb=(0.95, 0.98, 1.0),
        line_gap=15,
    )
    draw_text(
        page_one,
        54,
        route_top + 4,
        f'{bundle["date_range_label"]} | Generated {bundle["generated_at"]}',
        font_name="F1",
        size=9,
        rgb=(0.86, 0.92, 0.98),
    )

    draw_rect(page_one, 36, 162, 540, 96, (0.96, 0.98, 1.0), (0.82, 0.88, 0.94), 0.8)
    draw_text(page_one, 54, 184, "Trip Summary", font_name="F2", size=12, rgb=(0.11, 0.2, 0.31))
    draw_wrapped_text(
        page_one,
        54,
        210,
        bundle["overview_body"],
        max_chars=92,
        font_name="F1",
        size=9,
        rgb=(0.2, 0.27, 0.36),
        line_gap=12,
    )

    snapshot_cards = [dict(card) for card in bundle["snapshot_cards"][:4]]
    if snapshot_cards:
        snapshot_cards[0]["value"] = pdf_from_city if has_origin else "Not specified"
    if len(snapshot_cards) > 1:
        snapshot_cards[1]["value"] = pdf_to_city
    card_width = 264
    card_height = 78
    card_gap = 12
    snapshot_top = 278
    for index, card in enumerate(snapshot_cards):
        row_index = index // 2
        column_index = index % 2
        x_position = 36 + (column_index * (card_width + card_gap))
        top_position = snapshot_top + (row_index * (card_height + 12))
        draw_info_card(
            page_one,
            x_position,
            top_position,
            card_width,
            card_height,
            card["label"],
            card["value"],
            card["body"],
        )

    packing_title_top = 464
    draw_text(page_one, 36, packing_title_top, "Packing Recommendations", font_name="F2", size=12, rgb=(0.11, 0.2, 0.31))
    packing_cards = bundle["packing_items"][:6]
    packing_top = 488
    packing_width = 264
    packing_height = 82
    for index, item in enumerate(packing_cards):
        row_index = index // 2
        column_index = index % 2
        x_position = 36 + (column_index * (packing_width + 12))
        top_position = packing_top + (row_index * (packing_height + 12))
        draw_rect(page_one, x_position, top_position, packing_width, packing_height, (0.95, 0.97, 1.0), (0.84, 0.89, 0.95), 0.6)
        draw_text(page_one, x_position + 14, top_position + 16, item.get("eyebrow", "Recommendation"), font_name="F2", size=8, rgb=(0.36, 0.46, 0.58))
        next_top = draw_wrapped_text(
            page_one,
            x_position + 14,
            top_position + 34,
            item.get("title", ""),
            max_chars=34,
            font_name="F2",
            size=10,
            rgb=(0.11, 0.2, 0.31),
            line_gap=11,
        )
        draw_wrapped_text(
            page_one,
            x_position + 14,
            next_top + 2,
            item.get("body", ""),
            max_chars=40,
            font_name="F1",
            size=8,
            rgb=(0.23, 0.31, 0.41),
            line_gap=9,
        )

    page_two = new_page()
    draw_rect(page_two, 36, 34, 540, 74, (0.16, 0.29, 0.46))
    draw_text(page_two, 54, 61, "Destination Daily Forecast", font_name="F2", size=20, rgb=(1, 1, 1))
    draw_text(page_two, 54, 86, route_display, font_name="F1", size=9, rgb=(0.88, 0.94, 0.99))

    table_top = 124
    draw_rect(page_two, 36, table_top, 540, 28, (0.36, 0.49, 0.65))
    draw_text(page_two, 52, table_top + 18, "Daily Destination Outlook", font_name="F2", size=12, rgb=(1, 1, 1))

    headers = [
        ("Date", 36, 86),
        ("Day", 122, 46),
        ("Condition", 168, 96),
        ("Low", 264, 56),
        ("High", 320, 56),
        ("Rain", 376, 56),
        ("Wind", 432, 82),
        ("UV", 514, 62),
    ]
    header_top = table_top + 38
    draw_rect(page_two, 36, header_top, 540, 26, (0.88, 0.92, 0.97), (0.82, 0.88, 0.94), 0.6)
    for title, x_position, _ in headers:
        draw_text(page_two, x_position + 6, header_top + 17, title, font_name="F2", size=8, rgb=(0.18, 0.27, 0.38))

    row_top = header_top + 26
    available_table_height = 566
    row_count = max(1, len(bundle["daily_rows"]))
    row_height = 28 if row_count <= 16 else max(22, int(available_table_height / row_count))
    row_text_offset = 17 if row_height >= 24 else max(12, row_height - 6)
    row_font_size = 8 if row_height >= 22 else 7
    for index, row in enumerate(bundle["daily_rows"]):
        fill_color = (0.97, 0.98, 1.0) if index % 2 == 0 else (0.94, 0.97, 0.995)
        current_row_top = row_top + (index * row_height)
        draw_rect(page_two, 36, current_row_top, 540, row_height, fill_color, (0.86, 0.9, 0.95), 0.4)
        values = [
            row["Date"],
            row["Day"],
            row["Condition"],
            row["Low"],
            row["High"],
            row["Rain"],
            row["Wind"],
            row["UV"],
        ]
        for (title, x_position, width), value in zip(headers, values):
            wrapped = wrap(_pdf_plain(value), width=max(6, int(width / 5.6))) or [""]
            draw_text(
                page_two,
                x_position + 6,
                current_row_top + row_text_offset,
                wrapped[0],
                font_name="F1",
                size=row_font_size,
                rgb=(0.2, 0.27, 0.36),
            )

    footer_top = min(760, row_top + (row_count * row_height) + 20)
    draw_text(
        page_two,
        36,
        footer_top,
        "Trip planning recommendations are based on the destination forecast range and the current snapshots included on page one.",
        font_name="F1",
        size=8,
        rgb=(0.42, 0.5, 0.6),
    )

    page_three = new_page()
    draw_rect(page_three, 36, 34, 540, 74, (0.15, 0.27, 0.44))
    draw_text(page_three, 54, 61, "Route & Activity Visuals", font_name="F2", size=20, rgb=(1, 1, 1))
    draw_text(page_three, 54, 86, route_display, font_name="F1", size=9, rgb=(0.88, 0.94, 0.99))

    map_top = 126
    map_height = 282
    map_left = 36
    map_width = 540
    map_inner_left = map_left + 16
    map_inner_top = map_top + 28
    map_inner_width = map_width - 32
    map_inner_height = map_height - 76

    draw_rect(page_three, map_left, map_top, map_width, map_height, (0.95, 0.97, 1.0), (0.82, 0.88, 0.94), 0.8)
    draw_text(page_three, 54, 148, "Route Sketch", font_name="F2", size=12, rgb=(0.11, 0.2, 0.31))
    draw_wrapped_text(
        page_three,
        54,
        170,
        "A simplified travel diagram showing the route, activity touchpoints, and the destination weather rhythm for the selected dates.",
        max_chars=84,
        font_name="F1",
        size=8,
        rgb=(0.22, 0.3, 0.39),
        line_gap=10,
    )

    draw_rect(page_three, map_inner_left, map_inner_top, map_inner_width, map_inner_height, (0.92, 0.96, 0.995), (0.84, 0.9, 0.96), 0.5)
    draw_rect(page_three, map_inner_left + 22, map_inner_top + 22, 146, 64, (0.89, 0.95, 0.99))
    draw_rect(page_three, map_inner_left + 258, map_inner_top + 18, 176, 82, (0.97, 0.98, 1.0))
    draw_rect(page_three, map_inner_left + 120, map_inner_top + 122, 214, 62, (0.91, 0.97, 0.95))
    draw_rect(page_three, map_inner_left + 372, map_inner_top + 132, 108, 42, (0.99, 0.96, 0.9))

    for step in range(1, 6):
        vertical_x = map_inner_left + (step * map_inner_width / 6)
        horizontal_top = map_inner_top + (step * map_inner_height / 6)
        draw_line(page_three, vertical_x, map_inner_top, vertical_x, map_inner_top + map_inner_height, (0.87, 0.91, 0.96), 0.5)
        draw_line(page_three, map_inner_left, horizontal_top, map_inner_left + map_inner_width, horizontal_top, (0.87, 0.91, 0.96), 0.5)

    draw_text(page_three, map_inner_left + map_inner_width - 18, map_inner_top + 18, "N", font_name="F2", size=8, rgb=(0.34, 0.42, 0.54))
    draw_line(page_three, map_inner_left + map_inner_width - 22, map_inner_top + 32, map_inner_left + map_inner_width - 22, map_inner_top + 50, (0.34, 0.42, 0.54), 1.2)
    draw_line(page_three, map_inner_left + map_inner_width - 26, map_inner_top + 36, map_inner_left + map_inner_width - 22, map_inner_top + 32, (0.34, 0.42, 0.54), 1.0)
    draw_line(page_three, map_inner_left + map_inner_width - 18, map_inner_top + 36, map_inner_left + map_inner_width - 22, map_inner_top + 32, (0.34, 0.42, 0.54), 1.0)

    route_line = bundle.get("route_line")
    if route_line:
        start_x = map_inner_left + (route_line["start_x"] * map_inner_width)
        start_top = map_inner_top + (route_line["start_y"] * map_inner_height)
        end_x = map_inner_left + (route_line["end_x"] * map_inner_width)
        end_top = map_inner_top + (route_line["end_y"] * map_inner_height)
        draw_line(page_three, start_x, start_top, end_x, end_top, (0.42, 0.55, 0.71), 2.2, dash=(7, 4))

    label_positions = {
        "origin": {"x": map_inner_left + 16, "top": map_inner_top + 98, "width": 92},
        "destination": {"x": map_inner_left + 246, "top": map_inner_top + 46, "width": 92},
        "outdoor": {"x": map_inner_left + 318, "top": map_inner_top + 8, "width": 112},
        "indoor": {"x": map_inner_left + 302, "top": map_inner_top + 118, "width": 110},
        "evening": {"x": map_inner_left + 278, "top": map_inner_top + 78, "width": 126},
    }

    for point in bundle.get("map_points", []):
        palette = point_palette.get(point.get("kind"), point_palette["destination"])
        point_x = map_inner_left + (point["x"] * map_inner_width)
        point_top = map_inner_top + (point["y"] * map_inner_height)
        draw_circle(page_three, point_x, point_top, 10, palette["soft"], palette["stroke"], 0.8)
        draw_circle(page_three, point_x, point_top, 5.4, palette["fill"], palette["stroke"], 0.6)

        fixed_label = label_positions.get(point.get("kind"), label_positions["destination"])
        label_x = fixed_label["x"]
        label_top = fixed_label["top"]
        label_width = fixed_label["width"]
        draw_map_label(
            page_three,
            label_x,
            label_top,
            label_width,
            point.get("label", ""),
            point.get("subtitle", ""),
            palette["soft"],
            palette["stroke"],
        )
        anchor_x = label_x if point_x < label_x else label_x + label_width
        anchor_top = label_top + 22
        draw_line(page_three, point_x, point_top, anchor_x, anchor_top, palette["stroke"], 0.6)

    legend_top = map_top + map_height - 38
    draw_rect(page_three, 52, legend_top, 508, 22, (0.96, 0.98, 1.0), (0.86, 0.9, 0.95), 0.4)
    legend_items = [
        ("origin", "Start"),
        ("destination", "Destination"),
        ("outdoor", "Outdoor window"),
        ("indoor", "Indoor backup"),
        ("evening", "Evening option"),
    ]
    legend_x = 68
    for kind, label in legend_items:
        palette = point_palette[kind]
        draw_circle(page_three, legend_x, legend_top + 11, 4.2, palette["fill"], palette["stroke"], 0.5)
        draw_text(page_three, legend_x + 10, legend_top + 14, label, font_name="F1", size=7, rgb=(0.27, 0.35, 0.45))
        legend_x += 94

    lower_top = 430
    climate_width = 336
    climate_height = 282
    draw_rect(page_three, 36, lower_top, climate_width, climate_height, (0.96, 0.98, 1.0), (0.82, 0.88, 0.94), 0.8)
    draw_text(page_three, 54, lower_top + 22, "Temperature Rhythm", font_name="F2", size=12, rgb=(0.11, 0.2, 0.31))
    draw_wrapped_text(
        page_three,
        54,
        lower_top + 44,
        "The daily range markers highlight where the trip feels steadier and where the destination shifts more between day and night.",
        max_chars=52,
        font_name="F1",
        size=8,
        rgb=(0.22, 0.3, 0.39),
        line_gap=10,
    )

    visual_days = bundle.get("visual_days", [])[:6]
    if visual_days:
        high_values = [day["high_value"] for day in visual_days]
        low_values = [day["low_value"] for day in visual_days]
        scale_min = min(low_values)
        scale_max = max(high_values)
        scale_span = max(1, scale_max - scale_min)
        chart_left = 74
        chart_right = 36 + climate_width - 24
        chart_top = lower_top + 100
        chart_bottom = lower_top + 212
        chart_height = chart_bottom - chart_top

        for guide in range(5):
            guide_top = chart_top + (guide * chart_height / 4)
            draw_line(page_three, chart_left, guide_top, chart_right, guide_top, (0.9, 0.93, 0.97), 0.5)

        step = (chart_right - chart_left) / max(1, len(visual_days))
        for index, day in enumerate(visual_days):
            center_x = chart_left + (step * index) + (step / 2)
            high_ratio = (day["high_value"] - scale_min) / scale_span
            low_ratio = (day["low_value"] - scale_min) / scale_span
            high_top = chart_bottom - (high_ratio * chart_height)
            low_top = chart_bottom - (low_ratio * chart_height)
            draw_line(page_three, center_x, high_top, center_x, low_top, (0.49, 0.67, 0.85), 5.0)
            draw_circle(page_three, center_x, high_top, 4.8, (0.79, 0.89, 0.98), (0.55, 0.71, 0.88), 0.5)
            draw_circle(page_three, center_x, low_top, 4.8, (0.35, 0.58, 0.79), (0.28, 0.49, 0.7), 0.5)
            draw_text(page_three, center_x - 14, high_top - 10, day["high_text"], font_name="F1", size=6, rgb=(0.3, 0.4, 0.5))
            draw_text(page_three, center_x - 14, low_top + 17, day["low_text"], font_name="F1", size=6, rgb=(0.3, 0.4, 0.5))
            draw_text(page_three, center_x - 16, chart_bottom + 18, day["label"], font_name="F2", size=7, rgb=(0.19, 0.27, 0.37))
            draw_text(page_three, center_x - 16, chart_bottom + 31, day["day"], font_name="F1", size=6, rgb=(0.34, 0.42, 0.52))

        draw_text(page_three, 54, lower_top + climate_height - 18, f'Temperature range shown in {bundle.get("temperature_unit", "").strip() or "selected units"}.', font_name="F1", size=8, rgb=(0.42, 0.5, 0.6))

    activity_card_left = 388
    activity_card_width = 188
    activity_card_height = 282
    draw_rect(page_three, activity_card_left, lower_top, activity_card_width, activity_card_height, (0.96, 0.98, 1.0), (0.82, 0.88, 0.94), 0.8)
    draw_text(page_three, activity_card_left + 18, lower_top + 22, "Activity Windows", font_name="F2", size=12, rgb=(0.11, 0.2, 0.31))
    draw_wrapped_text(
        page_three,
        activity_card_left + 18,
        lower_top + 44,
        "Quick cues pulled from the destination outlook for a cleaner offline read.",
        max_chars=26,
        font_name="F1",
        size=8,
        rgb=(0.22, 0.3, 0.39),
        line_gap=10,
    )

    activity_points = [point for point in bundle.get("map_points", []) if point.get("kind") in {"outdoor", "indoor", "evening"}][:3]
    activity_top = lower_top + 92
    for index, point in enumerate(activity_points):
        palette = point_palette.get(point["kind"], point_palette["destination"])
        block_top = activity_top + (index * 50)
        draw_rect(page_three, activity_card_left + 14, block_top, activity_card_width - 28, 42, palette["soft"], palette["stroke"], 0.5)
        draw_circle(page_three, activity_card_left + 30, block_top + 20, 5, palette["fill"], palette["stroke"], 0.5)
        draw_text(page_three, activity_card_left + 42, block_top + 14, point.get("label", ""), font_name="F2", size=8, rgb=(0.14, 0.21, 0.31))
        draw_text(page_three, activity_card_left + 42, block_top + 28, point.get("subtitle", ""), font_name="F1", size=7, rgb=(0.28, 0.36, 0.46))

    summary_top = lower_top + activity_card_height - 64
    draw_rect(page_three, activity_card_left + 14, summary_top, activity_card_width - 28, 46, (0.93, 0.96, 0.99), (0.84, 0.9, 0.96), 0.5)
    draw_text(page_three, activity_card_left + 26, summary_top + 15, "Planner Focus", font_name="F2", size=8, rgb=(0.29, 0.39, 0.5))
    draw_wrapped_text(
        page_three,
        activity_card_left + 26,
        summary_top + 28,
        f"Use page one for current conditions and page two for the full day-by-day forecast.",
        max_chars=26,
        font_name="F1",
        size=7,
        rgb=(0.34, 0.42, 0.52),
        line_gap=8,
    )

    content_streams = ["\n".join(page).encode("latin-1", errors="replace") for page in pages]
    return _build_multi_page_pdf_bytes(content_streams, page_width, page_height)


def _draw_brand_logo(draw_rect, draw_line, draw_text, x, top, scale=1.0):
    panel_width = 72 * scale
    panel_height = 58 * scale
    draw_rect(x, top, panel_width, panel_height, (0.92, 0.97, 1.0), (0.78, 0.88, 0.95), 0.6)
    skyline_top = top + (38 * scale)
    draw_line(x + (14 * scale), skyline_top, x + (58 * scale), skyline_top, (0.9, 0.97, 1.0), 2.4 * scale)
    draw_line(x + (22 * scale), skyline_top, x + (22 * scale), top + (24 * scale), (0.84, 0.94, 0.99), 3.2 * scale)
    draw_line(x + (33 * scale), skyline_top, x + (33 * scale), top + (18 * scale), (0.85, 0.95, 0.995), 4.0 * scale)
    draw_line(x + (45 * scale), skyline_top, x + (45 * scale), top + (12 * scale), (0.88, 0.96, 1.0), 4.6 * scale)
    draw_line(x + (57 * scale), skyline_top, x + (57 * scale), top + (22 * scale), (0.85, 0.95, 0.995), 3.8 * scale)
    draw_line(x + (18 * scale), top + (32 * scale), x + (28 * scale), top + (22 * scale), (0.96, 0.995, 1.0), 2.2 * scale)
    draw_line(x + (28 * scale), top + (22 * scale), x + (37 * scale), top + (18 * scale), (0.96, 0.995, 1.0), 2.2 * scale)
    draw_line(x + (37 * scale), top + (18 * scale), x + (48 * scale), top + (18 * scale), (0.96, 0.995, 1.0), 2.2 * scale)
    draw_text(x + (60 * scale), top + (17 * scale), "o", font_name="F2", size=9 * scale, rgb=(0.98, 1.0, 1.0))
    draw_text(x + (88 * scale), top + (16 * scale), "SKYLINE", font_name="F2", size=20 * scale, rgb=(1, 1, 1))
    draw_text(x + (90 * scale), top + (37 * scale), "FORECAST", font_name="F2", size=10 * scale, rgb=(0.86, 0.93, 0.98))
    draw_line(x + (88 * scale), top + (46 * scale), x + (198 * scale), top + (46 * scale), (0.82, 0.92, 0.98), 1.2 * scale)


def _build_pdf_export_v2(bundle):
    page_width = 612
    page_height = 792
    commands = []

    def page_y(top_offset):
        return page_height - top_offset

    def draw_rect(x, top, width, height, fill_rgb, stroke_rgb=None, line_width=1):
        y = page_height - top - height
        fill = f"{fill_rgb[0]:.3f} {fill_rgb[1]:.3f} {fill_rgb[2]:.3f} rg"
        if stroke_rgb is None:
            commands.append(f"{fill}\n{x:.2f} {y:.2f} {width:.2f} {height:.2f} re f")
            return
        stroke = f"{stroke_rgb[0]:.3f} {stroke_rgb[1]:.3f} {stroke_rgb[2]:.3f} RG"
        commands.append(
            f"{line_width:.2f} w\n{fill}\n{stroke}\n{x:.2f} {y:.2f} {width:.2f} {height:.2f} re B"
        )

    def draw_text(x, top, text, font_name="F1", size=11, rgb=(0.12, 0.2, 0.3)):
        safe_text = _pdf_escape(text)
        commands.append(
            "BT\n"
            f"/{font_name} {size} Tf\n"
            f"{rgb[0]:.3f} {rgb[1]:.3f} {rgb[2]:.3f} rg\n"
            f"1 0 0 1 {x:.2f} {page_y(top):.2f} Tm\n"
            f"({safe_text}) Tj\n"
            "ET"
        )

    def draw_line(x1, top1, x2, top2, stroke_rgb, line_width=1):
        commands.append(
            f"{line_width:.2f} w\n"
            f"{stroke_rgb[0]:.3f} {stroke_rgb[1]:.3f} {stroke_rgb[2]:.3f} RG\n"
            f"{x1:.2f} {page_y(top1):.2f} m\n"
            f"{x2:.2f} {page_y(top2):.2f} l S"
        )

    def draw_wrapped_text(x, top, text, max_chars, font_name="F1", size=10, rgb=(0.2, 0.27, 0.36), line_gap=13):
        lines = wrap(_pdf_plain(text), width=max_chars) or [""]
        for index, line in enumerate(lines):
            draw_text(x, top + (index * line_gap), line, font_name=font_name, size=size, rgb=rgb)
        return top + (len(lines) * line_gap)

    draw_rect(36, 34, 540, 92, (0.13, 0.25, 0.42))
    _draw_brand_logo(draw_rect, draw_line, draw_text, 54, 52, 0.74)
    draw_text(404, 66, "Weather Export", font_name="F2", size=17, rgb=(1, 1, 1))
    draw_text(
        54,
        112,
        f'{bundle["city"]} | {bundle["range_label"]} | Generated {bundle["generated_at"]}',
        font_name="F1",
        size=10,
        rgb=(0.92, 0.96, 1.0),
    )
    draw_text(
        54,
        128,
        f'Temperature Unit: {bundle["temperature_unit"]}   Wind Unit: {bundle["wind_unit"]}',
        font_name="F1",
        size=9,
        rgb=(0.86, 0.92, 0.98),
    )

    stat_cards = [
        ("Condition", bundle["current"]["Condition"]),
        ("Temperature", bundle["current"]["Temperature"]),
        ("Feels Like", bundle["current"]["Feels Like"]),
        ("Wind", bundle["current"]["Wind"]),
    ]
    card_width = 124
    card_gap = 12
    for index, (label, value) in enumerate(stat_cards):
        x_position = 36 + (index * (card_width + card_gap))
        draw_rect(x_position, 158, card_width, 72, (0.93, 0.96, 0.99), (0.82, 0.88, 0.94), 0.8)
        draw_text(x_position + 14, 180, label, font_name="F2", size=9, rgb=(0.32, 0.42, 0.55))
        draw_text(x_position + 14, 205, value, font_name="F2", size=13, rgb=(0.11, 0.2, 0.31))

    draw_rect(36, 248, 540, 110, (0.96, 0.98, 1.0), (0.82, 0.88, 0.94), 0.8)
    draw_text(54, 272, "Advisory Snapshot", font_name="F2", size=12, rgb=(0.11, 0.2, 0.31))
    next_top = draw_wrapped_text(
        54,
        296,
        "Alerts: " + " | ".join(alert["title"] for alert in bundle["alerts"]),
        max_chars=88,
        font_name="F1",
        size=9,
        rgb=(0.2, 0.27, 0.36),
        line_gap=12,
    )
    next_top = draw_wrapped_text(
        54,
        next_top + 6,
        f'Insight: {bundle["primary_insight"]["title"]}. {bundle["primary_insight"]["body"]}',
        max_chars=88,
        font_name="F1",
        size=9,
        rgb=(0.2, 0.27, 0.36),
        line_gap=12,
    )
    draw_wrapped_text(
        54,
        next_top + 6,
        "Scores: "
        + " | ".join(
            f'{score["label"]} {score["value"]}/10'
            for score in bundle["scores"]
        ),
        max_chars=88,
        font_name="F1",
        size=9,
        rgb=(0.2, 0.27, 0.36),
        line_gap=12,
    )

    table_top = 380
    draw_rect(36, table_top, 540, 28, (0.36, 0.49, 0.65))
    draw_text(52, table_top + 18, "Selected Date Window", font_name="F2", size=12, rgb=(1, 1, 1))

    headers = [
        ("Date", 36, 72),
        ("Condition", 108, 100),
        ("Low", 208, 54),
        ("High", 262, 54),
        ("Rain %", 316, 56),
        ("Rain Total", 372, 64),
        ("UV", 436, 38),
        ("Sunrise / Sunset", 474, 102),
    ]
    header_top = table_top + 38
    draw_rect(36, header_top, 540, 26, (0.88, 0.92, 0.97), (0.82, 0.88, 0.94), 0.6)
    for title, x_position, _ in headers:
        draw_text(x_position + 6, header_top + 17, title, font_name="F2", size=8, rgb=(0.18, 0.27, 0.38))

    row_top = header_top + 26
    available_table_height = 312
    row_count = max(1, len(bundle["forecast_rows"]))
    row_height = 26 if row_count <= 12 else max(16, int(available_table_height / row_count))
    row_text_offset = 17 if row_height >= 22 else max(11, row_height - 5)
    row_font_size = 8 if row_height >= 20 else 7
    for index, row in enumerate(bundle["forecast_rows"]):
        fill_color = (0.97, 0.98, 1.0) if index % 2 == 0 else (0.94, 0.97, 0.995)
        current_row_top = row_top + (index * row_height)
        draw_rect(36, current_row_top, 540, row_height, fill_color, (0.86, 0.9, 0.95), 0.4)
        values = [
            row["Date"],
            row["Condition"],
            row["Low"],
            row["High"],
            row["Rain Chance"],
            row["Rain Total"],
            row["UV Index"],
            f'{row["Sunrise"]} / {row["Sunset"]}',
        ]
        for (_, x_position, width), value in zip(headers, values):
            wrapped = wrap(_pdf_plain(value), width=max(8, int(width / 5.8))) or [""]
            draw_text(
                x_position + 6,
                current_row_top + row_text_offset,
                wrapped[0],
                font_name="F1",
                size=row_font_size,
                rgb=(0.2, 0.27, 0.36),
            )

    footer_text = "Export includes the current snapshot and the selected weather window."
    footer_top = min(756, row_top + (row_count * row_height) + 18)
    draw_text(36, footer_top, footer_text, font_name="F1", size=8, rgb=(0.42, 0.5, 0.6))

    return _build_pdf_bytes("\n".join(commands).encode("latin-1", errors="replace"), page_width, page_height)


def _build_trip_plan_pdf_v2(bundle):
    page_width = 612
    page_height = 792
    pages = []
    point_palette = {
        "origin": {"fill": (0.16, 0.31, 0.49), "soft": (0.9, 0.94, 0.99), "stroke": (0.26, 0.4, 0.58)},
        "destination": {"fill": (0.89, 0.47, 0.35), "soft": (0.99, 0.93, 0.9), "stroke": (0.79, 0.38, 0.28)},
        "comparison": {"fill": (0.45, 0.5, 0.67), "soft": (0.93, 0.94, 0.99), "stroke": (0.34, 0.39, 0.56)},
    }

    cities = bundle.get("cities", [])
    map_points = bundle.get("map_points", [])
    route_segments = bundle.get("route_segments", [])
    comparison_rows = bundle.get("comparison_rows", [])
    planner_highlights = bundle.get("planner_highlights", [])

    def new_page():
        commands = []
        pages.append(commands)
        return commands

    def page_y(top_offset):
        return page_height - top_offset

    def draw_rect(page, x, top, width, height, fill_rgb, stroke_rgb=None, line_width=1):
        y = page_height - top - height
        fill = f"{fill_rgb[0]:.3f} {fill_rgb[1]:.3f} {fill_rgb[2]:.3f} rg"
        if stroke_rgb is None:
            page.append(f"{fill}\n{x:.2f} {y:.2f} {width:.2f} {height:.2f} re f")
            return
        stroke = f"{stroke_rgb[0]:.3f} {stroke_rgb[1]:.3f} {stroke_rgb[2]:.3f} RG"
        page.append(
            f"{line_width:.2f} w\n{fill}\n{stroke}\n{x:.2f} {y:.2f} {width:.2f} {height:.2f} re B"
        )

    def draw_text(page, x, top, text, font_name="F1", size=11, rgb=(0.12, 0.2, 0.3)):
        safe_text = _pdf_escape(text)
        page.append(
            "BT\n"
            f"/{font_name} {size} Tf\n"
            f"{rgb[0]:.3f} {rgb[1]:.3f} {rgb[2]:.3f} rg\n"
            f"1 0 0 1 {x:.2f} {page_y(top):.2f} Tm\n"
            f"({safe_text}) Tj\n"
            "ET"
        )

    def draw_wrapped_text(page, x, top, text, max_chars, font_name="F1", size=10, rgb=(0.2, 0.27, 0.36), line_gap=13):
        lines = wrap(_pdf_plain(text), width=max_chars) or [""]
        for index, line in enumerate(lines):
            draw_text(page, x, top + (index * line_gap), line, font_name=font_name, size=size, rgb=rgb)
        return top + (len(lines) * line_gap)

    def draw_line(page, x1, top1, x2, top2, stroke_rgb, line_width=1, dash=None):
        dash_command = "[] 0 d"
        if dash:
            dash_command = f"[{dash[0]:.2f} {dash[1]:.2f}] 0 d"
        page.append(
            f"{line_width:.2f} w\n"
            f"{stroke_rgb[0]:.3f} {stroke_rgb[1]:.3f} {stroke_rgb[2]:.3f} RG\n"
            f"{dash_command}\n"
            f"{x1:.2f} {page_y(top1):.2f} m\n"
            f"{x2:.2f} {page_y(top2):.2f} l S"
        )

    def draw_circle(page, center_x, top_center, radius, fill_rgb, stroke_rgb=None, line_width=1):
        kappa = 0.5522847498
        control = radius * kappa
        center_y = page_y(top_center)
        path = (
            f"{center_x + radius:.2f} {center_y:.2f} m\n"
            f"{center_x + radius:.2f} {center_y + control:.2f} {center_x + control:.2f} {center_y + radius:.2f} {center_x:.2f} {center_y + radius:.2f} c\n"
            f"{center_x - control:.2f} {center_y + radius:.2f} {center_x - radius:.2f} {center_y + control:.2f} {center_x - radius:.2f} {center_y:.2f} c\n"
            f"{center_x - radius:.2f} {center_y - control:.2f} {center_x - control:.2f} {center_y - radius:.2f} {center_x:.2f} {center_y - radius:.2f} c\n"
            f"{center_x + control:.2f} {center_y - radius:.2f} {center_x + radius:.2f} {center_y - control:.2f} {center_x + radius:.2f} {center_y:.2f} c"
        )
        fill = f"{fill_rgb[0]:.3f} {fill_rgb[1]:.3f} {fill_rgb[2]:.3f} rg"
        if stroke_rgb is None:
            page.append(f"{fill}\n{path}\nf")
            return
        stroke = f"{stroke_rgb[0]:.3f} {stroke_rgb[1]:.3f} {stroke_rgb[2]:.3f} RG"
        page.append(f"{line_width:.2f} w\n{fill}\n{stroke}\n{path}\nB")

    def draw_brand_logo(page, x, top, scale=1.0):
        _draw_brand_logo(
            lambda rx, rt, rw, rh, fill_rgb, stroke_rgb=None, line_width=1: draw_rect(page, rx, rt, rw, rh, fill_rgb, stroke_rgb, line_width),
            lambda x1, t1, x2, t2, stroke_rgb, line_width=1: draw_line(page, x1, t1, x2, t2, stroke_rgb, line_width),
            lambda tx, tt, text, font_name="F1", size=11, rgb=(0.12, 0.2, 0.3): draw_text(page, tx, tt, text, font_name, size, rgb),
            x,
            top,
            scale,
        )

    def draw_metric_card(page, x, top, width, height, label, value, body):
        draw_rect(page, x, top, width, height, (0.95, 0.97, 1.0), (0.82, 0.88, 0.94), 0.7)
        draw_text(page, x + 14, top + 18, label, font_name="F2", size=8, rgb=(0.35, 0.45, 0.57))
        next_top = draw_wrapped_text(
            page,
            x + 14,
            top + 38,
            value,
            max_chars=max(14, int(width / 7.2)),
            font_name="F2",
            size=11,
            rgb=(0.11, 0.2, 0.31),
            line_gap=12,
        )
        draw_wrapped_text(
            page,
            x + 14,
            next_top + 2,
            body,
            max_chars=max(18, int(width / 6.2)),
            font_name="F1",
            size=8,
            rgb=(0.23, 0.31, 0.41),
            line_gap=9,
        )

    def draw_cell_text(page, x, top, width, height, text, font_name="F1", size=7, rgb=(0.2, 0.27, 0.36)):
        lines = wrap(_pdf_plain(text), width=max(8, int(width / 5.9))) or [""]
        if len(lines) > 3:
            lines = lines[:2] + [lines[2][: max(4, len(lines[2]) - 3)] + "..."]
        line_gap = 8
        start_top = top + max(12, (height - (len(lines) * line_gap)) / 2 + 5)
        for index, line in enumerate(lines):
            draw_text(page, x + 6, start_top + (index * line_gap), line, font_name=font_name, size=size, rgb=rgb)

    cover_page = new_page()
    draw_rect(cover_page, 36, 34, 540, 92, (0.13, 0.25, 0.42))
    draw_brand_logo(cover_page, 54, 52, 0.74)
    draw_text(cover_page, 402, 64, "Trip Planner PDF", font_name="F2", size=17, rgb=(1, 1, 1))
    route_top = draw_wrapped_text(
        cover_page,
        54,
        112,
        bundle.get("route_label", "Trip Planner"),
        max_chars=72,
        font_name="F2",
        size=14,
        rgb=(0.95, 0.98, 1.0),
        line_gap=14,
    )
    draw_text(
        cover_page,
        54,
        route_top + 4,
        f'{bundle.get("date_range_label", "")} | {bundle.get("city_count", 0)} cities | Generated {bundle.get("generated_at", "")}',
        font_name="F1",
        size=9,
        rgb=(0.86, 0.92, 0.98),
    )

    draw_rect(cover_page, 36, 156, 540, 94, (0.96, 0.98, 1.0), (0.82, 0.88, 0.94), 0.8)
    draw_text(cover_page, 54, 180, "Planner Overview", font_name="F2", size=12, rgb=(0.11, 0.2, 0.31))
    draw_wrapped_text(
        cover_page,
        54,
        204,
        bundle.get("overview_body", ""),
        max_chars=90,
        font_name="F1",
        size=9,
        rgb=(0.2, 0.27, 0.36),
        line_gap=12,
    )

    card_count = max(1, len(cities))
    if card_count <= 2:
        cover_columns = 2
    elif card_count <= 4:
        cover_columns = 2
    else:
        cover_columns = 3
    card_gap = 12
    cover_card_width = (540 - ((cover_columns - 1) * card_gap)) / cover_columns
    cover_card_height = 94 if cover_columns == 2 else 90
    cards_top = 270
    for index, city in enumerate(cities):
        row_index = index // cover_columns
        column_index = index % cover_columns
        x_position = 36 + (column_index * (cover_card_width + card_gap))
        top_position = cards_top + (row_index * (cover_card_height + 12))
        draw_rect(cover_page, x_position, top_position, cover_card_width, cover_card_height, (0.95, 0.97, 1.0), (0.83, 0.89, 0.95), 0.6)
        draw_text(cover_page, x_position + 14, top_position + 16, city.get("role_label", "City"), font_name="F2", size=8, rgb=(0.36, 0.46, 0.58))
        draw_wrapped_text(
            cover_page,
            x_position + 14,
            top_position + 34,
            city.get("short_name", ""),
            max_chars=max(12, int(cover_card_width / 7.0)),
            font_name="F2",
            size=11,
            rgb=(0.11, 0.2, 0.31),
            line_gap=11,
        )
        draw_text(cover_page, x_position + 14, top_position + 58, city.get("current_summary", ""), font_name="F1", size=8, rgb=(0.22, 0.31, 0.41))
        draw_wrapped_text(
            cover_page,
            x_position + 14,
            top_position + 72,
            f'Trip range {city.get("comparison_values", {}).get("Trip Range", "--")} | Best {city.get("best_day_label", "--")}',
            max_chars=max(16, int(cover_card_width / 6.1)),
            font_name="F1",
            size=7,
            rgb=(0.28, 0.36, 0.46),
            line_gap=8,
        )

    if planner_highlights:
        highlight_top = 590 if cover_columns == 3 else 568
        draw_text(cover_page, 36, highlight_top, "Quick Comparison Highlights", font_name="F2", size=12, rgb=(0.11, 0.2, 0.31))
        highlight_card_width = (540 - 24) / 3
        for index, item in enumerate(planner_highlights[:3]):
            x_position = 36 + (index * (highlight_card_width + 12))
            draw_metric_card(cover_page, x_position, highlight_top + 18, highlight_card_width, 82, item["label"], item["value"], item["body"])

    map_page = new_page()
    draw_rect(map_page, 36, 34, 540, 80, (0.15, 0.27, 0.44))
    draw_brand_logo(map_page, 54, 48, 0.66)
    draw_text(map_page, 416, 62, "Route Overview", font_name="F2", size=16, rgb=(1, 1, 1))
    draw_text(map_page, 54, 102, bundle.get("route_label", ""), font_name="F1", size=9, rgb=(0.88, 0.94, 0.99))

    map_top = 124
    map_height = 286
    draw_rect(map_page, 36, map_top, 540, map_height, (0.95, 0.97, 1.0), (0.82, 0.88, 0.94), 0.8)
    draw_text(map_page, 54, map_top + 22, "Geographic Route Sketch", font_name="F2", size=12, rgb=(0.11, 0.2, 0.31))
    draw_wrapped_text(
        map_page,
        54,
        map_top + 44,
        "The route page now places each chosen city according to its latitude and longitude instead of using fixed fake map markers.",
        max_chars=86,
        font_name="F1",
        size=8,
        rgb=(0.22, 0.3, 0.39),
        line_gap=10,
    )

    map_canvas_left = 52
    map_canvas_top = map_top + 72
    map_canvas_width = 508
    map_canvas_height = 156
    draw_rect(map_page, map_canvas_left, map_canvas_top, map_canvas_width, map_canvas_height, (0.92, 0.96, 0.995), (0.84, 0.9, 0.96), 0.5)
    for step in range(1, 6):
        vertical_x = map_canvas_left + (step * map_canvas_width / 6)
        horizontal_top = map_canvas_top + (step * map_canvas_height / 6)
        draw_line(map_page, vertical_x, map_canvas_top, vertical_x, map_canvas_top + map_canvas_height, (0.87, 0.91, 0.96), 0.5)
        draw_line(map_page, map_canvas_left, horizontal_top, map_canvas_left + map_canvas_width, horizontal_top, (0.87, 0.91, 0.96), 0.5)

    for segment in route_segments:
        start_x = map_canvas_left + (segment["start_x"] * map_canvas_width)
        start_top = map_canvas_top + (segment["start_y"] * map_canvas_height)
        end_x = map_canvas_left + (segment["end_x"] * map_canvas_width)
        end_top = map_canvas_top + (segment["end_y"] * map_canvas_height)
        draw_line(map_page, start_x, start_top, end_x, end_top, (0.44, 0.57, 0.74), 1.8, dash=(6, 3))

    for point in map_points:
        palette = point_palette.get(point.get("kind"), point_palette["comparison"])
        point_x = map_canvas_left + (point["x"] * map_canvas_width)
        point_top = map_canvas_top + (point["y"] * map_canvas_height)
        draw_circle(map_page, point_x, point_top, 10, palette["soft"], palette["stroke"], 0.8)
        draw_circle(map_page, point_x, point_top, 6.2, palette["fill"], palette["stroke"], 0.6)
        draw_text(map_page, point_x - 2.8, point_top + 2.8, str(point["index"]), font_name="F2", size=7, rgb=(1, 1, 1))

    legend_top = map_top + 240
    legend_columns = 2
    legend_width = (508 - 12) / legend_columns
    for index, point in enumerate(map_points):
        row_index = index // legend_columns
        column_index = index % legend_columns
        block_x = 52 + (column_index * (legend_width + 12))
        block_top = legend_top + (row_index * 22)
        palette = point_palette.get(point.get("kind"), point_palette["comparison"])
        draw_circle(map_page, block_x + 8, block_top + 9, 4.3, palette["fill"], palette["stroke"], 0.5)
        draw_text(map_page, block_x + 18, block_top + 12, f'{point["index"]}. {point["label"]} ({point["subtitle"]})', font_name="F2", size=7, rgb=(0.16, 0.24, 0.34))
        draw_text(map_page, block_x + 18, block_top + 21, f'{point["summary"]} | {point["latitude"]}, {point["longitude"]}', font_name="F1", size=6, rgb=(0.31, 0.39, 0.49))

    comparison_top = 432
    draw_rect(map_page, 36, comparison_top, 540, 300, (0.96, 0.98, 1.0), (0.82, 0.88, 0.94), 0.8)
    draw_text(map_page, 54, comparison_top + 22, "City Comparison Matrix", font_name="F2", size=12, rgb=(0.11, 0.2, 0.31))
    draw_wrapped_text(
        map_page,
        54,
        comparison_top + 44,
        "The matrix keeps the selected cities side by side for the same travel window, so you can compare present conditions and trip-level signals without jumping between pages.",
        max_chars=88,
        font_name="F1",
        size=8,
        rgb=(0.22, 0.3, 0.39),
        line_gap=10,
    )

    header_row_top = comparison_top + 76
    metric_column_width = 108
    value_column_width = (540 - metric_column_width) / max(1, len(cities))
    draw_rect(map_page, 36, header_row_top, 540, 24, (0.88, 0.92, 0.97), (0.82, 0.88, 0.94), 0.5)
    draw_text(map_page, 44, header_row_top + 16, "Metric", font_name="F2", size=8, rgb=(0.18, 0.27, 0.38))
    for index, city in enumerate(cities):
        cell_x = 36 + metric_column_width + (index * value_column_width)
        draw_text(map_page, cell_x + 6, header_row_top + 16, city.get("short_name", ""), font_name="F2", size=8, rgb=(0.18, 0.27, 0.38))

    matrix_row_top = header_row_top + 24
    matrix_row_height = 28 if len(cities) <= 4 else 32
    for index, row in enumerate(comparison_rows[:7]):
        current_top = matrix_row_top + (index * matrix_row_height)
        fill_color = (0.97, 0.98, 1.0) if index % 2 == 0 else (0.94, 0.97, 0.995)
        draw_rect(map_page, 36, current_top, 540, matrix_row_height, fill_color, (0.86, 0.9, 0.95), 0.4)
        draw_cell_text(map_page, 36, current_top, metric_column_width, matrix_row_height, row["label"], font_name="F2", size=7, rgb=(0.17, 0.26, 0.36))
        for city_index, value in enumerate(row.get("values", [])):
            cell_x = 36 + metric_column_width + (city_index * value_column_width)
            draw_cell_text(map_page, cell_x, current_top, value_column_width, matrix_row_height, value, font_name="F1", size=6 if len(cities) >= 5 else 7)

    for city in cities:
        detail_page = new_page()
        draw_rect(detail_page, 36, 34, 540, 84, (0.15, 0.27, 0.44))
        draw_brand_logo(detail_page, 54, 50, 0.68)
        draw_text(detail_page, 54, 128, city.get("city_name", ""), font_name="F2", size=18, rgb=(0.11, 0.2, 0.31))
        draw_text(detail_page, 54, 148, f'{city.get("role_label", "City")} | {bundle.get("date_range_label", "")}', font_name="F1", size=9, rgb=(0.33, 0.41, 0.52))

        draw_rect(detail_page, 36, 166, 540, 84, (0.96, 0.98, 1.0), (0.82, 0.88, 0.94), 0.8)
        draw_text(detail_page, 54, 190, "City Summary", font_name="F2", size=12, rgb=(0.11, 0.2, 0.31))
        draw_wrapped_text(
            detail_page,
            54,
            214,
            city.get("overview_body", ""),
            max_chars=90,
            font_name="F1",
            size=9,
            rgb=(0.2, 0.27, 0.36),
            line_gap=12,
        )

        note_cards = city.get("note_cards", [])[:4]
        note_top = 268
        note_width = 264
        note_height = 64
        for index, note in enumerate(note_cards):
            row_index = index // 2
            column_index = index % 2
            x_position = 36 + (column_index * (note_width + 12))
            top_position = note_top + (row_index * (note_height + 12))
            draw_metric_card(detail_page, x_position, top_position, note_width, note_height, note.get("label", ""), note.get("value", ""), note.get("body", ""))

        table_top = 424
        draw_rect(detail_page, 36, table_top, 540, 28, (0.36, 0.49, 0.65))
        draw_text(detail_page, 52, table_top + 18, "Daily Forecast Window", font_name="F2", size=12, rgb=(1, 1, 1))

        headers = [
            ("Date", 36, 86),
            ("Day", 122, 44),
            ("Condition", 166, 96),
            ("Low", 262, 54),
            ("High", 316, 54),
            ("Rain", 370, 54),
            ("Wind", 424, 86),
            ("UV", 510, 66),
        ]
        header_top = table_top + 38
        draw_rect(detail_page, 36, header_top, 540, 24, (0.88, 0.92, 0.97), (0.82, 0.88, 0.94), 0.5)
        for title, x_position, _ in headers:
            draw_text(detail_page, x_position + 6, header_top + 16, title, font_name="F2", size=8, rgb=(0.18, 0.27, 0.38))

        row_top = header_top + 24
        row_count = max(1, len(city.get("daily_rows", [])))
        available_table_height = 250
        row_height = 26 if row_count <= 10 else max(18, int(available_table_height / row_count))
        row_text_offset = 16 if row_height >= 22 else max(10, row_height - 6)
        row_font_size = 7 if row_height >= 20 else 6
        for index, row in enumerate(city.get("daily_rows", [])):
            current_top = row_top + (index * row_height)
            fill_color = (0.97, 0.98, 1.0) if index % 2 == 0 else (0.94, 0.97, 0.995)
            draw_rect(detail_page, 36, current_top, 540, row_height, fill_color, (0.86, 0.9, 0.95), 0.4)
            row_values = [
                row["Date"],
                row["Day"],
                row["Condition"],
                row["Low"],
                row["High"],
                row["Rain"],
                row["Wind"],
                row["UV"],
            ]
            for (_, x_position, width), value in zip(headers, row_values):
                wrapped = wrap(_pdf_plain(value), width=max(6, int(width / 5.7))) or [""]
                draw_text(detail_page, x_position + 6, current_top + row_text_offset, wrapped[0], font_name="F1", size=row_font_size, rgb=(0.2, 0.27, 0.36))

        draw_text(
            detail_page,
            36,
            756,
            "This page keeps the same date range used across the comparison matrix so the city-to-city read stays aligned.",
            font_name="F1",
            size=8,
            rgb=(0.42, 0.5, 0.6),
        )

    content_streams = ["\n".join(page).encode("latin-1", errors="replace") for page in pages]
    return _build_multi_page_pdf_bytes(content_streams, page_width, page_height)


def _build_overview_sheet_xml(bundle):
    row_cells = {}
    merged_ranges = []
    column_widths = {
        1: 18,
        2: 18,
        3: 18,
        4: 18,
        5: 4,
        6: 18,
        7: 18,
        8: 18,
        9: 18,
        10: 18,
    }

    def add_cell(row_index, column_index, value, style_id):
        ref = f"{_xlsx_column_name(column_index)}{row_index}"
        row_cells.setdefault(row_index, []).append((column_index, _xlsx_inline_cell(ref, value, style_id)))

    add_cell(1, 1, "SKYLINE FORECAST", 1)
    merged_ranges.append("A1:J1")
    add_cell(2, 1, f'{bundle["city"]} | {bundle["range_label"]} | Generated {bundle["generated_at"]}', 2)
    merged_ranges.append("A2:J2")

    add_cell(4, 1, "Current Conditions", 3)
    merged_ranges.append("A4:D4")
    add_cell(4, 6, "Export Details", 3)
    merged_ranges.append("F4:J4")

    current_pairs = [
        ("Condition", bundle["current"]["Condition"]),
        ("Temperature", bundle["current"]["Temperature"]),
        ("Feels Like", bundle["current"]["Feels Like"]),
        ("Humidity", bundle["current"]["Humidity"]),
        ("Wind", bundle["current"]["Wind"]),
        ("Pressure", bundle["current"]["Pressure"]),
        ("Visibility", bundle["current"]["Visibility"]),
        ("Precipitation", bundle["current"]["Precipitation"]),
    ]
    positions = [
        (5, 1, 2),
        (6, 1, 2),
        (7, 1, 2),
        (8, 1, 2),
        (5, 3, 4),
        (6, 3, 4),
        (7, 3, 4),
        (8, 3, 4),
    ]
    for (label, value), (row_index, label_col, value_col) in zip(current_pairs, positions):
        add_cell(row_index, label_col, label, 5)
        add_cell(row_index, value_col, value, 6)

    detail_pairs = [
        ("Range", bundle["range_label"]),
        ("Temperature Unit", bundle["temperature_unit"]),
        ("Wind Unit", bundle["wind_unit"]),
        ("Days Included", str(bundle["days_count"])),
    ]
    for offset, (label, value) in enumerate(detail_pairs, start=5):
        add_cell(offset, 6, label, 5)
        add_cell(offset, 7, value, 6)
        merged_ranges.append(f"G{offset}:J{offset}")

    add_cell(10, 1, "Advisory Snapshot", 3)
    merged_ranges.append("A10:J10")
    advisory_lines = [
        "Top Alerts: " + " | ".join(alert["title"] for alert in bundle["alerts"]),
        f'Primary Insight: {bundle["primary_insight"]["title"]}',
        bundle["primary_insight"]["body"],
        "Scores: "
        + " | ".join(
            f'{score["label"]} {score["value"]}/10'
            for score in bundle["scores"]
        ),
    ]
    add_cell(11, 1, "\n".join(advisory_lines), 8)
    merged_ranges.append("A11:J13")

    add_cell(15, 1, "Selected Weather Window", 3)
    merged_ranges.append("A15:J15")

    headers = [
        "Date",
        "Day",
        "Condition",
        "Low",
        "High",
        "Rain Chance",
        "Rain Total",
        "UV Index",
        "Sunrise",
        "Sunset",
    ]
    for index, header in enumerate(headers, start=1):
        add_cell(16, index, header, 4)
    for row_offset, forecast_row in enumerate(bundle["forecast_rows"], start=17):
        for col_index, header in enumerate(headers, start=1):
            add_cell(row_offset, col_index, forecast_row[header], 7)

    return _build_sheet_xml(row_cells, merged_ranges, column_widths)


def _build_forecast_sheet_xml(bundle):
    row_cells = {}
    merged_ranges = []
    column_widths = {
        1: 14,
        2: 10,
        3: 18,
        4: 11,
        5: 11,
        6: 13,
        7: 13,
        8: 10,
        9: 12,
        10: 12,
    }

    def add_cell(row_index, column_index, value, style_id):
        ref = f"{_xlsx_column_name(column_index)}{row_index}"
        row_cells.setdefault(row_index, []).append((column_index, _xlsx_inline_cell(ref, value, style_id)))

    add_cell(1, 1, "SKYLINE FORECAST", 1)
    merged_ranges.append("A1:J1")
    add_cell(2, 1, f'{bundle["city"]} | {bundle["range_label"]} forecast breakdown', 2)
    merged_ranges.append("A2:J2")
    add_cell(4, 1, "Daily Weather Window Table", 3)
    merged_ranges.append("A4:J4")

    headers = [
        "Date",
        "Day",
        "Condition",
        "Low",
        "High",
        "Rain Chance",
        "Rain Total",
        "UV Index",
        "Sunrise",
        "Sunset",
    ]
    for index, header in enumerate(headers, start=1):
        add_cell(5, index, header, 4)
    for row_offset, forecast_row in enumerate(bundle["forecast_rows"], start=6):
        for col_index, header in enumerate(headers, start=1):
            add_cell(row_offset, col_index, forecast_row[header], 7)

    return _build_sheet_xml(row_cells, merged_ranges, column_widths)


def _build_sheet_xml(row_cells, merged_ranges, column_widths):
    rows_xml = []
    for row_index in sorted(row_cells):
        cells = "".join(
            cell_xml
            for _, cell_xml in sorted(row_cells[row_index], key=lambda item: item[0])
        )
        rows_xml.append(f'<row r="{row_index}">{cells}</row>')

    cols_xml = "".join(
        f'<col min="{column_index}" max="{column_index}" width="{width}" customWidth="1"/>'
        for column_index, width in sorted(column_widths.items())
    )
    merge_xml = ""
    if merged_ranges:
        merge_items = "".join(f'<mergeCell ref="{cell_range}"/>' for cell_range in merged_ranges)
        merge_xml = f'<mergeCells count="{len(merged_ranges)}">{merge_items}</mergeCells>'

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<cols>{cols_xml}</cols>"
        f"<sheetData>{''.join(rows_xml)}</sheetData>"
        f"{merge_xml}"
        "</worksheet>"
    )


def _xlsx_column_name(column_index):
    letters = ""
    index = column_index
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _xlsx_inline_cell(reference, value, style_id):
    text = xml_escape("" if value is None else str(value), quote=False).replace("\n", "&#10;")
    return (
        f'<c r="{reference}" s="{style_id}" t="inlineStr">'
        f'<is><t xml:space="preserve">{text}</t></is>'
        "</c>"
    )


def _build_content_types_xml():
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>"""


def _build_root_relationships_xml():
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""


def _build_app_properties_xml():
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Skyline Forecast</Application>
  <HeadingPairs>
    <vt:vector size="2" baseType="variant">
      <vt:variant><vt:lpstr>Worksheets</vt:lpstr></vt:variant>
      <vt:variant><vt:i4>2</vt:i4></vt:variant>
    </vt:vector>
  </HeadingPairs>
  <TitlesOfParts>
    <vt:vector size="2" baseType="lpstr">
      <vt:lpstr>Overview</vt:lpstr>
      <vt:lpstr>Forecast</vt:lpstr>
    </vt:vector>
  </TitlesOfParts>
</Properties>"""


def _build_core_properties_xml():
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:creator>OpenAI Codex</dc:creator>
  <cp:lastModifiedBy>OpenAI Codex</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{now_iso}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{now_iso}</dcterms:modified>
</cp:coreProperties>"""


def _build_workbook_xml():
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Overview" sheetId="1" r:id="rId1"/>
    <sheet name="Forecast" sheetId="2" r:id="rId2"/>
  </sheets>
</workbook>"""


def _build_workbook_relationships_xml():
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""


def _build_styles_xml():
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="4">
    <font><sz val="11"/><name val="Calibri"/></font>
    <font><b/><sz val="11"/><name val="Calibri"/></font>
    <font><b/><sz val="18"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>
    <font><sz val="11"/><color rgb="FFEAF2FB"/><name val="Calibri"/></font>
  </fonts>
  <fills count="6">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF1F426B"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF5D7EA6"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFEFF5FC"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFD8E4F2"/><bgColor indexed="64"/></patternFill></fill>
  </fills>
  <borders count="2">
    <border><left/><right/><top/><bottom/><diagonal/></border>
    <border>
      <left style="thin"><color rgb="FFC8D5E5"/></left>
      <right style="thin"><color rgb="FFC8D5E5"/></right>
      <top style="thin"><color rgb="FFC8D5E5"/></top>
      <bottom style="thin"><color rgb="FFC8D5E5"/></bottom>
      <diagonal/>
    </border>
  </borders>
  <cellStyleXfs count="1">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>
  </cellStyleXfs>
  <cellXfs count="9">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="2" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="left" vertical="center"/></xf>
    <xf numFmtId="0" fontId="3" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="left" vertical="center"/></xf>
    <xf numFmtId="0" fontId="1" fillId="5" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="left" vertical="center"/></xf>
    <xf numFmtId="0" fontId="1" fillId="3" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
    <xf numFmtId="0" fontId="1" fillId="4" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="left" vertical="center"/></xf>
    <xf numFmtId="0" fontId="0" fillId="4" borderId="1" xfId="0" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="left" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1"><alignment horizontal="left" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="0" fillId="4" borderId="1" xfId="0" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="left" vertical="top" wrapText="1"/></xf>
  </cellXfs>
  <cellStyles count="1">
    <cellStyle name="Normal" xfId="0" builtinId="0"/>
  </cellStyles>
  <dxfs count="0"/>
  <tableStyles count="0" defaultTableStyle="TableStyleMedium2" defaultPivotStyle="PivotStyleLight16"/>
</styleSheet>"""


def _pdf_plain(text):
    normalized = unicodedata.normalize("NFKD", str(text))
    latin_text = normalized.encode("latin-1", "ignore").decode("latin-1")
    return latin_text.replace("\r", " ").replace("\n", " ").strip()


def _pdf_escape(text):
    safe = _pdf_plain(text)
    safe = safe.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return safe.encode("latin-1", errors="replace").decode("latin-1")


def _build_pdf_bytes(content_stream, page_width, page_height):
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_width} {page_height}] "
            "/Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>"
        ).encode("ascii"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content_stream), content_stream),
    ]

    pdf = io.BytesIO()
    pdf.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_id, object_body in enumerate(objects, start=1):
        offsets.append(pdf.tell())
        pdf.write(f"{object_id} 0 obj\n".encode("ascii"))
        pdf.write(object_body)
        pdf.write(b"\nendobj\n")

    xref_position = pdf.tell()
    pdf.write(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.write(f"{offset:010d} 00000 n \n".encode("ascii"))

    pdf.write(
        (
            "trailer\n"
            f"<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            "startxref\n"
            f"{xref_position}\n"
            "%%EOF"
        ).encode("ascii")
    )
    return pdf.getvalue()


def _build_multi_page_pdf_bytes(content_streams, page_width, page_height):
    page_count = len(content_streams)
    page_object_ids = [3 + index for index in range(page_count)]
    font_one_id = 3 + page_count
    font_two_id = font_one_id + 1
    content_ids = [font_two_id + 1 + index for index in range(page_count)]

    kids_refs = " ".join(f"{page_id} 0 R" for page_id in page_object_ids)
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids_refs}] /Count {page_count} >>".encode("ascii"),
    ]

    for page_id, content_id in zip(page_object_ids, content_ids):
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_width} {page_height}] "
                f"/Resources << /Font << /F1 {font_one_id} 0 R /F2 {font_two_id} 0 R >> >> "
                f"/Contents {content_id} 0 R >>"
            ).encode("ascii")
        )

    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")

    for content_stream in content_streams:
        objects.append(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content_stream), content_stream))

    pdf = io.BytesIO()
    pdf.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_id, object_body in enumerate(objects, start=1):
        offsets.append(pdf.tell())
        pdf.write(f"{object_id} 0 obj\n".encode("ascii"))
        pdf.write(object_body)
        pdf.write(b"\nendobj\n")

    xref_position = pdf.tell()
    pdf.write(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.write(f"{offset:010d} 00000 n \n".encode("ascii"))

    pdf.write(
        (
            "trailer\n"
            f"<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            "startxref\n"
            f"{xref_position}\n"
            "%%EOF"
        ).encode("ascii")
    )
    return pdf.getvalue()
