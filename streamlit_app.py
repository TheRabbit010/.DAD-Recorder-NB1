import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

# 1. ตั้งค่าหน้าจอแบบขยายกว้างเต็มตา
st.set_page_config(layout="wide", page_title="DAD Multi-Zone Visualizer")

st.title("📊 DAD Time-Series Visualizer")

# ==========================================
# เมนูด้านข้าง (Sidebar) สำหรับตั้งค่า
# ==========================================
st.sidebar.header("⏰ การตั้งค่าเวลา (Time Settings)")
start_date = st.sidebar.date_input("วันที่เริ่มต้น", pd.to_datetime("today"))
start_time = st.sidebar.time_input("เวลาเริ่มต้น", pd.to_datetime("08:00").time())
sample_rate_sec = st.sidebar.number_input("ความถี่ในการบันทึก (วินาที/จุด)", min_value=0.1, value=1.0, step=0.1)
start_datetime = datetime.combine(start_date, start_time)

st.sidebar.divider()
st.sidebar.header("⚙️ การแสดงผล (Display Options)")
show_max = st.sidebar.checkbox("🔴 แสดงค่าสูงสุด (Show Max)", value=False)
show_min = st.sidebar.checkbox("🔵 แสดงค่าต่ำสุด (Show Min)", value=False)

# ==========================================
# อัปโหลดไฟล์และประมวลผล
# ==========================================
uploaded_files = st.file_uploader("เลือกไฟล์ .DAD / .DAT", type=["dad", "dat"], accept_multiple_files=True)

if uploaded_files:
    for file in uploaded_files:
        try:
            binary_data = file.read()
            raw_signals = np.frombuffer(binary_data, dtype=np.int16, offset=512).astype(float)
            
            # ปรับสเกลข้อมูล (หาร 10.0 หากไฟล์ดิบเก็บเป็นทศนิยม 1 ตำแหน่งแบบ Integer)
            if np.abs(raw_signals).max() > 2000:
                raw_signals = raw_signals / 10.0

            num_channels = 24
            points_per_channel = len(raw_signals) // num_channels
            reshaped_data = raw_signals[:points_per_channel * num_channels].reshape(points_per_channel, num_channels)

            # ตั้งชื่อคอลัมน์และโซนตามรูปตัวอย่าง
            col_names = []
            for i in range(1, 8): col_names.append(f"Top{i} (Z{i})")          # 1-7
            for i in range(1, 8): col_names.append(f"Bot{i} (Z{i+7})")        # 8-14
            col_names.extend(["Dryer zone1", "Dryer zone2", "Dryer zone3"])     # 15-17
            col_names.extend(["N2 Inlet", "N2 Outlet"])                        # 18-19
            col_names.extend(["O2 Exit", "O2 Entrance", "O2 Zone2"])           # 20-22
            col_names.extend(["Dew Point 1", "Dew Point 2"])                   # 23-24

            time_freq = f"{int(sample_rate_sec * 1000)}ms"
            time_axis = pd.date_range(start=start_datetime, periods=points_per_channel, freq=time_freq)

            df = pd.DataFrame(reshaped_data, columns=col_names[:num_channels])
            df.insert(0, "Datetime", time_axis)

            # แยกกลุ่มสัญญาณตามภาพตัวอย่าง
            top_cols = [c for c in df.columns if c.startswith("Top")]
            bot_cols = [c for c in df.columns if c.startswith("Bot")]
            o2_dryer_cols = [c for c in df.columns if any(k in c for k in ["Dryer", "O2", "N2", "Dew"])]

            # สร้าง Subplots ซ้อนกัน 3 ชั้นตามสไตล์รูปภาพ
            fig = make_subplots(
                rows=3, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.06,
                subplot_titles=('🌡️ Top Zones', '🌡️ Bottom Zones', '🔥 O2 & Dryer / Process Zones')
            )

            # 1. เพิ่มข้อมูล Top Zones
            for col in top_cols:
                fig.add_trace(go.Scatter(
                    x=df["Datetime"], y=df[col], name=col,
                    legendgroup="Top Zones", legendgrouptitle_text="Top Zones",
                    hovertemplate=f"<b>{col}</b>: %{{y:.1f}} °C<extra></extra>"
                ), row=1, col=1)

            # 2. เพิ่มข้อมูล Bottom Zones
            for col in bot_cols:
                fig.add_trace(go.Scatter(
                    x=df["Datetime"], y=df[col], name=col,
                    legendgroup="Bottom Zones", legendgrouptitle_text="Bottom Zones",
                    hovertemplate=f"<b>{col}</b>: %{{y:.1f}} °C<extra></extra>"
                ), row=2, col=1)

            # 3. เพิ่มข้อมูล O2 & Dryer / อื่นๆ
            for col in o2_dryer_cols:
                fig.add_trace(go.Scatter(
                    x=df["Datetime"], y=df[col], name=col,
                    legendgroup="O2 & Dryer", legendgrouptitle_text="O2 & Dryer",
                    hovertemplate=f"<b>{col}</b>: %{{y:.1f}}<extra></extra>"
                ), row=3, col=1)

            # เพิ่มมาร์กเกอร์ Max / Min ในกรณีที่มีการติ๊กเลือก
            if show_max or show_min:
                all_signal_cols = top_cols + bot_cols + o2_dryer_cols
                for col in all_signal_cols:
                    r = 1 if col in top_cols else (2 if col in bot_cols else 3)
                    if show_max:
                        max_idx = df[col].idxmax()
                        fig.add_trace(go.Scatter(
                            x=[df.loc[max_idx, "Datetime"]], y=[df.loc[max_idx, col]],
                            mode="markers+text", marker=dict(color="red", size=8, symbol="triangle-up"),
                            text=[f"Max: {df.loc[max_idx, col]:.1f}"], textposition="top center",
                            showlegend=False, hoverinfo="skip"
                        ), row=r, col=1)
                    if show_min:
                        min_idx = df[col].idxmin()
                        fig.add_trace(go.Scatter(
                            x=[df.loc[min_idx, "Datetime"]], y=[df.loc[min_idx, col]],
                            mode="markers+text", marker=dict(color="blue", size=8, symbol="triangle-down"),
                            text=[f"Min: {df.loc[min_idx, col]:.1f}"], textposition="bottom center",
                            showlegend=False, hoverinfo="skip"
                        ), row=r, col=1)

            # ตกแต่ง Layout ให้เหมือนตัวอย่าง
            fig.update_layout(
                height=900,
                template="plotly_white",
                hovermode="x unified",
                legend=dict(
                    groupclick="toggleitem",
                    orientation="v",
                    x=1.01, y=1,
                    xanchor="left", yanchor="top"
                ),
                margin=dict(l=50, r=160, t=50, b=40)
            )

            # ตั้งค่าเส้นประแนวดิ่ง (Spike Line) และการแสดงผลแกน X
            fig.update_xaxes(
                showspikes=True,
                spikecolor="black",
                spikesnap="cursor",
                spikemode="across",
                spikedash="dash",
                spikethickness=1,
                tickformat="%H:%M, %d/%m"
            )

            st.plotly_chart(fig, use_container_width=True)

        except Exception as e:
            st.error(f"เกิดข้อผิดพลาดในการอ่านไฟล์ {file.name}: {e}")
