import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime

# 1. ตั้งค่าหน้าจอแบบขยายกว้างเต็มตา
st.set_page_config(layout="wide", page_title="DAD Data Analyzer")

st.title("📊 โปรแกรมวิเคราะห์ไฟล์ .DAD ไบนารีและพล็อตกราฟแยกโซน")
st.write("รองรับการแยกช่องสัญญาณ: Top(7), Bottom(7), Dryer(2), N2, O2(2), Debinder(4) และ Dew Point พร้อมแกนเวลาจริง")

# ==========================================
# เมนูด้านข้าง (Sidebar) สำหรับตั้งค่าเวลาให้แกน X
# ==========================================
st.sidebar.header("⏰ การตั้งค่าเวลา (Time Settings)")
st.sidebar.caption("ระบุเวลาเริ่มต้นที่เครื่องเริ่มบันทึกไฟล์นี้")
start_date = st.sidebar.date_input("วันที่เริ่มต้น (Start Date)", pd.to_datetime("today"))
start_time = st.sidebar.time_input("เวลาเริ่มต้น (Start Time)", pd.to_datetime("08:00").time())
sample_rate_sec = st.sidebar.number_input("ความถี่ในการบันทึก (วินาที/จุด)", min_value=0.1, value=1.0, step=0.1)

# ประกอบร่างวันที่และเวลา
start_datetime = datetime.combine(start_date, start_time)

# ==========================================
# ส่วนอัปโหลดและประมวลผลไฟล์
# ==========================================
uploaded_file = st.file_uploader("กรุณาเลือกไฟล์ .DAD ของคุณ", type=["dad", "dat"])

if uploaded_file is not None:
    try:
        # อ่าน Byte ข้อมูลดิบ
        binary_data = uploaded_file.read()
        
        # ถอดรหัสข้าม Header 512 bytes (ปรับเป็น dtype ตามจริงของเครื่อง ถ้ากราฟเพี้ยนให้ลองเปลี่ยนเป็น np.int32 หรือ np.float32)
        raw_signals = np.frombuffer(binary_data, dtype=np.int16, offset=512)
        total_points = len(raw_signals)
        
        # 💡 อัปเดตโครงสร้าง Channels: รวมทั้งหมด 25 ช่องสัญญาณ
        # (Top=7, Bot=7, Dryer=2, N2=2, O2=2, Debinder=4, Dew=1) -> รวม 25
        num_channels = 25  
        points_per_channel = total_points // num_channels
        
        # แปลง Array 1 มิติ เป็นตาราง 2 มิติ (จุดเวลา x ช่องสัญญาณ)
        reshaped_data = raw_signals[:points_per_channel * num_channels].reshape(points_per_channel, num_channels)
        
        # 💡 สถาปนาตั้งชื่อคอลัมน์ให้ตรงกับโจทย์
        col_names = []
        for i in range(1, 8): col_names.append(f"Top{i}")                  # 1-7 (Top 7 zones)
        for i in range(1, 8): col_names.append(f"Bottom{i}")               # 8-14 (Bottom 7 zones)
        for i in range(1, 3): col_names.append(f"Dryer Zone{i}")           # 15-16 (Dryer 2 zones)
        col_names.extend(["N2 Entrance", "N2 Exit"])                       # 17-18 (N2 - สมมติว่ามี 2 จุด)
        col_names.extend(["ppm O2 Entrance", "ppm O2 Exit"])               # 19-20 (ppm O2 entrance & exit)
        for i in range(1, 5): col_names.append(f"Debinder Zone{i}")        # 21-24 (Debinder 4 zones)
        col_names.append("Dew Point")                                      # 25 (Dew Point)
        
        # สร้างแกนเวลา (Time / DatetimeIndex) จากค่าที่ตั้งไว้ใน Sidebar
        time_freq = f"{int(sample_rate_sec * 1000)}ms" # แปลงเป็นมิลลิวินาที
        time_axis = pd.date_range(start=start_datetime, periods=points_per_channel, freq=time_freq)
        
        # ประกอบข้อมูลเข้าเป็น DataFrame
        df = pd.DataFrame(reshaped_data, columns=col_names[:num_channels])
        df.insert(0, "Datetime", time_axis)
        
        # แสดงตาราง
        st.subheader("📋 ตารางตัวเลขหลังถอดรหัส (พร้อมแกนเวลาจริง)")
        st.dataframe(df.head())
        
        # ฟังก์ชันวาดกราฟ
        def draw_section_graph(section_title, keywords):
            selected_cols = [c for c in df.columns if any(k.lower() in c.lower() for k in keywords)]
            if selected_cols:
                fig = px.line(df, x="Datetime", y=selected_cols, title=f"{section_title} Waveform Display", template="plotly_white")
                fig.update_yaxes(autorange=True)
                
                # ฟอร์แมตแกน X ให้แสดง วัน-เดือน-ปี และ เวลา อย่างชัดเจน
                fig.update_xaxes(
                    title_text="Date / Time",
                    tickformat="%Y-%m-%d %H:%M:%S",
                    tickangle=45
                )
                
                fig.update_layout(legend_title_text='Signals', margin=dict(l=20, r=20, t=40, b=20), hovermode="x unified")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning(f"ไม่พบข้อมูลสำหรับ: {section_title}")
        
        # ==========================================
        # พล็อตกราฟแยกโซนตามที่กำหนด
        # ==========================================
        st.divider()
        st.subheader("📐 1. Top 7 Zones")
        draw_section_graph("Top Zones", ["top"])
        
        st.divider()
        st.subheader("📐 2. Bottom 7 Zones")
        draw_section_graph("Bottom Zones", ["bottom"])
        
        st.divider()
        st.subheader("🔥 3. Dryer 2 Zones")
        draw_section_graph("Dryer", ["dryer"])
        
        st.divider()
        st.subheader("💨 4. N2")
        draw_section_graph("N2", ["n2"])
        
        st.divider()
        st.subheader("🧪 5. ppm O2 Entrance & Exit")
        draw_section_graph("ppm O2", ["o2"])
        
        st.divider()
        st.subheader("⚙️ 6. Debinder 4 Zones")
        draw_section_graph("Debinder", ["debinder"])

        st.divider()
        st.subheader("💧 7. Dew Point")
        draw_section_graph("Dew Point", ["dew point"])

    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดทางโครงสร้างไฟล์ไบนารี: {e}")
        st.info("💡 ข้อแนะนำเพิ่มเติม: หากกราฟเพี้ยน/เป็นเส้นหยักรุนแรง ให้ลองเช็คจำนวน Channels ว่าเครื่องเซ็ตไว้ 25 ช่องพอดีหรือไม่ หรือเปลี่ยนชนิดตัวแปรจาก `np.int16` เป็น `np.int32` ครับ")
