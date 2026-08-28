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
st.sidebar.header("⏰ การตั้งค่าเวลา (Time Settings)")
start_date = st.sidebar.date_input("วันที่เริ่มต้นไฟล์แรก", pd.to_datetime("today"))
start_time = st.sidebar.time_input("เวลาเริ่มต้นไฟล์แรก", pd.to_datetime("08:00").time())
sample_rate_sec = st.sidebar.number_input("ความถี่ในการบันทึก (วินาที/จุด)", min_value=0.1, value=1.0, step=0.1)
current_start_datetime = datetime.combine(start_date, start_time)

st.sidebar.divider()
st.sidebar.header("⚙️ แสดงผล (Display Options)")

# ตัวเลือกการคำนวณเส้นเดี่ยวประจำโซน
line_calc_mode = st.sidebar.selectbox(
    "รูปแบบเส้นสัญญาณประจำโซน",
    ["Average (ค่าเฉลี่ย)", "Maximum (ค่าสูงสุด)", "Minimum (ค่าต่ำสุด)"],
    index=0
)

# ปุ่มแสดงจุด Max / Min บนเส้นกราฟ
show_max = st.sidebar.checkbox("🔴 แสดงค่าสูงสุด (Show Max)", value=False)
show_min = st.sidebar.checkbox("🔵 แสดงค่าต่ำสุด (Show Min)", value=False)

# ==========================================
# โครงสร้างถอดรหัสไบนารี Yokogawa (.DAD) 20 Channels
# ==========================================
HEADER_OFFSET = 512
SCALE_DIVIDER = 10.0
DTYPE_STR = ">i2"  # Big-Endian Signed Int16

ch_info = {
    1: "Z#1 Top",
    2: "Z#2 Top",
    3: "Z#3 Top",
    4: "Z#4 Top",
    5: "Z#5 Top",
    6: "Z#6 Top",
    7: "Z#7 Top",
    8: "Z#1 Bottom",
    9: "Z#2 Bottom",
    10: "Z#3 Bottom",
    11: "Z#4 Bottom",
    12: "Z#5 Bottom",
    13: "Z#6 Bottom",
    14: "Z#7 Bottom",
    15: "O2 Exit",
    16: "Dryer #1",
    17: "Dryer #2",
    18: "N2 Flow",
    19: "O2 Entrance",
    20: "Dew Point"
}

top_names = [ch_info[i] for i in range(1, 8)]
bot_names = [ch_info[i] for i in range(8, 15)]
col_names = [ch_info[i] for i in range(1, 21)]
num_channels = len(col_names)

# ==========================================
# อัปโหลดและประมวลผลไฟล์
# ==========================================
uploaded_files = st.file_uploader("เลือกไฟล์ .DAD / .DAT", type=["dad", "dat"], accept_multiple_files=True)

if uploaded_files:
    sorted_files = sorted(uploaded_files, key=lambda x: x.name)
    all_dfs = []

    for file in sorted_files:
        try:
            binary_data = file.read()
            
            # ถอดรหัสสัญญาณไบนารี Big-Endian Int16
            raw_signals = np.frombuffer(binary_data, dtype=np.dtype(DTYPE_STR), offset=HEADER_OFFSET).astype(float)
            
            # หาร 10.0 เพื่อปรับค่ากลับเป็นทศนิยมจริง
            scaled_signals = raw_signals / SCALE_DIVIDER

            points_per_channel = len(scaled_signals) // num_channels
            reshaped_data = scaled_signals[:points_per_channel * num_channels].reshape(points_per_channel, num_channels)

            # สร้างแกนเวลา
            time_freq = f"{int(sample_rate_sec * 1000)}ms"
            time_axis = pd.date_range(start=current_start_datetime, periods=points_per_channel, freq=time_freq)
            
            current_start_datetime = time_axis[-1] + pd.Timedelta(seconds=sample_rate_sec)

            df_single = pd.DataFrame(reshaped_data, columns=col_names)
            df_single.insert(0, "Datetime", time_axis)
            all_dfs.append(df_single)

        except Exception as e:
            st.error(f"เกิดข้อผิดพลาดในการอ่านไฟล์ {file.name}: {e}")

    if all_dfs:
        full_df = pd.concat(all_dfs, ignore_index=True)

        # ตัดเวลาที่ซ้ำกันออกและเรียงลำดับเวลา
        full_df = full_df.sort_values(by="Datetime")
        full_df = full_df.drop_duplicates(subset=["Datetime"], keep="first").reset_index(drop=True)

        num_files_str = f"({len(sorted_files)} Files)"

        # คำนวณรวบยอดให้เหลือเพียง 1 เส้นต่อ 1 กลุ่มกราฟ ตามตัวเลือกจาก Sidebar
        if "Average" in line_calc_mode:
            full_df["Top_Single"] = full_df[top_names].mean(axis=1)
            full_df["Bot_Single"] = full_df[bot_names].mean(axis=1)
            full_df["Dryer_Single"] = full_df[["Dryer #1", "Dryer #2"]].mean(axis=1)
            full_df["O2_Single"] = full_df[["O2 Exit", "O2 Entrance"]].mean(axis=1)
            mode_label = "Avg"
        elif "Maximum" in line_calc_mode:
            full_df["Top_Single"] = full_df[top_names].max(axis=1)
            full_df["Bot_Single"] = full_df[bot_names].max(axis=1)
            full_df["Dryer_Single"] = full_df[["Dryer #1", "Dryer #2"]].max(axis=1)
            full_df["O2_Single"] = full_df[["O2 Exit", "O2 Entrance"]].max(axis=1)
            mode_label = "Max"
        else:
            full_df["Top_Single"] = full_df[top_names].min(axis=1)
            full_df["Bot_Single"] = full_df[bot_names].min(axis=1)
            full_df["Dryer_Single"] = full_df[["Dryer #1", "Dryer #2"]].min(axis=1)
            full_df["O2_Single"] = full_df[["O2 Exit", "O2 Entrance"]].min(axis=1)
            mode_label = "Min"

        with st.expander("🔍 ดูตารางข้อมูลรวมทุกไฟล์ (Combined Dataset)"):
            st.dataframe(full_df.head(100), use_container_width=True)

        # ฟังก์ชันวาดกราฟแบบ 1 เส้นเดี่ยวต่อ 1 กราฟ
        def create_single_line_plot(y_col, y_title, y_range=None, unit="°C", color="#1f77b4"):
            fig = make_subplots(specs=[[{"secondary_y": False}]])
            
            fig.add_trace(go.Scatter(
                x=full_df["Datetime"], y=full_df[y_col], name=f"{y_title} ({mode_label})",
                line=dict(color=color, width=1.8),
                hovertemplate=f"<b>{y_title}</b>: %{{y:.1f}} {unit}<extra></extra>"
            ))

            # มาร์กเกอร์จุดสูงสุด (Max Point)
            if show_max:
                max_idx = full_df[y_col].idxmax()
                fig.add_trace(go.Scatter(
                    x=[full_df.loc[max_idx, "Datetime"]], y=[full_df.loc[max_idx, y_col]],
                    mode="markers+text", marker=dict(color="red", size=8, symbol="triangle-up"),
                    text=[f"Max: {full_df.loc[max_idx, y_col]:.1f}"], textposition="top center",
                    showlegend=False, hoverinfo="skip"
                ))

            # มาร์กเกอร์จุดต่ำสุด (Min Point)
            if show_min:
                min_idx = full_df[y_col].idxmin()
                fig.add_trace(go.Scatter(
                    x=[full_df.loc[min_idx, "Datetime"]], y=[full_df.loc[min_idx, y_col]],
                    mode="markers+text", marker=dict(color="blue", size=8, symbol="triangle-down"),
                    text=[f"Min: {full_df.loc[min_idx, y_col]:.1f}"], textposition="bottom center",
                    showlegend=False, hoverinfo="skip"
                ))

            fig.update_layout(
                height=350, template="plotly_white", hovermode="x unified",
                margin=dict(l=40, r=40, t=30, b=30),
                legend=dict(x=1.02, y=1, xanchor="left", yanchor="top")
            )
            fig.update_xaxes(title_text="Date & Time", tickformat="%H:%M\n%b %d, %Y")
            
            if y_range:
                fig.update_yaxes(title_text=f"{y_title} [{unit}]", range=y_range)
            else:
                fig.update_yaxes(title_text=f"{y_title} [{unit}]", autorange=True)

            return fig

        # ==========================================
        # 1. Top Zones Timeline (1 Line)
        # ==========================================
        st.subheader(f"📐 Top Zones Timeline ({mode_label}) {num_files_str}")
        fig_top = create_single_line_plot("Top_Single", "Top Zones", y_range=[400, 650], unit="°C", color="#4b7bec")
        st.plotly_chart(fig_top, use_container_width=True)

        # ==========================================
        # 2. Bottom Zones Timeline (1 Line)
        # ==========================================
        st.subheader(f"📐 Bottom Zones Timeline ({mode_label}) {num_files_str}")
        fig_bot = create_single_line_plot("Bot_Single", "Bottom Zones", y_range=[400, 650], unit="°C", color="#eb3b5a")
        st.plotly_chart(fig_bot, use_container_width=True)

        # ==========================================
        # 3. Dryer Temperatures Timeline (1 Line)
        # ==========================================
        st.subheader(f"🔥 Dryer Temperatures Timeline ({mode_label}) {num_files_str}")
        fig_dryer = create_single_line_plot("Dryer_Single", "Dryer Temp", y_range=[0, 400], unit="°C", color="#26de81")
        st.plotly_chart(fig_dryer, use_container_width=True)

        # ==========================================
        # 4. Oxygen Concentration Timeline (1 Line)
        # ==========================================
        st.subheader(f"🧪 Oxygen Concentration Timeline ({mode_label}) {num_files_str}")
        fig_o2 = create_single_line_plot("O2_Single", "O2 Level", y_range=[0, 200], unit="ppm", color="#fc5c65")
        st.plotly_chart(fig_o2, use_container_width=True)

        # ==========================================
        # 5. N2 Flow Timeline (1 Line)
        # ==========================================
        st.subheader(f"💨 N2 Flow Timeline {num_files_str}")
        fig_n2 = create_single_line_plot("N2 Flow", "N2 Flow", y_range=None, unit="L/min", color="#20bf6b")
        st.plotly_chart(fig_n2, use_container_width=True)

        # ==========================================
        # 6. Dew Point Timeline (1 Line)
        # ==========================================
        st.subheader(f"💧 Dew Point Timeline {num_files_str}")
        fig_dew = create_single_line_plot("Dew Point", "Dew Point", y_range=[-100, 10], unit="°Cdp", color="#8854d0")
        st.plotly_chart(fig_dew, use_container_width=True)
