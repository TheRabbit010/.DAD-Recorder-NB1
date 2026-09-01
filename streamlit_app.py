import re
import io
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

st.set_page_config(layout="wide", page_title="DAD Timeline Visualizer")
st.title("📊 DAD Time-Series Visualizer")

def clear_old_data():
    for key in list(st.session_state.keys()):
        if key != "dad_file_uploader":
            del st.session_state[key]

st.sidebar.header("⚙️ การแสดงผล (Display Options)")
show_max = st.sidebar.checkbox("🔴 แสดงค่าสูงสุด (Show Max)", value=False)
show_min = st.sidebar.checkbox("🔵 แสดงค่าต่ำสุด (Show Min)", value=False)
st.sidebar.divider()
st.sidebar.success("⏱️ **ระบบเวลา:** ดึงเวลาเริ่มต้นจากชื่อไฟล์ และเพิ่มขึ้น 10s อัตโนมัติ")
if st.sidebar.button("🗑️ ล้างข้อมูลทั้งหมด (Clear Data)", use_container_width=True, type="secondary"):
    clear_old_data()
    st.rerun()

# Mapping สัญญาณ
col_mapping = {
    1: 4, 2: 6, 3: 8, 4: 10, 5: 12, 6: 14, 7: 16,
    8: 18, 9: 20, 10: 22, 11: 24, 12: 26, 13: 28, 14: 30,
    15: 32, 16: 36, 17: 38, 18: 84, 19: 88, 20: 86
}
ch_info = {
    1: "Z#1 Top", 2: "Z#2 Top", 3: "Z#3 Top", 4: "Z#4 Top", 5: "Z#5 Top", 6: "Z#6 Top", 7: "Z#7 Top",
    8: "Z#1 Bottom", 9: "Z#2 Bottom", 10: "Z#3 Bottom", 11: "Z#4 Bottom", 12: "Z#5 Bottom", 13: "Z#6 Bottom", 14: "Z#7 Bottom",
    15: "O2 Exit", 16: "Dryer #1", 17: "Dryer #2", 18: "N2 Flow", 19: "O2 Entrance", 20: "Dew Point"
}

HEADER_OFFSET = 512
TOTAL_CHANNELS = 90  
SCALE_DIVIDER = 10.0
DTYPE_STR = ">i2"

top_names = [ch_info[i] for i in range(1, 8)]
bot_names = [ch_info[i] for i in range(8, 15)]
COLOR_PALETTE = ["#8e44ad", "#2980b9", "#27ae60", "#d35400", "#f39c12", "#c0392b", "#16a085"] * 3

def extract_start_time_from_filename(filename):
    matches = re.findall(r'\d{6}', filename)
    if len(matches) >= 2:
        d_str, t_str = matches[-2], matches[-1]
        p1, p2, p3 = int(d_str[:2]), int(d_str[2:4]), int(d_str[4:6])
        hh, mm, ss = int(t_str[:2]), int(t_str[2:4]), int(t_str[4:6])
        if 20 <= p1 <= 35: year, month, day = 2000 + p1, p2, p3
        elif 20 <= p3 <= 35: day, month, year = p1, p2, 2000 + p3
        else: year, month, day = 2000 + p1, p2, p3
        try: return datetime(year, month, day, hh, mm, ss), True
        except ValueError: pass
    return pd.to_datetime("today").replace(microsecond=0), False

uploaded_files = st.file_uploader("เลือกไฟล์ .DAD", type=["dad", "DAD"], accept_multiple_files=True, key="dad_file_uploader", on_change=clear_old_data)

if uploaded_files:
    parsed_files = [(f, *extract_start_time_from_filename(f.name)) for f in uploaded_files]
    parsed_files.sort(key=lambda x: x[1])
    all_dfs = []
    
    for file, start_dt, is_valid in parsed_files:
        try:
            binary_data = file.read()
            raw_signals = np.frombuffer(binary_data, dtype=np.dtype(DTYPE_STR), offset=HEADER_OFFSET).astype(float)
            points_per_channel = len(raw_signals) // TOTAL_CHANNELS
            
            if points_per_channel == 0: continue
            usable_points = points_per_channel * TOTAL_CHANNELS
            
            # 💡 แก้ไขสำคัญ: เปลี่ยน order='F' เป็น 'C' (จัดเรียงตามแนวนอนทีละเรคคอร์ด)
            reshaped_data = raw_signals[:usable_points].reshape((points_per_channel, TOTAL_CHANNELS), order='C')
            reshaped_data = reshaped_data / SCALE_DIVIDER

            data_dict = {}
            for ch_num, col_idx in col_mapping.items():
                ch_name = ch_info[ch_num]
                # เผื่อมีการสลับอินเด็กซ์, หากยังคงเพี้ยนอาจต้องเช็ค col_idx
                # โค้ดเดิมใช้ดัชนีคอลัมน์คู่ (เช่น 4,6,8,...) ซึ่งถูกต้องหากเป็นโครงสร้างเครื่องบางรุ่น
                if col_idx < TOTAL_CHANNELS:
                    val_array = reshaped_data[:, col_idx]
                    # กรองค่า 0.0 หรือค่าที่เหวี่ยงผิดปกติ
                    if "Top" in ch_name or "Bottom" in ch_name or "Dryer" in ch_name:
                        val_array = np.where((val_array <= 0.0) | (val_array > 1500.0), np.nan, val_array)
                    else:
                        val_array = np.where((val_array < -500.0) | (val_array > 3500.0), np.nan, val_array)
                    data_dict[ch_name] = val_array

            df_single = pd.DataFrame(data_dict)
            time_axis = pd.date_range(start=start_dt, periods=points_per_channel, freq="10s")
            df_single.insert(0, "Datetime", time_axis)
            for col in df_single.columns[1:]:
                df_single[col] = df_single[col].interpolate(method='linear', limit_direction='both')
            all_dfs.append(df_single)
        except Exception as e:
            st.error(f"Error reading {file.name}: {e}")

    if all_dfs:
        full_df = pd.concat(all_dfs, ignore_index=True).sort_values("Datetime").drop_duplicates("Datetime").reset_index(drop=True)

        with st.expander("🔍 ดูตารางข้อมูลดิบ (ตรวจสอบความเรียบร้อย)"):
            st.dataframe(full_df.head(100), use_container_width=True)

        def apply_white_theme_style(fig, y_title, y_range=None):
            fig.update_layout(height=400, template="plotly_white", margin=dict(l=40, r=40, t=30, b=30), hovermode="x unified", legend=dict(x=1.01, y=1, xanchor="left", yanchor="top", font=dict(size=11)))
            fig.update_xaxes(title_text="Date & Time", tickformat="%d/%m\n%H:%M:%S", showgrid=True, gridcolor="#E5E5E5")
            fig.update_yaxes(title_text=y_title, showgrid=True, gridcolor="#E5E5E5", range=y_range if y_range else None, autorange=True if not y_range else False)

        def add_max_min_markers(fig, df, cols):
            for col in cols:
                if col in df.columns:
                    if show_max and not df[col].isna().all():
                        max_idx = df[col].idxmax()
                        fig.add_trace(go.Scatter(x=[df.loc[max_idx, "Datetime"]], y=[df.loc[max_idx, col]], mode="markers+text", marker=dict(color="red", size=8, symbol="triangle-up"), text=[f"Max: {df.loc[max_idx, col]:.1f}"], textposition="top center", showlegend=False, hoverinfo="skip"))
                    if show_min and not df[col].isna().all():
                        min_idx = df[col].idxmin()
                        fig.add_trace(go.Scatter(x=[df.loc[min_idx, "Datetime"]], y=[df.loc[min_idx, col]], mode="markers+text", marker=dict(color="blue", size=8, symbol="triangle-down"), text=[f"Min: {df.loc[min_idx, col]:.1f}"], textposition="bottom center", showlegend=False, hoverinfo="skip"))

        st.subheader("📐 Top Zones Timeline")
        fig_top = make_subplots()
        for idx, col in enumerate(top_names):
            if col in full_df.columns:
                fig_top.add_trace(go.Scatter(x=full_df["Datetime"], y=full_df[col], name=col, line=dict(width=1.5, color=COLOR_PALETTE[idx]), hovertemplate=f"{col}: %{{y:.1f}} °C<extra></extra>"))
        add_max_min_markers(fig_top, full_df, top_names)
        # ไม่ล็อค y_range ปล่อยให้ปรับออโต้เพื่อดูว่าค่าเพี้ยนไหม
        apply_white_theme_style(fig_top, "Temperature [°C]", y_range=None) 
        st.plotly_chart(fig_top, use_container_width=True)

        # (เพิ่มส่วนพล็อต Bottom, Dryer ฯลฯ เหมือนเดิมตามต้องการ)
