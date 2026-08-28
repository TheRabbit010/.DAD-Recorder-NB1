import re
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

# 1. ตั้งค่าหน้าจอแบบกว้าง
st.set_page_config(layout="wide", page_title="DAD Timeline Visualizer")

st.title("📊 DAD Time-Series Visualizer")

# ==========================================
# แถบตั้งค่าด้านข้าง (Sidebar)
# ==========================================
st.sidebar.header("⏰ ตั้งค่าเวลาสำรอง (กรณีชื่อไฟล์ไม่มีเวลา)")
start_date = st.sidebar.date_input("วันที่เริ่มต้น", pd.to_datetime("today"))
start_time = st.sidebar.time_input("เวลาเริ่มต้น", pd.to_datetime("08:00").time())
fallback_start_datetime = datetime.combine(start_date, start_time)

st.sidebar.divider()
st.sidebar.header("🔧 ปรับแต่งโครงสร้างไฟล์ (Binary Format)")
array_order = st.sidebar.selectbox(
    "การจัดเรียง Array สัญญาณ",
    ["Fortran Order (Channel-Sequential) - แนะนำ", "C-Order (Interleaved)"],
    index=0,
    help="หากกราฟเกิดลายฟันปลาขึ้นลงรุนแรง ให้เลือก Fortran Order"
)

st.sidebar.divider()
st.sidebar.header("⚙️ การแสดงผล (Display Options)")
show_max = st.sidebar.checkbox("🔴 แสดงค่าสูงสุด (Show Max)", value=False)
show_min = st.sidebar.checkbox("🔵 แสดงค่าต่ำสุด (Show Min)", value=False)

# ==========================================
# โครงสร้างถอดรหัส Yokogawa .DAD 20 Channels
# ==========================================
HEADER_OFFSET = 512
SCALE_DIVIDER = 10.0
DTYPE_STR = ">i2"  # Big-Endian Signed Int16

ch_info = {
    1: "Z#1 Top", 2: "Z#2 Top", 3: "Z#3 Top", 4: "Z#4 Top",
    5: "Z#5 Top", 6: "Z#6 Top", 7: "Z#7 Top",
    8: "Z#1 Bottom", 9: "Z#2 Bottom", 10: "Z#3 Bottom", 11: "Z#4 Bottom",
    12: "Z#5 Bottom", 13: "Z#6 Bottom", 14: "Z#7 Bottom",
    15: "O2 Exit", 16: "Dryer #1", 17: "Dryer #2", 18: "N2 Flow",
    19: "O2 Entrance", 20: "Dew Point"
}

top_names = [ch_info[i] for i in range(1, 8)]
bot_names = [ch_info[i] for i in range(8, 15)]
col_names = [ch_info[i] for i in range(1, 21)]
num_channels = len(col_names)

COLOR_PALETTE = [
    "#8e44ad", "#2980b9", "#27ae60", "#d35400", 
    "#f39c12", "#c0392b", "#16a085", "#8e44ad", 
    "#2980b9", "#27ae60", "#d35400", "#f39c12", 
    "#c0392b", "#16a085", "#e74c3c", "#2ecc71", 
    "#e67e22", "#1abc9c", "#3498db", "#9b59b6"
]

# ฟังก์ชันถอดรหัส Date & Time จากชื่อไฟล์จริง (เช่น ..._DATA260825_160000.DAD)
def extract_datetime_from_filename(filename, default_dt):
    # ค้นหาแพทเทิร์นตัวเลข 6 ตัว สองชุด เช่น 260825_160000
    match = re.search(r'(\d{2})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})', filename)
    if match:
        p1, p2, p3, hh, min_s, ss = map(int, match.groups())
        
        # ตรวจสอบรูปแบบ YYMMDD หรือ DDMMYY
        if p1 == 26 or p1 == 25: # กรณี YYMMDD (ปี 2026/2025)
            year, mm, dd = 2000 + p1, p2, p3
        elif p3 == 26 or p3 == 25: # กรณี DDMMYY
            dd, mm, year = p1, p2, 2000 + p3
        else:
            year, mm, dd = 2000 + p1, p2, p3

        try:
            return datetime(year, mm, dd, hh, min_s, ss), True
        except ValueError:
            return default_dt, False
    return default_dt, False

# ==========================================
# อัปโหลดไฟล์ .DAD
# ==========================================
uploaded_files = st.file_uploader("เลือกไฟล์ .DAD", type=["dad", "DAD"], accept_multiple_files=True)

if uploaded_files:
    sorted_files = sorted(uploaded_files, key=lambda x: x.name)
    file_info_list = []

    for file in sorted_files:
        try:
            binary_data = file.read()
            raw_signals = np.frombuffer(binary_data, dtype=np.dtype(DTYPE_STR), offset=HEADER_OFFSET).astype(float)
            scaled_signals = raw_signals / SCALE_DIVIDER

            points_per_channel = len(scaled_signals) // num_channels
            usable_points = points_per_channel * num_channels
            
            # 💡 แก้อาการฟันปลา: ใช้ order='F' (Fortran-order) เพื่อเรียงข้อมูลต่อกันทีละช่องสัญญาณ
            order_code = 'F' if "Fortran" in array_order else 'C'
            reshaped_data = scaled_signals[:usable_points].reshape((points_per_channel, num_channels), order=order_code)

            start_dt, has_auto_dt = extract_datetime_from_filename(file.name, fallback_start_datetime)

            file_info_list.append({
                "file_name": file.name,
                "data": reshaped_data,
                "total_rows": points_per_channel,
                "start_datetime": start_dt,
                "has_auto_dt": has_auto_dt
            })
        except Exception as e:
            st.error(f"เกิดข้อผิดพลาดในการอ่านไฟล์ {file.name}: {e}")

    if file_info_list:
        all_dfs = []
        current_time_cursor = fallback_start_datetime

        for i, info in enumerate(file_info_list):
            total_rows = info["total_rows"]
            
            # คำนวณแกนเวลาต่อเนื่องจากไฟล์จริง
            if i < len(file_info_list) - 1 and info["has_auto_dt"] and file_info_list[i+1]["has_auto_dt"]:
                delta_sec = (file_info_list[i+1]["start_datetime"] - info["start_datetime"]).total_seconds()
                auto_sample_rate = delta_sec / total_rows if total_rows > 0 else 1.0
                file_start_time = info["start_datetime"]
            else:
                auto_sample_rate = 1.0
                file_start_time = info["start_datetime"] if info["has_auto_dt"] else current_time_cursor

            time_freq = f"{max(1, int(auto_sample_rate * 1000))}ms"
            time_axis = pd.date_range(start=file_start_time, periods=total_rows, freq=time_freq)
            current_time_cursor = time_axis[-1] + pd.Timedelta(milliseconds=max(1, int(auto_sample_rate * 1000)))

            df_single = pd.DataFrame(info["data"], columns=col_names)
            df_single.insert(0, "Datetime", time_axis)
            all_dfs.append(df_single)

        full_df = pd.concat(all_dfs, ignore_index=True)
        full_df = full_df.sort_values(by="Datetime").reset_index(drop=True)
        full_df = full_df.drop_duplicates(subset=["Datetime"], keep="first").reset_index(drop=True)

        num_files_str = f"({len(sorted_files)} Files)"

        with st.expander("🔍 ดูตารางข้อมูลรวมทุกไฟล์ (Combined Dataset)"):
            st.dataframe(full_df.head(100), use_container_width=True)

        # สไตล์พื้นหลังสีขาว ฟอร์แมตเวลาเหมือนรูปตัวอย่าง image_7b303c.png
        def apply_white_theme_style(fig, y_title, y_range=None, is_secondary=False):
            fig.update_layout(
                height=400,
                template="plotly_white",
                paper_bgcolor="white",
                plot_bgcolor="white",
                hovermode="x unified",
                margin=dict(l=50, r=50, t=30, b=40),
                legend=dict(
                    x=1.01, y=1,
                    xanchor="left", yanchor="top",
                    font=dict(size=11)
                )
            )
            fig.update_xaxes(
                title_text="Date & Time",
                tickformat="%d/%m\n%H:%M", # แสดงผล วัน/เดือน เวลา เหมือนรูปตัวอย่าง
                showgrid=True,
                gridcolor="#E5E5E5",
                gridwidth=1
            )
            fig.update_yaxes(
                title_text=y_title,
                showgrid=True,
                gridcolor="#E5E5E5",
                gridwidth=1,
                range=y_range if y_range else None,
                autorange=True if not y_range else False,
                secondary_y=is_secondary
            )

        def add_max_min_markers(fig, df, cols, secondary_y_cols=[]):
            for col in cols:
                is_sec = col in secondary_y_cols
                if show_max:
                    max_idx = df[col].idxmax()
                    fig.add_trace(go.Scatter(
                        x=[df.loc[max_idx, "Datetime"]], y=[df.loc[max_idx, col]],
                        mode="markers+text", marker=dict(color="red", size=8, symbol="triangle-up"),
                        text=[f"Max: {df.loc[max_idx, col]:.1f}"], textposition="top center",
                        showlegend=False, hoverinfo="skip"
                    ), secondary_y=is_sec)
                if show_min:
                    min_idx = df[col].idxmin()
                    fig.add_trace(go.Scatter(
                        x=[df.loc[min_idx, "Datetime"]], y=[df.loc[min_idx, col]],
                        mode="markers+text", marker=dict(color="blue", size=8, symbol="triangle-down"),
                        text=[f"Min: {df.loc[min_idx, col]:.1f}"], textposition="bottom center",
                        showlegend=False, hoverinfo="skip"
                    ), secondary_y=is_sec)

        # ==========================================
        # 1. Top Zones Timeline (Scale: 400 - 650 °C)
        # ==========================================
        st.subheader(f"📐 Top Zones Timeline {num_files_str}")
        fig_top = make_subplots(specs=[[{"secondary_y": False}]])
        for idx, col in enumerate(top_names):
            fig_top.add_trace(go.Scatter(
                x=full_df["Datetime"], y=full_df[col], name=col,
                line=dict(width=1.8, color=COLOR_PALETTE[idx % len(COLOR_PALETTE)]),
                hovertemplate=f"{col}: %{{y:.1f}} °C<extra></extra>"
            ))
        add_max_min_markers(fig_top, full_df, top_names)
        apply_white_theme_style(fig_top, "Temperature [°C]", y_range=[400, 650])
        st.plotly_chart(fig_top, use_container_width=True)

        # ==========================================
        # 2. Bottom Zones Timeline (Scale: 400 - 650 °C)
        # ==========================================
        st.subheader(f"📐 Bottom Zones Timeline {num_files_str}")
        fig_bot = make_subplots(specs=[[{"secondary_y": False}]])
        for idx, col in enumerate(bot_names):
            fig_bot.add_trace(go.Scatter(
                x=full_df["Datetime"], y=full_df[col], name=col,
                line=dict(width=1.8, color=COLOR_PALETTE[idx % len(COLOR_PALETTE)]),
                hovertemplate=f"{col}: %{{y:.1f}} °C<extra></extra>"
            ))
        add_max_min_markers(fig_bot, full_df, bot_names)
        apply_white_theme_style(fig_bot, "Temperature [°C]", y_range=[400, 650])
        st.plotly_chart(fig_bot, use_container_width=True)

        # ==========================================
        # 3. Dryer Temperatures Timeline (Scale: 0 - 400 °C)
        # ==========================================
        st.subheader(f"🔥 Dryer Temperatures Timeline {num_files_str}")
        fig_dryer = make_subplots(specs=[[{"secondary_y": False}]])
        fig_dryer.add_trace(go.Scatter(
            x=full_df["Datetime"], y=full_df["Dryer #1"], name="Dryer #1",
            line=dict(color="#2ecc71", width=2.0),
            hovertemplate="Dryer #1: %{y:.1f} °C<extra></extra>"
        ))
        fig_dryer.add_trace(go.Scatter(
            x=full_df["Datetime"], y=full_df["Dryer #2"], name="Dryer #2",
            line=dict(color="#e67e22", width=2.0),
            hovertemplate="Dryer #2: %{y:.1f} °C<extra></extra>"
        ))
        add_max_min_markers(fig_dryer, full_df, ["Dryer #1", "Dryer #2"])
        apply_white_theme_style(fig_dryer, "Temperature [°C]", y_range=[0, 400])
        st.plotly_chart(fig_dryer, use_container_width=True)

        # ==========================================
        # 4. Oxygen Concentration & N2 Flow Timeline
        # ==========================================
        st.subheader(f"🧪 Oxygen Concentration & N2 Flow Timeline {num_files_str}")
        fig_o2_n2 = make_subplots(specs=[[{"secondary_y": True}]])
        fig_o2_n2.add_trace(go.Scatter(
            x=full_df["Datetime"], y=full_df["O2 Exit"], name="O2 Exit",
            line=dict(color="#e74c3c", width=2.0),
            hovertemplate="O2 Exit: %{y:.1f} ppm<extra></extra>"
        ), secondary_y=False)
        fig_o2_n2.add_trace(go.Scatter(
            x=full_df["Datetime"], y=full_df["O2 Entrance"], name="O2 Entrance",
            line=dict(color="#3498db", width=2.0),
            hovertemplate="O2 Entrance: %{y:.1f} ppm<extra></extra>"
        ), secondary_y=False)
        fig_o2_n2.add_trace(go.Scatter(
            x=full_df["Datetime"], y=full_df["N2 Flow"], name="N2 Flow",
            line=dict(color="#2ecc71", width=1.5, dash="dash"),
            hovertemplate="N2 Flow: %{y:.1f}<extra></extra>"
        ), secondary_y=True)
        add_max_min_markers(fig_o2_n2, full_df, ["O2 Exit", "O2 Entrance", "N2 Flow"], secondary_y_cols=["N2 Flow"])
        apply_white_theme_style(fig_o2_n2, "O2 Level [ppm]", y_range=[0, 200])
        fig_o2_n2.update_yaxes(title_text="N2 Flow", autorange=True, secondary_y=True, showgrid=False)
        st.plotly_chart(fig_o2_n2, use_container_width=True)

        # ==========================================
        # 5. Dew Point Timeline
        # ==========================================
        st.subheader(f"💧 Dew Point Timeline {num_files_str}")
        fig_dew = make_subplots(specs=[[{"secondary_y": False}]])
        fig_dew.add_trace(go.Scatter(
            x=full_df["Datetime"], y=full_df["Dew Point"], name="Dew Point",
            line=dict(color="#9b59b6", width=2.0),
            hovertemplate="Dew Point: %{y:.1f} °Cdp<extra></extra>"
        ))
        add_max_min_markers(fig_dew, full_df, ["Dew Point"])
        apply_white_theme_style(fig_dew, "Dew Point [°Cdp]", y_range=[-100, 10])
        st.plotly_chart(fig_dew, use_container_width=True)
