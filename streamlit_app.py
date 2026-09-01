import re
import io
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

# ==========================================
# 1. ตั้งค่าหน้าจอ
# ==========================================
st.set_page_config(layout="wide", page_title="DAD Timeline Visualizer")
st.title("📊 DAD Time-Series Visualizer")

# ==========================================
# 🔄 ฟังก์ชันเคลียร์ข้อมูลเก่าอัตโนมัติ
# ==========================================
def clear_old_data():
    """ล้างข้อมูลและ cache เก่าใน session_state ทั้งหมดเมื่อมีการเปลี่ยนไฟล์"""
    for key in list(st.session_state.keys()):
        if key != "dad_file_uploader":  # เว้น key ของ file uploader ไว้
            del st.session_state[key]

# ==========================================
# 2. แถบตั้งค่าด้านข้าง (Sidebar)
# ==========================================
st.sidebar.header("⚙️ การแสดงผล (Display Options)")
show_max = st.sidebar.checkbox("🔴 แสดงค่าสูงสุด (Show Max)", value=False)
show_min = st.sidebar.checkbox("🔵 แสดงค่าต่ำสุด (Show Min)", value=False)

st.sidebar.divider()
st.sidebar.header("⏱️ การตั้งค่าเวลา (Time Settings)")
sample_rate_sec = st.sidebar.number_input("ความถี่ในการบันทึก (วินาที/Record)", min_value=0.1, value=1.0, step=0.1, 
                                          help="ระบุความเร็วในการดึงข้อมูลของเครื่อง (เช่น 1 วินาที)")

st.sidebar.divider()
# ปุ่มสำหรับกดล้างข้อมูลเองด้วยตนเอง (Manual Reset)
if st.sidebar.button("🗑️ ล้างข้อมูลทั้งหมด (Clear Data)", use_container_width=True, type="secondary"):
    clear_old_data()
    st.rerun()

# ==========================================
# 3. โครงสร้าง Mapping สัญญาณ
# ==========================================
col_mapping = {
    1: 4,   2: 6,   3: 8,   4: 10,  5: 12,  6: 14,  7: 16,  # Top Zones
    8: 18,  9: 20,  10: 22, 11: 24, 12: 26, 13: 28, 14: 30, # Bottom Zones
    15: 32, # O2 Exit
    16: 36, 17: 38, # Dryers
    18: 84, # N2 Flow
    19: 88, # O2 Entrance
    20: 86, # Dew Point
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

COLOR_PALETTE = [
    "#8e44ad", "#2980b9", "#27ae60", "#d35400", 
    "#f39c12", "#c0392b", "#16a085", "#8e44ad", 
    "#2980b9", "#27ae60", "#d35400", "#f39c12", 
    "#c0392b", "#16a085", "#e74c3c", "#2ecc71"
]

def extract_start_time_from_filename(filename):
    matches = re.findall(r'\d{6}', filename)
    if len(matches) >= 2:
        d_str, t_str = matches[-2], matches[-1]
        p1, p2, p3 = int(d_str[:2]), int(d_str[2:4]), int(d_str[4:6])
        hh, mm, ss = int(t_str[:2]), int(t_str[2:4]), int(t_str[4:6])
            
        if 20 <= p1 <= 30:  
            year, month, day = 2000 + p1, p2, p3
        elif 20 <= p3 <= 30: 
            day, month, year = p1, p2, 2000 + p3
        else:
            year, month, day = 2000 + p1, p2, p3

        try:
            return datetime(year, month, day, hh, mm, ss), True
        except ValueError:
            pass
            
    return pd.to_datetime("today").replace(hour=8, minute=0, second=0, microsecond=0), False

# ==========================================
# 4. การจัดการและรวมไฟล์ (เปิดใช้งาน Auto-Clear)
# ==========================================
uploaded_files = st.file_uploader(
    "เลือกไฟล์ .DAD", 
    type=["dad", "DAD"], 
    accept_multiple_files=True,
    key="dad_file_uploader",
    on_change=clear_old_data  # 👈 เรียกใช้ฟังก์ชันล้างข้อมูลทันทีเมื่อเปลี่ยนไฟล์
)

if uploaded_files:
    # เรียงลำดับไฟล์ตาม Datetime จริง
    parsed_files = []
    for f in uploaded_files:
        dt, is_valid = extract_start_time_from_filename(f.name)
        parsed_files.append((f, dt if is_valid else datetime.max))
    
    parsed_files.sort(key=lambda x: x[1])
    sorted_files = [item[0] for item in parsed_files]

    all_dfs = []
    
    for i, file in enumerate(sorted_files):
        try:
            binary_data = file.read()
            raw_signals = np.frombuffer(binary_data, dtype=np.dtype(DTYPE_STR), offset=HEADER_OFFSET).astype(float)
            
            points_per_channel = len(raw_signals) // TOTAL_CHANNELS
            
            if points_per_channel == 0:
                st.warning(f"ไฟล์ {file.name} ข้อมูลไม่เพียงพอ")
                continue

            usable_points = points_per_channel * TOTAL_CHANNELS
            reshaped_data = raw_signals[:usable_points].reshape((points_per_channel, TOTAL_CHANNELS), order='F')
            reshaped_data = reshaped_data / SCALE_DIVIDER

            data_dict = {}
            for ch_num, col_idx in col_mapping.items():
                ch_name = ch_info[ch_num]
                val_array = reshaped_data[:, col_idx]
                
                # กรองค่าขยะ 0.0 ของกลุ่มอุณหภูมิออก
                if "Top" in ch_name or "Bottom" in ch_name or "Dryer" in ch_name:
                    val_array = np.where((val_array <= 0.0) | (val_array > 3500.0), np.nan, val_array)
                else:
                    val_array = np.where((val_array < -500.0) | (val_array > 3500.0), np.nan, val_array)
                    
                data_dict[ch_name] = val_array

            df_single = pd.DataFrame(data_dict)

            start_dt, _ = extract_start_time_from_filename(file.name)
            time_freq = f"{int(sample_rate_sec * 1000)}ms"
            time_axis = pd.date_range(start=start_dt, periods=points_per_channel, freq=time_freq)
            
            df_single.insert(0, "Datetime", time_axis)
            
            for col in df_single.columns[1:]:
                df_single[col] = df_single[col].interpolate(method='linear', limit_direction='both')
                
            all_dfs.append(df_single)
            
        except Exception as e:
            st.error(f"เกิดข้อผิดพลาดในการอ่านไฟล์ {file.name}: {e}")

    # ==========================================
    # 5. การแสดงผลกราฟ
    # ==========================================
    if all_dfs:
        full_df = pd.concat(all_dfs, ignore_index=True)
        full_df = full_df.sort_values(by="Datetime").reset_index(drop=True)
        full_df = full_df.drop_duplicates(subset=["Datetime"], keep="first").reset_index(drop=True)

        num_files_str = f"({len(sorted_files)} Files)"

        # 📥 Export Section
        st.sidebar.divider()
        st.sidebar.header("📥 ดาวน์โหลดข้อมูล")
        csv_data = full_df.to_csv(index=False).encode('utf-8-sig')
        st.sidebar.download_button(
            label="📥 ดาวน์โหลดข้อมูล (.csv)",
            data=csv_data,
            file_name=f"DAD_Export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )

        with st.expander("🔍 ดูตารางข้อมูลดิบ"):
            st.dataframe(full_df.head(100), use_container_width=True)

        def apply_white_theme_style(fig, y_title, y_range=None, is_secondary=False):
            fig.update_layout(
                height=380,
                template="plotly_white",
                margin=dict(l=40, r=40, t=30, b=30),
                hovermode="x unified",
                legend=dict(x=1.01, y=1, xanchor="left", yanchor="top", font=dict(size=11))
            )
            fig.update_xaxes(title_text="Date & Time", tickformat="%d/%m\n%H:%M:%S", showgrid=True, gridcolor="#E5E5E5")
            fig.update_yaxes(title_text=y_title, showgrid=True, gridcolor="#E5E5E5", range=y_range if y_range else None, autorange=True if not y_range else False, secondary_y=is_secondary)

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

        st.subheader(f"🔥 Dryer Temperatures Timeline {num_files_str}")
        fig_dryer = make_subplots(specs=[[{"secondary_y": False}]])
        fig_dryer.add_trace(go.Scatter(x=full_df["Datetime"], y=full_df["Dryer #1"], name="Dryer #1", line=dict(color="#2ecc71", width=2.0)))
        fig_dryer.add_trace(go.Scatter(x=full_df["Datetime"], y=full_df["Dryer #2"], name="Dryer #2", line=dict(color="#e67e22", width=2.0)))
        add_max_min_markers(fig_dryer, full_df, ["Dryer #1", "Dryer #2"])
        apply_white_theme_style(fig_dryer, "Temperature [°C]", y_range=None)
        st.plotly_chart(fig_dryer, use_container_width=True)

        st.subheader(f"🧪 Oxygen Concentration & N2 Flow Timeline {num_files_str}")
        fig_o2_n2 = make_subplots(specs=[[{"secondary_y": True}]])
        fig_o2_n2.add_trace(go.Scatter(x=full_df["Datetime"], y=full_df["O2 Exit"], name="O2 Exit", line=dict(color="#e74c3c", width=2.0)), secondary_y=False)
        fig_o2_n2.add_trace(go.Scatter(x=full_df["Datetime"], y=full_df["O2 Entrance"], name="O2 Entrance", line=dict(color="#3498db", width=2.0)), secondary_y=False)
        fig_o2_n2.add_trace(go.Scatter(x=full_df["Datetime"], y=full_df["N2 Flow"], name="N2 Flow", line=dict(color="#2ecc71", width=1.5, dash="dash")), secondary_y=True)
        add_max_min_markers(fig_o2_n2, full_df, ["O2 Exit", "O2 Entrance", "N2 Flow"], secondary_y_cols=["N2 Flow"])
        apply_white_theme_style(fig_o2_n2, "O2 Level [ppm]", y_range=None)
        fig_o2_n2.update_yaxes(title_text="N2 Flow", autorange=True, secondary_y=True, showgrid=False)
        st.plotly_chart(fig_o2_n2, use_container_width=True)

        st.subheader(f"💧 Dew Point Timeline {num_files_str}")
        fig_dew = make_subplots(specs=[[{"secondary_y": False}]])
        fig_dew.add_trace(go.Scatter(x=full_df["Datetime"], y=full_df["Dew Point"], name="Dew Point", line=dict(color="#9b59b6", width=2.0)))
        add_max_min_markers(fig_dew, full_df, ["Dew Point"])
        apply_white_theme_style(fig_dew, "Dew Point [°Cdp]", y_range=None)
        st.plotly_chart(fig_dew, use_container_width=True)
