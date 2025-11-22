import os
import sys
import json
from dataclasses import dataclass
from datetime import datetime
from typing import List


# ================== MODELS ==================

@dataclass
class IcsEvent:
    start: datetime
    end: datetime
    summary: str
    description: str
    location: str


# ================== ICS PARSER ==================

def parse_ics_datetime(value: str) -> datetime:
    """Parse datetime ICS kiểu 20251117T070000 hoặc 20251117T0700."""
    value = value.strip()
    if value.endswith("Z"):
        value = value[:-1]

    if len(value) == 15:      # 20251117T070000
        fmt = "%Y%m%dT%H%M%S"
    elif len(value) == 13:    # 20251117T0700
        fmt = "%Y%m%dT%H%M"
    else:                     # fallback
        value = value.replace("T", "")
        fmt = "%Y%m%d%H%M"

    return datetime.strptime(value, fmt)


def parse_ics_file(file_path: str) -> List[IcsEvent]:
    events: List[IcsEvent] = []

    with open(file_path, "r", encoding="utf-8") as f:
        lines = [line.rstrip("\n") for line in f]

    in_event = False
    current = {}

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        if line == "BEGIN:VEVENT":
            in_event = True
            current = {}
            continue
        if line == "END:VEVENT":
            if in_event:
                start = current.get("DTSTART")
                end = current.get("DTEND")
                if isinstance(start, datetime) and isinstance(end, datetime):
                    events.append(
                        IcsEvent(
                            start=start,
                            end=end,
                            summary=str(current.get("SUMMARY", "")),
                            description=str(current.get("DESCRIPTION", "")),
                            location=str(current.get("LOCATION", "")),
                        )
                    )
            in_event = False
            continue

        if not in_event:
            continue

        # Trong VEVENT
        if line.startswith("DTSTART"):
            # Ví dụ: DTSTART;TZID=Asia/Bangkok:20251117T070000
            try:
                _, value = line.split(":", 1)
                current["DTSTART"] = parse_ics_datetime(value)
            except ValueError:
                pass
        elif line.startswith("DTEND"):
            try:
                _, value = line.split(":", 1)
                current["DTEND"] = parse_ics_datetime(value)
            except ValueError:
                pass
        elif line.startswith("SUMMARY:"):
            current["SUMMARY"] = line[len("SUMMARY:"):]
        elif line.startswith("DESCRIPTION:"):
            current["DESCRIPTION"] = line[len("DESCRIPTION:"):]
        elif line.startswith("LOCATION:"):
            current["LOCATION"] = line[len("LOCATION:"):]

    events.sort(key=lambda e: e.start)
    return events


# ================== HTML TEMPLATE ==================

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <title>Lịch học từ ICS</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 16px;
        }
        h2 {
            margin-bottom: 6px;
        }
        .controls {
            margin-bottom: 10px;
        }
        button {
            margin-right: 6px;
            padding: 4px 10px;
        }
        #week-label {
            font-weight: bold;
            margin-left: 8px;
        }
        table {
            border-collapse: collapse;
            width: 100%;
        }
        th, td {
            border: 1px solid #ccc;
            vertical-align: top;
            padding: 4px;
        }
        th.day {
            text-align: center;
            background: #f0f0f0;
            font-weight: bold;
        }
        th.corner {
            background: #fafafa;
        }
        td.slot-label {
            width: 80px;
            font-weight: bold;
            background: #fafafa;
        }
        .event {
            margin-bottom: 4px;
            padding: 4px;
            border-radius: 4px;
            background: #e0f7fa;
            font-size: 12px;
        }
        .event.theory {
            background: #bbdefb;
        }
        .event.practice {
            background: #c8e6c9;
        }
        .meta {
            font-size: 12px;
            color: #666;
            margin-bottom: 10px;
        }
    </style>
</head>
<body>
    <h2>Lịch học từ ICS</h2>
    <div class="meta">Nguồn file: {{ICS_NAME}}</div>

    <div class="controls">
        <button id="prev-week">&laquo; Tuần trước</button>
        <button id="reset-week">Về tuần đầu</button>
        <button id="next-week">Tuần sau &raquo;</button>
        <span id="week-label"></span>
    </div>

    <table id="schedule-table"></table>

    <script>
    const DAY_NAMES = ["Thứ 2","Thứ 3","Thứ 4","Thứ 5","Thứ 6","Thứ 7","Chủ nhật"];
    const SLOTS = ["Sáng","Chiều","Tối"];

    // Dữ liệu sự kiện từ Python
    const rawEvents = {{EVENTS_JSON}};

    // Chuẩn hoá: chuyển string ISO -> Date
    const events = rawEvents.map(ev => ({
        ...ev,
        start: new Date(ev.start),
        end: new Date(ev.end),
    }));

    function getMonday(d) {
        const date = new Date(d.getFullYear(), d.getMonth(), d.getDate());
        const day = date.getDay(); // Sun=0, Mon=1, ...
        const diff = (day === 0 ? -6 : 1 - day); // đưa về Monday
        date.setDate(date.getDate() + diff);
        date.setHours(0,0,0,0);
        return date;
    }

    function formatDate(d) {
        const dd = String(d.getDate()).padStart(2, "0");
        const mm = String(d.getMonth() + 1).padStart(2, "0");
        const yyyy = d.getFullYear();
        return `${dd}/${mm}/${yyyy}`;
    }

    function detectSlot(ev) {
        // Ưu tiên đọc "Tiết: x -> y" trong description
        const m = ev.description.match(/Tiết:\s*([0-9]+)/);
        if (m) {
            const lesson = parseInt(m[1], 10);
            if (lesson >= 1 && lesson <= 5) return "Sáng";
            if (lesson >= 6 && lesson <= 10) return "Chiều";
            return "Tối";
        }
        // fallback theo giờ
        const h = ev.start.getHours();
        if (h < 12) return "Sáng";
        if (h < 18) return "Chiều";
        return "Tối";
    }

    function htmlEscape(text) {
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    // Nếu không có sự kiện -> hiển thị thông báo
    if (events.length === 0) {
        document.getElementById("schedule-table").innerHTML =
            "<tr><td>Không có sự kiện nào trong file ICS.</td></tr>";
    } else {
        const minDate = events.reduce((min, e) =>
            e.start < min ? e.start : min, events[0].start);
        const maxDate = events.reduce((max, e) =>
            e.start > max ? e.start : max, events[0].start);

        const baseMonday = getMonday(minDate);
        const lastMonday = getMonday(maxDate);
        const msPerWeek = 7 * 24 * 60 * 60 * 1000;
        const maxOffsetWeeks = Math.round((lastMonday - baseMonday) / msPerWeek);

        let currentOffset = 0;

        function buildWeekGrid(monday) {
            const grid = {};
            for (const slot of SLOTS) {
                for (let d = 0; d < 7; d++) {
                    grid[slot + "_" + d] = [];
                }
            }

            const weekEnd = new Date(monday.getTime() + msPerWeek);

            for (const ev of events) {
                const evDate = new Date(ev.start.getFullYear(), ev.start.getMonth(), ev.start.getDate());
                if (evDate >= monday && evDate < weekEnd) {
                    // dow: Mon=0 .. Sun=6
                    let dow = evDate.getDay(); // Sun=0
                    dow = (dow === 0) ? 6 : (dow - 1);

                    let slot = detectSlot(ev);
                    if (!SLOTS.includes(slot)) slot = "Sáng";

                    grid[slot + "_" + dow].push(ev);
                }
            }

            // sort trong từng ô theo giờ
            for (const key in grid) {
                grid[key].sort((a, b) => a.start - b.start);
            }

            return grid;
        }

        function renderWeek() {
            const monday = new Date(baseMonday.getTime() + currentOffset * msPerWeek);
            const weekDates = [];
            for (let i = 0; i < 7; i++) {
                const d = new Date(monday);
                d.setDate(monday.getDate() + i);
                weekDates.push(d);
            }

            const grid = buildWeekGrid(monday);

            // Tiêu đề tuần
            const weekLabel = `Tuần từ ${formatDate(weekDates[0])} đến ${formatDate(weekDates[6])}`;
            document.getElementById("week-label").textContent = weekLabel;

            // Header
            let headerRow = '<tr><th class="corner"></th>';
            for (let i = 0; i < 7; i++) {
                headerRow += `<th class="day">${DAY_NAMES[i]}<br>${formatDate(weekDates[i])}</th>`;
            }
            headerRow += '</tr>';

            // Body
            let bodyRows = "";
            for (const slot of SLOTS) {
                let row = `<tr><td class="slot-label">${slot}</td>`;
                for (let d = 0; d < 7; d++) {
                    const cellEvents = grid[slot + "_" + d];
                    if (!cellEvents || cellEvents.length === 0) {
                        row += "<td></td>";
                    } else {
                        let cellHtml = "";
                        for (const ev of cellEvents) {
                            let descHtml = htmlEscape(ev.description).replace(/\\n/g, "<br>");
                            let cssClass = "event";
                            if (ev.description.includes("Thực hành")) cssClass += " practice";
                            else if (ev.description.includes("Lý thuyết")) cssClass += " theory";

                            cellHtml += `
                                <div class="${cssClass}">
                                    <strong>${htmlEscape(ev.summary)}</strong><br>
                                    ${descHtml}
                                </div>
                            `;
                        }
                        row += `<td>${cellHtml}</td>`;
                    }
                }
                row += "</tr>";
                bodyRows += row;
            }

            document.getElementById("schedule-table").innerHTML =
                headerRow + bodyRows;

            // Disable nút khi hết tuần
            document.getElementById("prev-week").disabled = (currentOffset <= 0);
            document.getElementById("next-week").disabled = (currentOffset >= maxOffsetWeeks);
        }

        document.getElementById("prev-week").addEventListener("click", () => {
            if (currentOffset > 0) {
                currentOffset -= 1;
                renderWeek();
            }
        });

        document.getElementById("next-week").addEventListener("click", () => {
            if (currentOffset < maxOffsetWeeks) {
                currentOffset += 1;
                renderWeek();
            }
        });

        document.getElementById("reset-week").addEventListener("click", () => {
            currentOffset = 0;
            renderWeek();
        });

        renderWeek();
    }
    </script>
</body>
</html>
"""


# ================== MAIN BUILDER ==================

def build_html_from_ics(ics_path: str, output_dir: str = "viewer") -> str:
    events = parse_ics_file(ics_path)

    # đổi sang dict để nhét vào JSON
    events_data = []
    for ev in events:
        events_data.append({
            "start": ev.start.isoformat(),
            "end": ev.end.isoformat(),
            "summary": ev.summary,
            "description": ev.description,
            "location": ev.location,
        })

    events_json = json.dumps(events_data, ensure_ascii=False)

    ics_name = os.path.basename(ics_path)
    html = HTML_TEMPLATE.replace("{{EVENTS_JSON}}", events_json)
    html = html.replace("{{ICS_NAME}}", ics_name)

    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(ics_name)[0]
    out_path = os.path.join(output_dir, f"{base_name}_viewer.html")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    return out_path


def main():
    if len(sys.argv) < 2:
        print("Cách dùng:")
        print("    python ics_viewer_builder.py ics/220146027.ics")
        sys.exit(1)

    ics_path = sys.argv[1]
    if not os.path.exists(ics_path):
        print(f"Không tìm thấy file ICS: {ics_path}")
        sys.exit(1)

    out_file = build_html_from_ics(ics_path)
    print(f"Đã tạo file HTML: {out_file}")
    print("Mở file này bằng trình duyệt để xem lịch và bấm Tuần trước / Tuần sau.")


if __name__ == "__main__":
    main()
