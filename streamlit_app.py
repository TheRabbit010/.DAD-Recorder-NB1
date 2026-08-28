import re
import io
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

# 1. ตั้งค่าหน้าจอ
st.set_page_config(layout="wide", page_title="DAD Timeline Visualizer")

st.title("📊 DAD Time-Series Visualizer")

# ==========================================
# แถบตั้งค่าด้านข้าง (Sidebar)
# ==========================================
st.sidebar.header("⚙️ การแสดงผล (Display Options)")
show_max = st.sidebar.checkbox("🔴 แสดงค่าสูงสุด (Show Max)", value=False)
show_min = st.sidebar.checkbox("🔵 แสดงค่าต่ำสุด (Show Min)", value=False)

st.sidebar.divider()
st.sidebar.header("🔧 จูนโครงสร้างไบนารี (Advanced Parsing)")
st.sidebar.markdown("""
*หากค่าตัวเลขยังไม่ตรง ให้ลองเลื่อน `Offset (จุดเริ่มต้น)` เพื่อขยับตัวเลขให้ตรงล็อค*
""")
# ให้ผู้ใช้เลื่อนหา Offset จนกว่ากราฟจะโผล่ขึ้นมาตรงตามจริง
byte_offset = st.sidebar.slider("จุดเริ่มต้น Header (Byte Offset)", min_value=0, max_value=2048, value=512, step=2)
stride_length = st.sidebar.slider("ความกว้างบรรทัด (Stride Length)", min_value=10, max_value=250, value=88, step=1)

# ==========================================
# โครงสร้าง Mapping สัญญาณ
# ==========================================
# ตั้งค่าลำดับช่องสัญญาณ 20 ช่อง ตามหน้าจอแสดงผล
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
all_col_names = [ch_info[i] for i in range(1, 21)]

COLOR_PALETTE = [
    "#8e44ad", "#2980b9", "#27ae60", "#d35400", 
    "#f39c12", "#c0392b", "#16a085", "#8e44ad", 
    "#2980b9", "#27ae60", "#d35400", "#f39c12", 
    "#c0392b", "#16a085", "#e74c3c", "#2ecc71", 
    "#e67e22", "#1abc9c", "#3498db", "#9b59b6"
]

# ฟังก์ชันสกัดวันและเวลาจริงจากชื่อไฟล์ .DAD
def parse_datetime_from_filename(filename):
    match = re.search(r'(\d{6})_(\d{6})', filename)
    if not match:
        match = re.search(r'(\d{2})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})', filename)

    if match:
        if len(match.groups()) == 2:
            d_str, t_str = match.groups()
            p1, p2, p3 = int(d_str[:2]), int(d_str[2:4]), int(d_str[4:6])
            hh, mm, ss = int(t_str[:2]), int(t_str[2:4]), int(t_str[4:6])
        else:
            p1, p2, p3, hh, mm, ss = map(int, match.groups())
            
        # ตรวจสอบรูปแบบ YYMMDD หรือ DDMMYY
        if 20 <= p1 <= 30:  # YYMMDD (เช่น 260825 -> 2026-08-25)
            year, month, day = 2000 + p1, p2, p3
        elif 20 <= p3 <= 30: # DDMMYY (เช่น 250826 -> 25/08/2026)
            day, month, year = p1, p2, 2000 + p3
        else:
            year, month, day = 2000 + p1, p2, p3

        try:
            return datetime(year, month, day, hh, mm, ss), True
        except ValueError:
            pass
    
    # กรณีไม่พบเวลาในชื่อไฟล์ ให้ใช้วันนี้ 08:00
    fallback_dt = pd.to_datetime("today").replace(hour=8, minute=0, second=0, microsecond=0)
    return fallback_dt, False

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
            
            # แปลงไฟล์เป็น Int16
            raw_signals = np.frombuffer(binary_data, dtype=">i2", offset=int(byte_offset)).astype(float)
            scaled_signals = raw_signals / 10.0

            total_records = len(scaled_signals) // int(stride_length)
            
            if total_records == 0:
                st.warning(f"ไฟล์ {file.name} ข้อมูลสั้นเกินไป หรือตั้งค่า Offset เกินขนาดไฟล์")
                continue

            # สร้างตารางข้อมูลขนาด (N x Stride)
            reshaped_full = scaled_signals[:total_records * int(stride_length)].reshape(total_records, int(stride_length))

            # สร้าง DataFrame ชั่วคราว 20 คอลัมน์แรกเพื่อนำมาสแกนค่า
            # (ขยับช่วงคอลัมน์ให้อ่าน 20 ช่องสัญญาณ เริ่มจาก Col 0 เป็นต้นไป)
            usable_cols = min(20, int(stride_length))
            data_dict = {}
            for i in range(usable_cols):
                data_dict[all_col_names[i]] = reshaped_full[:, i]
            
            # เติม 0 ให้ครบ 20 ช่องหาก Stride ต่ำกว่า 20
            for i in range(usable_cols, 20):
                data_dict[all_col_names[i]] = np.zeros(total_records)

            auto_dt, has_auto_dt = parse_datetime_from_filename(file.name)

            file_info_list.append({
                "file_name": file.name,
                "df_data": pd.DataFrame(data_dict),
                "total_rows": total_records,
                "start_datetime": auto_dt,
                "has_auto_dt": has_auto_dt
            })
        except Exception as e:
            st.error(f"เกิดข้อผิดพลาดในการอ่านไฟล์ {file.name}: {e}")

    if file_info_list:
        all_dfs = []
        
        # จัดการร้อยเรียงเวลาของทุกไฟล์เข้าด้วยกัน (คำนวณวินาทีอัตโนมัติ)
        current_time_cursor = file_info_list[0]["start_datetime"]
        for i, info in enumerate(file_info_list):
            total_rows = info["total_rows"]
            
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

            df_single = info["df_data"].copy()
            df_single.insert(0, "Datetime", time_axis)
            all_dfs.append(df_single)

        full_df = pd.concat(all_dfs, ignore_index=True)
        full_df = full_df.sort_values(by="Datetime").reset_index(drop=True)
        full_df = full_df.drop_duplicates(subset=["Datetime"], keep="first").reset_index(drop=True)

        num_files_str = f"({len(sorted_files)} Files)"

        # ==========================================
        # 📥 ปุ่ม Export Excel / CSV ด้านข้าง
        # ==========================================
        st.sidebar.divider()
        st.sidebar.header("📥 ดาวน์โหลดข้อมูล (Export)")

        try:
            import openpyxl
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                full_df.to_excel(writer, sheet_name='All Data', index=False)
                full_df[['Datetime'] + top_names].to_excel(writer, sheet_name='Top Zones', index=False)
                full_df[['Datetime'] + bot_names].to_excel(writer, sheet_name='Bottom Zones', index=False)
                full_df[['Datetime', 'Dryer #1', 'Dryer #2']].to_excel(writer, sheet_name='Dryer', index=False)
                full_df[['Datetime', 'O2 Exit', 'O2 Entrance', 'N2 Flow']].to_excel(writer, sheet_name='O2 & N2 Flow', index=False)
                full_df[['Datetime', 'Dew Point']].to_excel(writer, sheet_name='Dew Point', index=False)

            st.sidebar.download_button(
                label="📥 ดาวน์โหลดไฟล์ Excel (.xlsx)",
                data=excel_buffer.getvalue(),
                file_name=f"DAD_Export_Data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        except Exception:
            csv_data = full_df.to_csv(index=False).encode('utf-8-sig')
            st.sidebar.download_button(
                label="📥 ดาวน์โหลดข้อมูล (.csv)",
                data=csv_data,
                file_name=f"DAD_Export_Data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )

        with st.expander("🔍 ดูตารางข้อมูล (ปรับ Slider ด้านซ้ายเพื่อเลื่อนตัวเลขเข้าช่องที่ถูกต้อง)"):
            st.dataframe(full_df.head(100), use_container_width=True)

        # ----------------------------------------
        # ฟังก์ชันวาดกราฟ
        # ----------------------------------------
        def apply_white_theme_style(fig, y_title, y_range=None, is_secondary=False):
            fig.update_layout(
                height=380,
                template="plotly_white",
                margin=dict(l=40, r=40, t=30, b=30),
                hovermode="x unified",
                legend=dict(x=1.01, y=1, xanchor="left", yanchor="top", font=dict(size=11))
            )
            fig.update_xaxes(
                title_text="Date & Time",
                tickformat="%d/%m\n%H:%M:%S",
                showgrid=True, gridcolor="#E5E5E5"
            )
            fig.update_yaxes(
                title_text=y_title,
                showgrid=True, gridcolor="#E5E5E5",
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

        # 1. Top Zones (Auto-range เผื่อค่าอุณหภูมิสวิง)
        st.subheader(f"📐 Top Zones Timeline {num_files_str}")
        fig_top = make_subplots(specs=[[{"secondary_y": False}]])
        for idx, col in enumerate(top_names):
            fig_top.add_trace(go.Scatter(
                x=full_df["Datetime"], y=full_df[col], name=col,
                line=dict(width=1.8, color=COLOR_PALETTE[idx % len(COLOR_PALETTE)]),
                hovertemplate=f"{col}: %{{y:.1f}} °C<extra></extra>"
            ))
        add_max_min_markers(fig_top, full_df, top_names)
        apply_white_theme_style(fig_top, "Temperature [°C]", y_range=None)
        st.plotly_chart(fig_top, use_container_width=True)

        # 2. Bottom Zones
        st.subheader(f"📐 Bottom Zones Timeline {num_files_str}")
        fig_bot = make_subplots(specs=[[{"secondary_y": False}]])
        for idx, col in enumerate(bot_names):
            fig_bot.add_trace(go.Scatter(
                x=full_df["Datetime"], y=full_df[col], name=col,
                line=dict(width=1.8, color=COLOR_PALETTE[idx % len(COLOR_PALETTE)]),
                hovertemplate=f"{col}: %{{y:.1f}} °C<extra></extra>"
            ))
        add_max_min_markers(fig_bot, full_df, bot_names)
        apply_white_theme_style(fig_bot, "Temperature [°C]", y_range=None)
        st.plotly_chart(fig_bot, use_container_width=True)

        # 3. Dryer Temperatures
        st.subheader(f"🔥 Dryer Temperatures Timeline {num_files_str}")
        fig_dryer = make_subplots(specs=[[{"secondary_y": False}]])
        fig_dryer.add_trace(go.Scatter(
            x=full_df["Datetime"], y=full_df["Dryer #1"], name="Dryer #1", line=dict(color="#2ecc71", width=2.0)
        ))
        fig_dryer.add_trace(go.Scatter(
            x=full_df["Datetime"], y=full_df["Dryer #2"], name="Dryer #2", line=dict(color="#e67e22", width=2.0)
        ))
        add_max_min_markers(fig_dryer, full_df, ["Dryer #1", "Dryer #2"])
        apply_white_theme_style(fig_dryer, "Temperature [°C]", y_range=None)
        st.plotly_chart(fig_dryer, use_container_width=True)

        # 4. Oxygen & N2
        st.subheader(f"🧪 Oxygen Concentration & N2 Flow Timeline {num_files_str}")
        fig_o2_n2 = make_subplots(specs=[[{"secondary_y": True}]])
        fig_o2_n2.add_trace(go.Scatter(
            x=full_df["Datetime"], y=full_df["O2 Exit"], name="O2 Exit", line=dict(color="#e74c3c", width=2.0)
        ), secondary_y=False)
        fig_o2_n2.add_trace(go.Scatter(
            x=full_df["Datetime"], y=full_df["O2 Entrance"], name="O2 Entrance", line=dict(color="#3498db", width=2.0)
        ), secondary_y=False)
        fig_o2_n2.add_trace(go.Scatter(
            x=full_df["Datetime"], y=full_df["N2 Flow"], name="N2 Flow", line=dict(color="#2ecc71", width=1.5, dash="dash")
        ), secondary_y=True)
        add_max_min_markers(fig_o2_n2, full_df, ["O2 Exit", "O2 Entrance", "N2 Flow"], secondary_y_cols=["N2 Flow"])
        apply_white_theme_style(fig_o2_n2, "O2 Level [ppm]", y_range=None)
        fig_o2_n2.update_yaxes(title_text="N2 Flow", autorange=True, secondary_y=True, showgrid=False)
        st.plotly_chart(fig_o2_n2, use_container_width=True)

        # 5. Dew Point
        st.subheader(f"💧 Dew Point Timeline {num_files_str}")
        fig_dew = make_subplots(specs=[[{"secondary_y": False}]])
        fig_dew.add_trace(go.Scatter(
            x=full_df["Datetime"], y=full_df["Dew Point"], name="Dew Point", line=dict(color="#9b59b6", width=2.0)
        ))
        add_max_min_markers(fig_dew, full_df, ["Dew Point"])
        apply_white_theme_style(fig_dew, "Dew Point [°Cdp]", y_range=None)
        st.plotly_chart(fig_dew, use_container_width=True)
