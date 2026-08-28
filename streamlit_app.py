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
st.sidebar.header("⏰ ตั้งค่าเวลาสำรอง (Fallback Time)")
start_date = st.sidebar.date_input("วันที่เริ่มต้น", pd.to_datetime("today"))
start_time = st.sidebar.time_input("เวลาเริ่มต้น", pd.to_datetime("08:00").time())
fallback_start_datetime = datetime.combine(start_date, start_time)

st.sidebar.divider()
st.sidebar.header("🔧 การจัดตำแหน่งแชนเนล (Stride Calibration)")
use_auto_stride = st.sidebar.checkbox("⚡ คำนวณ Stride อัตโนมัติ (Auto-Detect)", value=True)
manual_stride = st.sidebar.number_input(
    "ระยะก้าวคอลัมน์ (Stride)", 
    min_value=50, max_value=150, value=88, step=1,
    help="หากค่าตัวเลขในตารางเฉียงทแยงมุม ให้ลองปรับลด/เพิ่มค่านี้ทีละ 1 หรือ 2"
)
header_offset = st.sidebar.number_input("Header Offset (Bytes)", min_value=0, max_value=2048, value=512, step=64)

st.sidebar.divider()
st.sidebar.header("⚙️ การแสดงผล (Display Options)")
show_max = st.sidebar.checkbox("🔴 แสดงค่าสูงสุด (Show Max)", value=False)
show_min = st.sidebar.checkbox("🔵 แสดงค่าต่ำสุด (Show Min)", value=False)

# ==========================================
# โครงสร้าง Mapping ตามไฟล์จริง (20 Channels)
# ==========================================
col_mapping = {
    1: 4,   # CH01 -> Z#1 Top
    2: 6,   # CH02 -> Z#2 Top
    3: 8,   # CH03 -> Z#3 Top
    4: 10,  # CH04 -> Z#4 Top
    5: 12,  # CH05 -> Z#5 Top
    6: 14,  # CH06 -> Z#6 Top
    7: 16,  # CH07 -> Z#7 Top
    8: 18,  # CH08 -> Z#1 Bottom
    9: 20,  # CH09 -> Z#2 Bottom
    10: 22, # CH10 -> Z#3 Bottom
    11: 24, # CH11 -> Z#4 Bottom
    12: 26, # CH12 -> Z#5 Bottom
    13: 28, # CH13 -> Z#6 Bottom
    14: 30, # CH14 -> Z#7 Bottom
    15: 32, # CH15 -> O2 Exit
    16: 36, # CH16 -> Dryer #1
    17: 38, # CH17 -> Dryer #2
    18: 84, # CH18 -> N2 Flow
    19: 88, # CH19 -> O2 Entrance
    20: 86, # CH20 -> Dew Point
}

ch_info = {
    1: "Z#1 Top", 2: "Z#2 Top", 3: "Z#3 Top", 4: "Z#4 Top",
    5: "Z#5 Top", 6: "Z#6 Top", 7: "Z#7 Top",
    8: "Z#1 Bottom", 9: "Z#2 Bottom", 10: "Z#3 Bottom", 11: "Z#4 Bottom",
    12: "Z#5 Bottom", 13: "Z#6 Bottom", 14: "Z#7 Bottom",
    15: "O2 Exit", 16: "Dryer #1", 17: "Dryer #2", 18: "N2 Flow",
    19: "O2 Entrance", 20: "Dew Point"
}

SCALE_DIVIDER = 10.0
DTYPE_STR = ">i2"  # Big-Endian Signed Int16

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

def extract_datetime_from_filename(filename, default_dt):
    match = re.search(r'(\d{2})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})', filename)
    if match:
        p1, p2, p3, hh, min_s, ss = map(int, match.groups())
        if p1 in [24, 25, 26]:
            year, mm, dd = 2000 + p1, p2, p3
        elif p3 in [24, 25, 26]:
            dd, mm, year = p1, p2, 2000 + p3
        else:
            year, mm, dd = 2000 + p1, p2, p3
        try:
            return datetime(year, mm, dd, hh, min_s, ss), True
        except ValueError:
            return default_dt, False
    return default_dt, False

# ฟังก์ชันค้นหาระยะก้าวที่จัดคอลัมน์ได้ตรงแนวตั้งที่สุด
def detect_best_stride(scaled_signals, target_cols, candidate_range=range(84, 95)):
    best_stride = 88
    min_diff_sum = float('inf')
    
    for s in candidate_range:
        total_rows = len(scaled_signals) // s
        if total_rows < 10:
            continue
        reshaped = scaled_signals[:total_rows * s].reshape(total_rows, s)
        valid_cols = [c for c in target_cols if c < s]
        if not valid_cols:
            continue
        
        # คำนวณความผันผวนของค่าระหว่างบรรทัดติดกัน
        diffs = np.mean(np.abs(np.diff(reshaped[:, valid_cols], axis=0)))
        if diffs < min_diff_sum:
            min_diff_sum = diffs
            best_stride = s
            
    return best_stride

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
            raw_signals = np.frombuffer(binary_data, dtype=np.dtype(DTYPE_STR), offset=int(header_offset)).astype(float)
            scaled_signals = raw_signals / SCALE_DIVIDER

            target_col_indices = list(col_mapping.values())
            
            # คำนวณหรือกำหนด Stride
            if use_auto_stride:
                stride = detect_best_stride(scaled_signals, target_col_indices)
            else:
                stride = int(manual_stride)

            total_records = len(scaled_signals) // stride
            reshaped_full = scaled_signals[:total_records * stride].reshape(total_records, stride)

            data_dict = {}
            for ch_num, col_idx in col_mapping.items():
                ch_name = ch_info[ch_num]
                if col_idx < stride:
                    data_dict[ch_name] = reshaped_full[:, col_idx]
                else:
                    data_dict[ch_name] = np.zeros(total_records)

            start_dt, has_auto_dt = extract_datetime_from_filename(file.name, fallback_start_datetime)

            file_info_list.append({
                "file_name": file.name,
                "df_data": pd.DataFrame(data_dict),
                "total_rows": total_records,
                "start_datetime": start_dt,
                "has_auto_dt": has_auto_dt,
                "stride_used": stride
            })
        except Exception as e:
            st.error(f"เกิดข้อผิดพลาดในการอ่านไฟล์ {file.name}: {e}")

    if file_info_list:
        all_dfs = []
        current_time_cursor = fallback_start_datetime

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
        stride_info_str = f" (Stride ปัจจุบัน: {file_info_list[0]['stride_used']} Columns)"

        # ==========================================
        # 📥 ดาวน์โหลดข้อมูล
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

        with st.expander(f"🔍 ดูตารางข้อมูลรวมทุกไฟล์ {stride_info_str}"):
            st.dataframe(full_df.head(100), use_container_width=True)

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
                tickformat="%d/%m\n%H:%M",
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
