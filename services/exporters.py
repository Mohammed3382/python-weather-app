import io
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

    write_row(["Skyline Forecast Export"])
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

    def draw_wrapped_text(x, top, text, max_chars, font_name="F1", size=10, rgb=(0.2, 0.27, 0.36), line_gap=13):
        lines = wrap(_pdf_plain(text), width=max_chars) or [""]
        for index, line in enumerate(lines):
            draw_text(x, top + (index * line_gap), line, font_name=font_name, size=size, rgb=rgb)
        return top + (len(lines) * line_gap)

    draw_rect(36, 34, 540, 84, (0.13, 0.25, 0.42))
    draw_text(54, 63, "Skyline Forecast Export", font_name="F2", size=22, rgb=(1, 1, 1))
    draw_text(
        54,
        88,
        f'{bundle["city"]} | {bundle["range_label"]} | Generated {bundle["generated_at"]}',
        font_name="F1",
        size=10,
        rgb=(0.92, 0.96, 1.0),
    )
    draw_text(
        54,
        105,
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
        draw_rect(x_position, 138, card_width, 72, (0.93, 0.96, 0.99), (0.82, 0.88, 0.94), 0.8)
        draw_text(x_position + 14, 160, label, font_name="F2", size=9, rgb=(0.32, 0.42, 0.55))
        draw_text(x_position + 14, 185, value, font_name="F2", size=13, rgb=(0.11, 0.2, 0.31))

    draw_rect(36, 228, 540, 108, (0.96, 0.98, 1.0), (0.82, 0.88, 0.94), 0.8)
    draw_text(54, 252, "Advisory Snapshot", font_name="F2", size=12, rgb=(0.11, 0.2, 0.31))
    next_top = draw_wrapped_text(
        54,
        276,
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

    table_top = 356
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
    page_width = 612
    page_height = 792
    pages = []

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

    page_one = new_page()
    draw_rect(page_one, 36, 34, 540, 92, (0.13, 0.25, 0.42))
    draw_text(page_one, 54, 62, "Skyline Forecast Trip Plan", font_name="F2", size=22, rgb=(1, 1, 1))
    route_top = draw_wrapped_text(
        page_one,
        54,
        88,
        bundle["route_label"],
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

    draw_rect(page_one, 36, 146, 540, 96, (0.96, 0.98, 1.0), (0.82, 0.88, 0.94), 0.8)
    draw_text(page_one, 54, 168, "Trip Summary", font_name="F2", size=12, rgb=(0.11, 0.2, 0.31))
    draw_wrapped_text(
        page_one,
        54,
        194,
        bundle["overview_body"],
        max_chars=92,
        font_name="F1",
        size=9,
        rgb=(0.2, 0.27, 0.36),
        line_gap=12,
    )

    snapshot_cards = bundle["snapshot_cards"][:4]
    card_width = 264
    card_height = 78
    card_gap = 12
    snapshot_top = 262
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

    packing_title_top = 448
    draw_text(page_one, 36, packing_title_top, "Packing Recommendations", font_name="F2", size=12, rgb=(0.11, 0.2, 0.31))
    packing_cards = bundle["packing_items"][:6]
    packing_top = 472
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
    draw_text(page_two, 54, 86, bundle["route_label"], font_name="F1", size=9, rgb=(0.88, 0.94, 0.99))

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

    add_cell(1, 1, "Skyline Forecast Export", 1)
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

    add_cell(1, 1, "Skyline Forecast Export", 1)
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
    return str(text).replace("\r", " ").replace("\n", " ").strip()


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
