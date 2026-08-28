import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime

# 1. ตั้งค่าหน้าจอแบบขยายกว้างเต็มตา
st.set_page_config(layout="wide", page_title="DAD Multi-Zone Visualizer")

st.title("📊 DAD Time-Series Visualizer (แยกกราฟรายโซน)")
st.write("อัปโหลดไฟล์ .DAD / .DAT แบบไบนารี (Binary) โปรแกรมจะข้ามการเช็ค UTF-8 และพล็อตกราฟให้ทันที")

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
enable_spikes = st.sidebar.checkbox("📍 แสดงเส้นเล็งเวลา (Spike Line)", value=True)

# ==========================================
# ส่วนอัปโหลดและประมวลผลไฟล์
# ==========================================
uploaded_files = st.file_uploader("เลือกไฟล์ .DAD / .DAT", type=["dad", "dat"], accept_multiple_files=True)

if uploaded_files:
    for file in uploaded_files:
        st.markdown(f"## 📂 ไฟล์: {file.name}")
        try:
            # 💡 อ่านข้อมูล Binary โดยตรงเพื่อหลีกเลี่ยง Error การถอดรหัสข้อความ
            binary_data = file.read()
            raw_signals = np.frombuffer(binary_data, dtype=np.int16, offset=512).astype(float)
            
            # ปรับสเกลข้อมูลอัตโนมัติ (หากเครื่องบันทึกเก็บค่าเป็นทศนิยมคูณ 10)
            if np.abs(raw_signals).max() > 2000:
                raw_signals = raw_signals / 10.0

            num_channels = 25
            points_per_channel = len(raw_signals) // num_channels
            reshaped_data = raw_signals[:points_per_channel * num_channels].reshape(points_per_channel, num_channels)

            # ตั้งชื่อคอลัมน์ 25 ช่อง
            col_names = []
            for i in range(1, 8): col_names.append(f"Top{i}")                  # 1-7
            for i in range(1, 8): col_names.append(f"Bottom{i}")               # 8-14
            for i in range(1, 3): col_names.append(f"Dryer Zone{i}")           # 15-16
            col_names.extend(["N2 Entrance", "N2 Exit"])                       # 17-18
            col_names.extend(["ppm O2 Entrance", "ppm O2 Exit"])               # 19-20
            for i in range(1, 5): col_names.append(f"Debinder Zone{i}")        # 21-24
            col_names.append("Dew Point")                                      # 25

            time_freq = f"{int(sample_rate_sec * 1000)}ms"
            time_axis = pd.date_range(start=start_datetime, periods=points_per_channel, freq=time_freq)

            df = pd.DataFrame(reshaped_data, columns=col_names[:num_channels])
            df.insert(0, "Datetime", time_axis)

            with st.expander("🔍 ดูตารางข้อมูลดิบ (Data Table)"):
                st.dataframe(df.head(100), use_container_width=True)

            # 💡 ฟังก์ชันสร้างกราฟแยกแต่ละโซน
            def draw_section_graph(section_title, keywords, unit="°C"):
                selected_cols = [c for c in df.columns if any(k.lower() in c.lower() for k in keywords)]
                if selected_cols:
                    fig = go.Figure()

                    for col in selected_cols:
                        # เพิ่มเส้นสัญญาณ
                        fig.add_trace(go.Scatter(
                            x=df["Datetime"],
                            y=df[col],
                            name=col,
                            mode='lines',
                            line=dict(width=2),
                            hovertemplate=f"<b>{col}</b>: %{{y:.1f}} {unit}<extra></extra>"
                        ))

                        # มาร์กเกอร์ ค่า Max
                        if show_max:
                            max_idx = df[col].idxmax()
                            max_val = df.loc[max_idx, col]
                            max_time = df.loc[max_idx, "Datetime"]
                            fig.add_trace(go.Scatter(
                                x=[max_time], y=[max_val],
                                mode='markers+text',
                                marker=dict(color='red', size=8, symbol='triangle-up'),
                                text=[f"Max: {max_val:.1f}"],
                                textposition="top center",
                                showlegend=False,
                                hoverinfo='skip'
                            ))

                        # มาร์กเกอร์ ค่า Min
                        if show_min:
                            min_idx = df[col].idxmin()
                            min_val = df.loc[min_idx, col]
                            min_time = df.loc[min_idx, "Datetime"]
                            fig.add_trace(go.Scatter(
                                x=[min_time], y=[min_val],
                                mode='markers+text',
                                marker=dict(color='blue', size=8, symbol='triangle-down'),
                                text=[f"Min: {min_val:.1f}"],
                                textposition="bottom center",
                                showlegend=False,
                                hoverinfo='skip'
                            ))

                    # ตกแต่งกราฟให้ดูง่ายและสะอาดตา
                    fig.update_layout(
                        height=400,
                        template="plotly_white",
                        hovermode="x unified",
                        margin=dict(l=50, r=30, t=40, b=40),
                        legend=dict(
                            orientation="h",
                            yanchor="bottom",
                            y=1.02,
                            xanchor="right",
                            x=1,
                            font=dict(size=12)
                        ),
                        xaxis=dict(
                            title="Date / Time",
                            showgrid=True,
                            gridcolor="rgba(220, 220, 220, 0.6)",
                            tickformat="%H:%M:%S\n%d/%m/%Y",
                            showspikes=enable_spikes,
                            spikecolor="gray",
                            spikemode="across",
                            spikedash="dash",
                            spikethickness=1
                        ),
                        yaxis=dict(
                            title=f"ค่าที่วัดได้ ({unit})",
                            autorange=True,
                            showgrid=True,
                            gridcolor="rgba(220, 220, 220, 0.6)",
                            zeroline=False
                        )
                    )

                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning(f"ไม่พบข้อมูลสำหรับ: {section_title}")

            # ==========================================
            # แสดงกราฟแยกทีละโซนชัดเจน
            # ==========================================
            st.divider()
            st.subheader("📐 1. Top 7 Zones")
            draw_section_graph("Top Zones", ["top"], unit="°C")

            st.divider()
            st.subheader("📐 2. Bottom 7 Zones")
            draw_section_graph("Bottom Zones", ["bottom"], unit="°C")

            st.divider()
            st.subheader("🔥 3. Dryer 2 Zones")
            draw_section_graph("Dryer Zones", ["dryer"], unit="°C")

            st.divider()
            st.subheader("💨 4. N2")
            draw_section_graph("N2 Zones", ["n2"], unit="L/min")

            st.divider()
            st.subheader("🧪 5. ppm O2 Entrance & Exit")
            draw_section_graph("ppm O2 Zones", ["o2"], unit="ppm")

            st.divider()
            st.subheader("⚙️ 6. Debinder 4 Zones")
            draw_section_graph("Debinder Zones", ["debinder"], unit="°C")

            st.divider()
            st.subheader("💧 7. Dew Point")
            draw_section_graph("Dew Point", ["dew"], unit="°C")

        except Exception as e:
            st.error(f"เกิดข้อผิดพลาดในการอ่านไฟล์ {file.name}: {e}")
