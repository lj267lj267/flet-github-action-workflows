import flet as ft
import requests
import base64
from datetime import datetime, time
import asyncio
from zai import ZhipuAiClient

API_BASE = "http://star.lj267.eu.org/api"
CHART_TEXT_GLOBAL = ""

# ========== 智谱 AI 配置 ==========
ZHIPU_API_KEY = "59235725a8cf427e81e3ee91507b19c8.KdkcpxU6eKRjjliQ"  # 请替换为您的真实 API Key
# =================================

def main(page: ft.Page):
    page.window_width = 720
    page.window_height = 1280
    page.window_center = True
    page.window_resizable = False
    page.theme = ft.Theme(font_family="微软雅黑")
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 12
    page.scroll = None
    page.bgcolor = ft.Colors.GREY_50
    #page.window_icon = "ico.ico"
    page.title = "星星点灯"
    page.locale_configuration = ft.LocaleConfiguration(
        supported_locales=[ft.Locale("zh", "CN")],
        current_locale=ft.Locale("zh", "CN")
    )

    selected_date = None
    selected_time = None
    current_chart_data = None
    chat_history = []
    global CHART_TEXT_GLOBAL

    # ==================== AI 对话流式调用 ====================
    async def send_chat_query(e):
        nonlocal chat_history
        if not current_chart_data:
            chat_tip.value = "请先生成星盘！"
            chat_tip.color = ft.Colors.RED
            page.update()
            return
        user_text = chat_input.value.strip()
        if not user_text:
            chat_tip.value = "请输入提问内容"
            chat_tip.color = ft.Colors.RED
            page.update()
            return

        chat_tip.value = "AI正在实时解读..."
        chat_tip.color = ft.Colors.BLUE_600
        user_msg = user_text
        chat_input.value = ""
        page.update()

        async def scroll_chat_to_bottom():
            await asyncio.sleep(0.1)
            await chat_msg_container.scroll_to(offset=-1, duration=0)
            page.update()

        # 用户消息气泡
        user_bubble = ft.Row(
            [ft.Container(
                ft.Text(f"你：{user_msg}", size=14, selectable=True),
                padding=10, border_radius=14, bgcolor=ft.Colors.BLUE_100, width=420
            )], alignment=ft.MainAxisAlignment.END
        )
        chat_msg_container.controls.append(user_bubble)
        page.update()
        await scroll_chat_to_bottom()

        # AI气泡容器（占位）
        ai_text_ref = ft.Ref[ft.Text]()
        ai_bubble = ft.Row(
            [ft.Container(
                ft.Text("AI占星师：", ref=ai_text_ref, size=14, selectable=True),
                padding=10, border_radius=14, bgcolor=ft.Colors.GREEN_100, width=420
            )], alignment=ft.MainAxisAlignment.START
        )
        chat_msg_container.controls.append(ai_bubble)
        page.update()
        await scroll_chat_to_bottom()

        # 构造提示词和消息
        system_prompt = (
            "你是专业西方占星解读师，严格基于下方用户本命星盘数据回答用户问题，禁止脱离星盘凭空乱说。"
            "回答要求：1. 语言通俗易懂，不要过度晦涩专业术语；"
            "2. 结合行星、星座、宫位、相位、四轴、元素特质综合分析；"
            "3. 分点清晰，逻辑通顺，情感温和客观；"
            "4. 如果用户提问超出星盘范围，礼貌告知仅能解读本命星盘相关问题；"
            "5. 不要输出无关内容，不编造不存在的星体配置。"
            "6. 如果以下提问内容与星座问题无关，请直接回答“对不起，这是与星座无关话题，恕不回复。”"
        )
        user_content = f"盘主星盘信息：\n{CHART_TEXT_GLOBAL}\n\n用户问题：{user_msg}"
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(chat_history)
        messages.append({"role": "user", "content": user_content})

        # ---- 使用 asyncio.Queue 传递流式数据 ----
        chunk_queue = asyncio.Queue()
        loop = asyncio.get_running_loop()  # 获取当前事件循环

        # 在线程中运行同步流式调用，传入 loop 参数
        def sync_stream(loop):
            try:
                client = ZhipuAiClient(api_key=ZHIPU_API_KEY)
                stream = client.chat.completions.create(
                    model="glm-4-flash",
                    messages=messages,
                    #thinking={"type": "enabled"},
                    stream=True,
                    max_tokens=4096,
                    temperature=0.96
                )
                for chunk in stream:
                    reasoning = chunk.choices[0].delta.reasoning_content or ""
                    content = chunk.choices[0].delta.content or ""
                    #combined = reasoning + content
                    combined = content
                    if combined:
                        asyncio.run_coroutine_threadsafe(
                            chunk_queue.put(combined),
                            loop
                        )
                # 结束标记
                asyncio.run_coroutine_threadsafe(
                    chunk_queue.put(None),
                    loop
                )
            except Exception as e:
                asyncio.run_coroutine_threadsafe(
                    chunk_queue.put(f"[[ERROR]]{str(e)}"),
                    loop
                )

        # 启动线程（正确方式）
        asyncio.create_task(asyncio.to_thread(sync_stream, loop))

        # 主循环：从队列中取块并更新 UI
        full_response = ""
        error_occurred = False
        while True:
            chunk = await chunk_queue.get()
            if chunk is None:
                break
            if chunk.startswith("[[ERROR]]"):
                error_occurred = True
                full_response = chunk.replace("[[ERROR]]", "❌ 错误：")
                ai_text_ref.current.value = f"AI占星师：\n{full_response}"
                page.update()
                await scroll_chat_to_bottom()
                break
            full_response += chunk
            ai_text_ref.current.value = f"AI占星师：\n{full_response}"
            page.update()
            await scroll_chat_to_bottom()

        # 处理结果
        if error_occurred:
            chat_tip.value = full_response
            chat_tip.color = ft.Colors.RED
        else:
            chat_history.append({"role": "user", "content": user_msg})
            chat_history.append({"role": "assistant", "content": full_response})
            chat_tip.value = "解读完成，继续提问"
            chat_tip.color = ft.Colors.GREEN_600
        page.update()

    # ==================== 以下为原有 UI 和功能函数 ====================
    def load_provinces():
        try:
            res = requests.get(f"{API_BASE}/location/provinces")
            json_data = res.json()
            provinces = json_data["data"]
            province_dd.options = [ft.dropdown.Option(p) for p in provinces]
            page.update()
        except Exception as e:
            status_text.value = f"加载省份失败：{e}"
            status_text.color = ft.Colors.RED
            page.update()

    def update_cities(e):
        prov = province_dd.value
        if not prov:
            city_dd.options = []
            district_dd.options = []
            page.update()
            return
        try:
            res = requests.get(f"{API_BASE}/location/cities", params={"province": prov})
            cities = res.json()["data"]
            city_dd.options = [ft.dropdown.Option(c) for c in cities]
            city_dd.value = cities[0] if cities else None
            update_districts(None)
            page.update()
        except Exception as ex:
            status_text.value = f"加载城市失败：{ex}"
            status_text.color = ft.Colors.RED
            page.update()

    def update_districts(e):
        prov = province_dd.value
        city = city_dd.value
        if not prov or not city:
            district_dd.options = []
            page.update()
            return
        try:
            res = requests.get(f"{API_BASE}/location/districts", params={"province": prov, "city": city})
            districts = res.json()["data"]
            district_dd.options = [ft.dropdown.Option(d) for d in districts]
            district_dd.value = districts[0] if districts else None
            page.update()
        except Exception as ex:
            status_text.value = f"加载区县失败：{ex}"
            status_text.color = ft.Colors.RED
            page.update()

    def show_date_picker(e):
        def on_date_change(e):
            nonlocal selected_date
            utc_date = date_picker.value
            if utc_date:
                local_offset = datetime.now().astimezone().utcoffset()
                if local_offset:
                    local_dt = utc_date + local_offset
                    selected_date = local_dt.date()
                else:
                    selected_date = utc_date
                date_display.value = selected_date.strftime("%Y-%m-%d")
            else:
                date_display.value = "未选择"
            page.update()
        date_picker = ft.DatePicker(on_change=on_date_change, locale=ft.Locale("zh", "CN"))
        page.overlay.append(date_picker)
        page.show_dialog(date_picker)

    def show_time_picker(e):
        def on_time_change(e):
            nonlocal selected_time
            selected_time = time_picker.value
            time_display.value = selected_time.strftime("%H:%M") if selected_time else "未选择"
            page.update()
        time_picker = ft.TimePicker(on_change=on_time_change, locale=ft.Locale("zh", "CN"))
        page.overlay.append(time_picker)
        page.show_dialog(time_picker)

    def generate_chart(e):
        nonlocal current_chart_data, chat_history
        global CHART_TEXT_GLOBAL
        status_text.value = ""
        result_container.controls.clear()
        chat_msg_container.controls.clear()
        chat_history = []
        page.update()
        if not selected_date or not selected_time:
            status_text.value = "请选择完整出生日期与时间"
            status_text.color = ft.Colors.RED
            page.update()
            return
        if not all([province_dd.value, city_dd.value, district_dd.value]):
            status_text.value = "请完整选择省、市、区县"
            status_text.color = ft.Colors.RED
            page.update()
            return
        req_json = {
            "name": "用户",
            "birth_date": selected_date.strftime("%Y-%m-%d"),
            "birth_time": selected_time.strftime("%H:%M"),
            "timezone_offset": "+08:00",
            "province": province_dd.value,
            "city": city_dd.value,
            "district": district_dd.value
        }
        try:
            resp = requests.post(f"{API_BASE}/calc_chart", json=req_json, timeout=30)
            resp_data = resp.json()
            if resp_data["code"] != 0:
                status_text.value = f"服务异常：{resp_data.get('msg','未知错误')}"
                status_text.color = ft.Colors.RED
                page.update()
                return
            chart_data = resp_data["data"]
            current_chart_data = chart_data
            CHART_TEXT_GLOBAL = format_chart_data(chart_data)
        except Exception as ex:
            status_text.value = f"请求后端失败：{ex}\n请启动server.py"
            status_text.color = ft.Colors.RED
            page.update()
            return
        status_text.value = "✅ 星盘生成成功，请查看星盘数据与AI解读"
        status_text.color = ft.Colors.GREEN
        tab_layout.selected_index = 1
        page.update()

        # 渲染星盘数据卡片
        card_shape = ft.RoundedRectangleBorder(radius=16)
        info_card = ft.Card(
            elevation=2,
            shape=card_shape,
            content=ft.Container(
                ft.Column([
                    ft.Text(f"👤 {chart_data['name']}", size=18, weight=ft.FontWeight.BOLD),
                    ft.Text(f"UTC 时间: {chart_data['utc_time']}", size=13),
                    ft.Text(f"📍 {chart_data['address']}", size=13),
                ]), padding=12
            )
        )
        result_container.controls.append(info_card)

        angles = chart_data.get("angles", {})
        if angles:
            angle_rows = []
            for key, label in [("asc", "上升点 ASC"), ("dsc", "下降点 DSC"), ("mc", "天顶 MC"), ("ic", "天底 IC")]:
                if key in angles:
                    a = angles[key]
                    angle_rows.append(ft.Text(f"{label}: {a['sign']}{a['symbol']} {a['dms']}"))
            angle_card = ft.Card(content=ft.Container(ft.Column([ft.Text("📍 四轴点", size=18, weight=ft.FontWeight.BOLD)] + angle_rows), padding=15))
            result_container.controls.append(angle_card)

        nodes = chart_data.get("nodes", {})
        if nodes:
            node_texts = []
            for k, lab in [("north", "北交点"), ("south", "南交点")]:
                if k in nodes:
                    n = nodes[k]
                    retro = " (逆行)" if n["retrograde"] else ""
                    node_texts.append(ft.Text(f"{lab}: {n['sign']}{n['symbol']} {n['dms']} 第{n['house']}宫{retro}"))
            node_card = ft.Card(content=ft.Container(ft.Column([ft.Text("🌙 南北交点", size=18, weight=ft.FontWeight.BOLD)] + node_texts), padding=15))
            result_container.controls.append(node_card)

        planets = chart_data.get("planets", [])
        if planets:
            rows = []
            for p in planets:
                retro = "⛔" if p["retrograde"] else ""
                rows.append(ft.DataRow(cells=[
                    ft.DataCell(ft.Text(p["name"])),
                    ft.DataCell(ft.Text(f"{p['sign']}{p['symbol']}")),
                    ft.DataCell(ft.Text(p["dms"])),
                    ft.DataCell(ft.Text(str(p["house"]))),
                    ft.DataCell(ft.Text(retro)),
                ]))
            table = ft.DataTable(
                columns=[ft.DataColumn(ft.Text("行星")), ft.DataColumn(ft.Text("星座")), ft.DataColumn(ft.Text("度数")), ft.DataColumn(ft.Text("宫位")), ft.DataColumn(ft.Text("逆行"))],
                rows=rows, heading_row_color=ft.Colors.GREY_300
            )
            planet_card = ft.Card(content=ft.Container(ft.Column([ft.Text("🪐 行星位置", size=18, weight=ft.FontWeight.BOLD), table]), padding=15))
            result_container.controls.append(planet_card)

        asteroids = chart_data.get("asteroids", [])
        if asteroids:
            ast_texts = []
            for a in asteroids:
                ast_texts.append(ft.Text(f"{a['name']}: {a['sign']}{a['symbol']} {a['dms']} 第{a['house']}宫"))
            ast_card = ft.Card(content=ft.Container(ft.Column([ft.Text("☄️ 小行星", size=18, weight=ft.FontWeight.BOLD)] + ast_texts), padding=15))
            result_container.controls.append(ast_card)

        aspects = chart_data.get("aspects", [])
        if aspects:
            aspect_rows = []
            for asp in aspects[:15]:
                b1 = asp.get("body1", "？")
                symbol = asp.get("symbol", "？")
                b2 = asp.get("body2", "？")
                orb = asp.get("orb", "？")
                aspect_rows.append(ft.DataRow(cells=[
                    ft.DataCell(ft.Text(b1)),
                    ft.DataCell(ft.Text(symbol, size=18, color=ft.Colors.BLUE_GREY_700)),
                    ft.DataCell(ft.Text(b2)),
                    ft.DataCell(ft.Text(orb)),
                ]))
            aspect_table = ft.DataTable(
                columns=[ft.DataColumn(ft.Text("星体1")), ft.DataColumn(ft.Text("相位")), ft.DataColumn(ft.Text("星体2")), ft.DataColumn(ft.Text("容许度"))],
                rows=aspect_rows, heading_row_color=ft.Colors.GREY_300, border_radius=8
            )
            aspect_card = ft.Card(content=ft.Container(ft.Column([ft.Text("🔮 主要相位", size=18, weight=ft.FontWeight.W_700), ft.Divider(height=10), aspect_table]), padding=15))
            result_container.controls.append(aspect_card)

        elements_raw = chart_data.get("elements", {})
        modalities_raw = chart_data.get("modalities", {})
        element_counts = {}
        for elem, data in elements_raw.items():
            if isinstance(data, dict):
                count = data.get('count', 0)
            else:
                count = data
            element_counts[elem] = element_counts.get(elem, 0) + count
        modality_counts = {}
        for mod, data in modalities_raw.items():
            if isinstance(data, dict):
                count = data.get('count', 0)
            else:
                count = data
            modality_counts[mod] = modality_counts.get(mod, 0) + count

        if element_counts or modality_counts:
            element_config = {
                "火": {"color": ft.Colors.RED_400, "icon": ft.Icons.WHATSHOT},
                "土": {"color": ft.Colors.BROWN_400, "icon": ft.Icons.LANDSCAPE},
                "风": {"color": ft.Colors.BLUE_400, "icon": ft.Icons.AIR},
                "水": {"color": ft.Colors.CYAN_400, "icon": ft.Icons.WATER},
            }
            modality_config = {
                "开创": {"color": ft.Colors.PURPLE_400, "icon": ft.Icons.STAR},
                "固定": {"color": ft.Colors.GREEN_400, "icon": ft.Icons.LOCK},
                "变动": {"color": ft.Colors.ORANGE_400, "icon": ft.Icons.SWAP_HORIZ},
            }
            total_elements = sum(element_counts.values()) if element_counts else 1
            total_modalities = sum(modality_counts.values()) if modality_counts else 1

            element_rows = []
            for elem, count in element_counts.items():
                pct = (count / total_elements) * 100
                config = element_config.get(elem, {})
                row = ft.Row([
                    ft.Icon(config.get("icon", ft.Icons.CIRCLE), color=config.get("color", ft.Colors.GREY)),
                    ft.Text(elem, width=40),
                    ft.Text(str(count), width=30, weight=ft.FontWeight.BOLD),
                    ft.ProgressBar(value=pct / 100, color=config.get("color", ft.Colors.BLUE), bgcolor=ft.Colors.GREY_200, width=150),
                    ft.Text(f"{pct:.0f}%", width=40),
                ], spacing=5, vertical_alignment=ft.CrossAxisAlignment.CENTER)
                element_rows.append(row)

            modality_rows = []
            for mod, count in modality_counts.items():
                pct = (count / total_modalities) * 100
                config = modality_config.get(mod, {})
                row = ft.Row([
                    ft.Icon(config.get("icon", ft.Icons.CIRCLE), color=config.get("color", ft.Colors.GREY)),
                    ft.Text(mod, width=40),
                    ft.Text(str(count), width=30, weight=ft.FontWeight.BOLD),
                    ft.ProgressBar(value=pct / 100, color=config.get("color", ft.Colors.BLUE), bgcolor=ft.Colors.GREY_200, width=150),
                    ft.Text(f"{pct:.0f}%", width=40),
                ], spacing=5, vertical_alignment=ft.CrossAxisAlignment.CENTER)
                modality_rows.append(row)

            dist_content = ft.Column([
                ft.Text("🔥 元素分布", size=16, weight=ft.FontWeight.BOLD),
                ft.Column(element_rows, spacing=8),
                ft.Divider(height=10),
                ft.Text("⚡ 特质分布", size=16, weight=ft.FontWeight.BOLD),
                ft.Column(modality_rows, spacing=8),
            ], spacing=10)
            dist_card = ft.Card(content=ft.Container(content=dist_content, padding=15))
            result_container.controls.append(dist_content)

        render_chart_result_tab()
        page.update()

    def render_input_tab():
        tab1_input.controls.clear()
        btn_style = ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10))
        date_btn = ft.Button("选择出生日期", icon=ft.Icons.CALENDAR_TODAY, on_click=show_date_picker, width=320, style=btn_style)
        time_btn = ft.Button("选择出生时间", icon=ft.Icons.ACCESS_TIME, on_click=show_time_picker, width=320, style=btn_style)
        gen_btn = ft.Button("✨ 生成本命星盘", bgcolor=ft.Colors.BLUE_500, color=ft.Colors.WHITE, on_click=generate_chart, width=320, height=48, style=btn_style)
        input_card = ft.Card(elevation=3, shape=ft.RoundedRectangleBorder(radius=16), content=ft.Container(ft.Column([
            ft.Text("📅 出生时间", size=16, weight=ft.FontWeight.BOLD),
            ft.Row([date_btn, date_display], wrap=True),
            ft.Row([time_btn, time_display], wrap=True),
            ft.Divider(),
            ft.Text("📍 出生地点", size=16, weight=ft.FontWeight.BOLD),
            province_dd, city_dd, district_dd,
            ft.Divider(height=20),
            gen_btn,
            status_text
        ], spacing=12), padding=15))
        tab1_input.controls.append(input_card)
        page.update()

    def render_chart_result_tab():
        tab2_chart.controls.clear()
        if not current_chart_data:
            empty_card = ft.Card(elevation=2, shape=ft.RoundedRectangleBorder(radius=16), content=ft.Container(ft.Text("暂无星盘数据，请切换到【出生信息】生成星盘", size=14, color=ft.Colors.GREY_600), padding=30, alignment=ft.Alignment.CENTER))
            tab2_chart.controls.append(empty_card)
        else:
            tab2_chart.controls.extend(result_container.controls)
        page.update()

    def render_chat_tab():
        tab3_chat.controls.clear()
        chat_input_row = ft.Row([chat_input, send_btn], spacing=8, vertical_alignment=ft.CrossAxisAlignment.END)
        chat_card = ft.Card(elevation=2, shape=ft.RoundedRectangleBorder(radius=16), expand=True, content=ft.Container(ft.Column([
            chat_tip,
            chat_msg_container,
            ft.Divider(height=8),
            chat_input_row
        ], expand=True, spacing=10), padding=12))
        tab3_chat.controls.append(chat_card)
        page.update()

    def format_chart_data(chart_data: dict) -> str:
        lines = []
        lines.append(f"姓名：{chart_data.get('name', '用户')}")
        lines.append(f"UTC时间：{chart_data.get('utc_time', '未知')}")
        lines.append(f"出生地点：{chart_data.get('address', '未知')}")

        angles = chart_data.get("angles", {})
        if angles:
            lines.append("\n【四轴点】")
            for key, label in [("asc", "上升点 ASC"), ("dsc", "下降点 DSC"), ("mc", "天顶 MC"), ("ic", "天底 IC")]:
                if key in angles:
                    a = angles[key]
                    lines.append(f"{label}: {a['sign']}{a['symbol']} {a['dms']}")

        nodes = chart_data.get("nodes", {})
        if nodes:
            lines.append("\n【南北交点】")
            for k, lab in [("north", "北交点"), ("south", "南交点")]:
                if k in nodes:
                    n = nodes[k]
                    retro = " (逆行)" if n["retrograde"] else ""
                    lines.append(f"{lab}: {n['sign']}{n['symbol']} {n['dms']} 第{n['house']}宫{retro}")

        planets = chart_data.get("planets", [])
        if planets:
            lines.append("\n【行星位置】")
            for p in planets:
                retro = " (逆行)" if p["retrograde"] else ""
                lines.append(f"{p['name']}: {p['sign']}{p['symbol']} {p['dms']} 第{p['house']}宫{retro}")

        asteroids = chart_data.get("asteroids", [])
        if asteroids:
            lines.append("\n【小行星】")
            for a in asteroids:
                lines.append(f"{a['name']}: {a['sign']}{a['symbol']} {a['dms']} 第{a['house']}宫")

        aspects = chart_data.get("aspects", [])
        if aspects:
            lines.append("\n【主要相位】")
            for asp in aspects:
                lines.append(f"{asp.get('body1','')} {asp.get('symbol','')} {asp.get('body2','')} (容许度 {asp.get('orb','')})")

        elements = chart_data.get("elements", {})
        if elements:
            lines.append("\n【元素分布】")
            for elem, count in elements.items():
                if isinstance(count, dict):
                    count = count.get('count', 0)
                lines.append(f"{elem}: {count}")

        modalities = chart_data.get("modalities", {})
        if modalities:
            lines.append("\n【特质分布】")
            for mod, count in modalities.items():
                if isinstance(count, dict):
                    count = count.get('count', 0)
                lines.append(f"{mod}: {count}")

        return "\n".join(lines)

    # ==================== UI 组件初始化 ====================
    tab1_input = ft.Column(expand=True, scroll=ft.ScrollMode.ALWAYS, spacing=10)
    tab2_chart = ft.Column(expand=True, scroll=ft.ScrollMode.ALWAYS, spacing=10)
    tab3_chat = ft.Column(expand=True, spacing=10)

    chat_msg_container = ft.Column(scroll=ft.ScrollMode.ALWAYS, expand=True, spacing=6)
    chat_tip = ft.Text("先生成星盘再提问", size=13, color=ft.Colors.GREY_600)
    chat_input = ft.TextField(hint_text="输入星盘问题，如：我的上升星座性格分析", multiline=True, min_lines=1, max_lines=3, expand=True, border_radius=12)
    send_btn = ft.IconButton(icon=ft.Icons.SEND_ROUNDED, bgcolor=ft.Colors.BLUE_500, icon_color=ft.Colors.WHITE, on_click=lambda e: asyncio.create_task(send_chat_query(e)))

    province_dd = ft.Dropdown(label="省份", width=320, border_radius=10, on_select=update_cities)
    city_dd = ft.Dropdown(label="城市", width=320, border_radius=10, options=[], on_select=update_districts)
    district_dd = ft.Dropdown(label="区县", width=320, border_radius=10, options=[])
    date_display = ft.Text("未选择", size=14)
    time_display = ft.Text("未选择", size=14)
    status_text = ft.Text("", size=13)
    result_container = ft.Column(spacing=10)

    app_bar = ft.AppBar(
        title=ft.Text("🌟 本命星盘AI解读", size=20, weight=ft.FontWeight.BOLD),
        center_title=True,
        bgcolor=ft.Colors.BLUE_500,
        color=ft.Colors.WHITE
    )

    tab_layout = ft.Tabs(
        length=3,
        expand=True,
        content=ft.Column(expand=True, controls=[
            ft.TabBar(tabs=[
                ft.Tab(label="出生信息", icon=ft.Icons.EDIT_CALENDAR),
                ft.Tab(label="星盘数据", icon=ft.Icons.PIE_CHART),
                ft.Tab(label="AI解读", icon=ft.Icons.CHAT_BUBBLE),
            ]),
            ft.TabBarView(expand=True, controls=[tab1_input, tab2_chart, tab3_chat])
        ])
    )

    page.add(app_bar, tab_layout)

    load_provinces()
    render_input_tab()
    render_chart_result_tab()
    render_chat_tab()

if __name__ == "__main__":
    ft.run(main)
