import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime

# 1. ตั้งค่าหน้าจอแบบขยายกว้างเต็มตา
st.set_page_config(layout="wide", page_title="DAD Binary Visualizer")

st.title("📈 DAD Time-Series Visualizer (Binary Processing)")
st.write("อัปโหลดไฟล์ .DAD / .DAT ดิบรวดเดียวหลายไฟล์ ระบบจะอ่านข้อมูลแบบ Binary และพล็อตกราฟแยก 7 หมวดให้อัตโนมัติ")

# ==========================================
# เมนูด้านข้าง (Sidebar) สำหรับตั้งค่าเวลา
# ==========================================
st.sidebar.header("⏰ การตั้งค่าเวลา (Time Settings)")
st.sidebar.caption("ระบุเวลาเริ่มต้นสำหรับไฟล์ที่อัปโหลด")
start_date = st.sidebar.date_input("วันที่เริ่มต้น (Start Date)", pd.to_datetime("today"))
start_time = st.sidebar.time_input("เวลาเริ่มต้น (Start Time)", pd.to_datetime("08:00").time())
sample_rate_sec = st.sidebar.number_input("ความถี่ในการบันทึก (วินาที/จุด)", min_value=0.1, value=1.0, step=0.1)

start_datetime = datetime.combine(start_date, start_time)

# ==========================================
# ส่วนอัปโหลดไฟล์ (รองรับหลายไฟล์)
# ==========================================
# ใช้ accept_multiple_files=True เพื่อให้โยนทีละหลายๆ ไฟล์ได้เหมือนในภาพ
uploaded_files = st.file_uploader("เลือกไฟล์ .DAD / .DAT", type=["dad", "dat"], accept_multiple_files=True)

if uploaded_files:
    # วนลูปประมวลผลทีละไฟล์ที่อัปโหลดเข้ามา
    for file in uploaded_files:
        st.markdown(f"<h2 style='color:#1E90FF;'>📂 ผลการวิเคราะห์ไฟล์: {file.name}</h2>", unsafe_allow_html=True)
        
        try:
            # 💡 สำคัญที่สุด: อ่านเป็น Byte ดิบ (ห้ามใช้ Text Decode เด็ดขาด)
            binary_data = file.read()
            
            # ถอดรหัส Binary ข้าม Header 512 bytes (ถ้าเครื่องรุ่นนี้ใช้ int32 ให้เปลี่ยน dtype เป็น np.int32)
            raw_signals = np.frombuffer(binary_data, dtype=np.int16, offset=512)
            total_points = len(raw_signals)
            
            # จำนวน Channels = 25
            num_channels = 25  
            points_per_channel = total_points // num_channels
            
            # แปลง Array ให้เป็นรูปตาราง
            reshaped_data = raw_signals[:points_per_channel * num_channels].reshape(points_per_channel, num_channels)
            
            # สร้างชื่อคอลัมน์ 25 ช่อง
            col_names = []
            for i in range(1, 8): col_names.append(f"Top{i}")                  # 1-7 (Top)
            for i in range(1, 8): col_names.append(f"Bottom{i}")               # 8-14 (Bottom)
            for i in range(1, 3): col_names.append(f"Dryer Zone{i}")           # 15-16 (Dryer)
            col_names.extend(["N2 Entrance", "N2 Exit"])                       # 17-18 (N2)
            col_names.extend(["ppm O2 Entrance", "ppm O2 Exit"])               # 19-20 (ppm O2)
            for i in range(1, 5): col_names.append(f"Debinder Zone{i}")        # 21-24 (Debinder)
            col_names.append("Dew Point")                                      # 25 (Dew Point)
            
            # สร้างแกนเวลา
            time_freq = f"{int(sample_rate_sec * 1000)}ms"
            time_axis = pd.date_range(start=start_datetime, periods=points_per_channel, freq=time_freq)
            
            # ประกอบข้อมูลเข้าเป็น DataFrame
            df = pd.DataFrame(reshaped_data, columns=col_names[:num_channels])
            df.insert(0, "Datetime", time_axis)
            
            st.success(f"✅ อ่านไฟล์ {file.name} สำเร็จ! พบข้อมูลทั้งหมด {points_per_channel} ชุดเวลา")
            
            # แสดงตัวอย่างตาราง (ซ่อนได้เพื่อให้หน้าเว็บไม่ยาวเกินไป)
            with st.expander("🔍 ดูตารางข้อมูลดิบ (Data Table)"):
                st.dataframe(df.head(100)) # แสดง 100 แถวแรก
            
            # ฟังก์ชันวาดกราฟสำหรับไฟล์ปัจจุบัน
            def draw_section_graph(section_title, keywords):
                selected_cols = [c for c in df.columns if any(k.lower() in c.lower() for k in keywords)]
                if selected_cols:
                    fig = px.line(df, x="Datetime", y=selected_cols, title=f"{section_title}", template="plotly_white")
                    fig.update_yaxes(autorange=True)
                    fig.update_xaxes(title_text="Date / Time", tickformat="%Y-%m-%d %H:%M:%S")
                    fig.update_layout(legend_title_text='Signals', margin=dict(l=20, r=20, t=40, b=20), hovermode="x unified")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning(f"ไม่พบข้อมูลสำหรับ: {section_title}")
            
            # ==========================================
            # แสดงกราฟทั้ง 7 โซน
            # ==========================================
            st.write("### 📐 1. Top 7 Zones")
            draw_section_graph("Top Zones Display", ["top"])
            
            st.write("### 📐 2. Bottom 7 Zones")
            draw_section_graph("Bottom Zones Display", ["bottom"])
            
            st.write("### 🔥 3. Dryer 2 Zones")
            draw_section_graph("Dryer Display", ["dryer"])
            
            st.write("### 💨 4. N2")
            draw_section_graph("N2 Flow Display", ["n2"])
            
            st.write("### 🧪 5. ppm O2 Entrance & Exit")
            draw_section_graph("O2 Concentration Display", ["o2"])
            
            st.write("### ⚙️ 6. Debinder 4 Zones")
            draw_section_graph("Debinder Display", ["debinder"])

            st.write("### 💧 7. Dew Point")
            draw_section_graph("Dew Point Display", ["dew point"])
            
            st.divider() # เส้นคั่นระหว่างไฟล์

        except Exception as e:
            st.error(f"❌ เกิดข้อผิดพลาดในการประมวลผลไฟล์ {file.name}: {e}")
            st.info("💡 ข้อแนะนำ: ตรวจสอบว่าไฟล์นี้ถูกบันทึกด้วยโครงสร้าง 25 ช่องสัญญาณหรือไม่ หรือลองเปลี่ยน `dtype=np.int16` เป็น `dtype=np.float32` หรือ `np.int32` ในบรรทัด np.frombuffer")
