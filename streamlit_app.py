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
st.sidebar.header("🔧 ปรับแต่งสเกลตัวเลข (Scale Calibration)")
scale_divider = st.sidebar.number_input("ตัวหารปรับสเกล (Divider)", value=10.0, step=1.0, help="หาร 10.0 เพื่อเปลี่ยนค่า Integer เป็น Decimal °C/ppm")
header_offset = st.sidebar.number_input("Header Offset (Bytes)", value=512, step=64)

st.sidebar.divider()
st.sidebar.header("⚙️ แสดงผล (Display Options)")
show_max = st.sidebar.checkbox("🔴 แสดงค่าสูงสุด (Show Max)", value=False)
show_min = st.sidebar.checkbox("🔵 แสดงค่าต่ำสุด (Show Min)", value=False)

# ==========================================
# อัปโหลดและประมวลผลไฟล์รวมเป็น Timeline เดียว
# ==========================================
uploaded_files = st.file_uploader("เลือกไฟล์ .DAD / .DAT", type=["dad", "dat"], accept_multiple_files=True)

if uploaded_files:
    # จัดเรียงไฟล์ตามชื่อไฟล์เพื่อให้เวลาเรียงกันถูกต้อง
    sorted_files = sorted(uploaded_files, key=lambda x: x.name)
    all_dfs = []
    
    # โครงสร้าง 19 แชนเนลหลักตามภาพตัวอย่าง
    top_names = [f"Top{i} (Z{i})" for i in range(1, 8)]
    bot_names = [f"Bot{i} (Z{i+7})" for i in range(1, 8)]
    col_names = top_names + bot_names + ["O2 Exit", "Dryer #1", "Dryer #2", "N2 Flow", "O2 Entrance"]
    num_channels = len(col_names)

    for file in sorted_files:
        try:
            binary_data = file.read()
            raw_signals = np.frombuffer(binary_data, dtype=np.int16, offset=int(header_offset)).astype(float)
            
            if scale_divider != 0:
                scaled_signals = raw_signals / scale_divider
            else:
                scaled_signals = raw_signals

            points_per_channel = len(scaled_signals) // num_channels
            reshaped_data = scaled_signals[:points_per_channel * num_channels].reshape(points_per_channel, num_channels)

            # คำนวณแกนเวลาให้เชื่อมต่อกันต่อเนื่องระหว่างไฟล์
            time_freq = f"{int(sample_rate_sec * 1000)}ms"
            time_axis = pd.date_range(start=current_start_datetime, periods=points_per_channel, freq=time_freq)
            
            # อัปเดตเวลาเริ่มต้นของไฟล์ถัดไป
            current_start_datetime = time_axis[-1] + pd.Timedelta(seconds=sample_rate_sec)

            df_single = pd.DataFrame(reshaped_data, columns=col_names)
            df_single.insert(0, "Datetime", time_axis)
            all_dfs.append(df_single)

        except Exception as e:
            st.error(f"เกิดข้อผิดพลาดในการอ่านไฟล์ {file.name}: {e}")

    if all_dfs:
        # รวมข้อมูลทุกไฟล์เข้าเป็น Timeline เดียวกัน
        full_df = pd.concat(all_dfs, ignore_index=True)
        num_files_str = f"({len(sorted_files)} Files)"

        with st.expander("🔍 ดูตารางข้อมูลรวมทุกไฟล์ (Combined Dataset)"):
            st.dataframe(full_df.head(100), use_container_width=True)

        # ==========================================
        # ฟังก์ชันผู้ช่วยสำหรับมาร์กเกอร์ Max / Min
        # ==========================================
        def add_max_min_markers(fig, df, cols, secondary_y_cols=[]):
            for col in cols:
                is_sec = col in secondary_y_cols
                if show_max:
                    max_idx = df[col].idxmax()
                    fig.add_trace(go.Scatter(
                        x=[df.loc[max_idx, "Datetime"]], y=[df.loc[max_idx, col]],
                        mode="markers+text", marker=dict(color="red", size=7, symbol="triangle-up"),
                        text=[f"Max: {df.loc[max_idx, col]:.1f}"], textposition="top center",
                        showlegend=False, hoverinfo="skip"
                    ), secondary_y=is_sec)
                if show_min:
                    min_idx = df[col].idxmin()
                    fig.add_trace(go.Scatter(
                        x=[df.loc[min_idx, "Datetime"]], y=[df.loc[min_idx, col]],
                        mode="markers+text", marker=dict(color="blue", size=7, symbol="triangle-down"),
                        text=[f"Min: {df.loc[min_idx, col]:.1f}"], textposition="bottom center",
                        showlegend=False, hoverinfo="skip"
                    ), secondary_y=is_sec)

        # ==========================================
        # 1. Oxygen Concentration & N2 Flow Timeline (Dual Y-Axis)
        # ==========================================
        st.subheader(f"🧪 Oxygen Concentration & N2 Flow Timeline {num_files_str}")
        fig_o2_n2 = make_subplots(specs=[[{"secondary_y": True}]])

        # O2 Exit & Entrance (แกนซ้าย - เส้นทึบ)
        fig_o2_n2.add_trace(go.Scatter(
            x=full_df["Datetime"], y=full_df["O2 Exit"], name="O2 Exit",
            line=dict(color="red", width=1.5),
            hovertemplate="O2 Exit: %{y:.1f} ppm<extra></extra>"
        ), secondary_y=False)

        fig_o2_n2.add_trace(go.Scatter(
            x=full_df["Datetime"], y=full_df["O2 Entrance"], name="O2 Entrance",
            line=dict(color="#1e90ff", width=1.5),
            hovertemplate="O2 Entrance: %{y:.1f} ppm<extra></extra>"
        ), secondary_y=False)

        # N2 Flow (แกนขวา - เส้นประ)
        fig_o2_n2.add_trace(go.Scatter(
            x=full_df["Datetime"], y=full_df["N2 Flow"], name="N2 Flow",
            line=dict(color="#2ed573", width=1.2, dash="dash"),
            hovertemplate="N2 Flow: %{y:.1f}<extra></extra>"
        ), secondary_y=True)

        add_max_min_markers(fig_o2_n2, full_df, ["O2 Exit", "O2 Entrance", "N2 Flow"], secondary_y_cols=["N2 Flow"])

        fig_o2_n2.update_layout(
            height=380, template="plotly_white", hovermode="x unified",
            margin=dict(l=40, r=40, t=30, b=30),
            legend=dict(x=1.05, y=1, xanchor="left", yanchor="top")
        )
        fig_o2_n2.update_xaxes(title_text="Date & Time", tickformat="%H:%M\n%b %d, %Y")
        fig_o2_n2.update_yaxes(title_text="O2 Level [ppm]", secondary_y=False)
        fig_o2_n2.update_yaxes(title_text="N2 Flow", secondary_y=True)
        st.plotly_chart(fig_o2_n2, use_container_width=True)

        # ==========================================
        # 2. Dryer Temperatures Timeline
        # ==========================================
        st.subheader(f"🔥 Dryer Temperatures Timeline {num_files_str}")
        fig_dryer = make_subplots(specs=[[{"secondary_y": False}]])

        fig_dryer.add_trace(go.Scatter(
            x=full_df["Datetime"], y=full_df["Dryer #1"], name="Dryer #1",
            line=dict(color="#00b894", width=1.5),
            hovertemplate="Dryer #1: %{y:.1f} °C<extra></extra>"
        ))
        fig_dryer.add_trace(go.Scatter(
            x=full_df["Datetime"], y=full_df["Dryer #2"], name="Dryer #2",
            line=dict(color="#ffa500", width=1.5),
            hovertemplate="Dryer #2: %{y:.1f} °C<extra></extra>"
        ))

        add_max_min_markers(fig_dryer, full_df, ["Dryer #1", "Dryer #2"])

        fig_dryer.update_layout(
            height=380, template="plotly_white", hovermode="x unified",
            margin=dict(l=40, r=40, t=30, b=30),
            legend=dict(x=1.05, y=1, xanchor="left", yanchor="top")
        )
        fig_dryer.update_xaxes(title_text="Date & Time", tickformat="%H:%M\n%b %d, %Y")
        fig_dryer.update_yaxes(title_text="Temperature [°C]")
        st.plotly_chart(fig_dryer, use_container_width=True)

        # ==========================================
        # 3. Top Zones Timeline
        # ==========================================
        st.subheader(f"📐 Top Zones Timeline {num_files_str}")
        fig_top = make_subplots(specs=[[{"secondary_y": False}]])
        for col in top_names:
            fig_top.add_trace(go.Scatter(
                x=full_df["Datetime"], y=full_df[col], name=col,
                hovertemplate=f"{col}: %{{y:.1f}} °C<extra></extra>"
            ))
        add_max_min_markers(fig_top, full_df, top_names)
        fig_top.update_layout(
            height=380, template="plotly_white", hovermode="x unified",
            margin=dict(l=40, r=40, t=30, b=30),
            legend=dict(x=1.05, y=1, xanchor="left", yanchor="top")
        )
        fig_top.update_xaxes(title_text="Date & Time", tickformat="%H:%M\n%b %d, %Y")
        fig_top.update_yaxes(title_text="Temperature [°C]")
        st.plotly_chart(fig_top, use_container_width=True)

        # ==========================================
        # 4. Bottom Zones Timeline
        # ==========================================
        st.subheader(f"📐 Bottom Zones Timeline {num_files_str}")
        fig_bot = make_subplots(specs=[[{"secondary_y": False}]])
        for col in bot_names:
            fig_bot.add_trace(go.Scatter(
                x=full_df["Datetime"], y=full_df[col], name=col,
                hovertemplate=f"{col}: %{{y:.1f}} °C<extra></extra>"
            ))
        add_max_min_markers(fig_bot, full_df, bot_names)
        fig_bot.update_layout(
            height=380, template="plotly_white", hovermode="x unified",
            margin=dict(l=40, r=40, t=30, b=30),
            legend=dict(x=1.05, y=1, xanchor="left", yanchor="top")
        )
        fig_bot.update_xaxes(title_text="Date & Time", tickformat="%H:%M\n%b %d, %Y")
        fig_bot.update_yaxes(title_text="Temperature [°C]")
        st.plotly_chart(fig_bot, use_container_width=True)
