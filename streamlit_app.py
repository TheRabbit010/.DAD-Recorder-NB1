import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# ตั้งค่าหน้าจอแบบขยายกว้างเต็มตาพล็อตกราฟซ้อนแชนเนลแบบรูปตัวอย่าง
st.set_page_config(layout="wide")

st.title("📊 โปรแกรมวิเคราะห์ไฟล์ .DAD ไบนารีและพล็อตกราฟแยกโซน")
st.write("อัปเดตให้รองรับการโยนไฟล์ .DAD / .DAT ดิบ และประมวลผลแยกช่องสัญญาณอัตโนมัติ")

# 1. กล่องสำหรับเปิดรับไฟล์ไบนารี .DAD โดยตรง
uploaded_file = st.file_uploader("กรุณาเลือกไฟล์ .DAD ของคุณ", type=["dad", "dat"])

if uploaded_file is not None:
    try:
        # 2. ทำการอ่าน Byte ข้อมูลดิบจากไฟล์ในระบบหน่วยความจำ
        binary_data = uploaded_file.read()
        
        # ถอดรหัสโครงสร้างสัญญาณไบนารีแบบ Short Integer (Int16) ข้าม Header 512 bytes
        raw_signals = np.frombuffer(binary_data, dtype=np.int16, offset=512)
        total_points = len(raw_signals)
        
        # 💡 ปรับจูนโครงสร้างแชนเนล: สมมติว่าในระบบมีสัญญาณที่วิ่งพร้อมกันทั้งหมด 24 ช่อง (Channels) 
        # (คุณสามารถเปลี่ยนตัวเลข num_channels เป็นค่าจริงของเครื่องบันทึกคุณได้เลยครับ)
        num_channels = 24  
        points_per_channel = total_points // num_channels
        
        # จัดแปลงรูปร่าง Array ใหม่ให้เป็นตารางมิติ (Rows = จุดเวลา, Columns = แต่ละแชนเนล)
        reshaped_data = raw_signals[:points_per_channel * num_channels].reshape(points_per_channel, num_channels)
        
        # 3. สถาปนาตั้งชื่อคอลัมน์ให้กับแต่ละเส้นสัญญานเพื่อใช้จับกลุ่มในกราฟ
        # ลำดับชื่อจำลองเรียงตามโครงสร้างการจับบันทึกของเครื่องวัด
        col_names = []
        for i in range(1, 8): col_names.append(f"Top{i} (Z{i})")          # แชนเนล 1-7
        for i in range(1, 8): col_names.append(f"Bot{i} (Z{i+7})")        # แชนเนล 8-14
        col_names.extend(["Dryer zone1", "Dryer zone2", "Dryer zone3"])     # แชนเนล 15-17
        col_names.extend(["N2 Inlet", "N2 Outlet"])                        # แชนเนล 18-19
        col_names.extend(["ppm O2 Exit", "O2 Entrance", "O2 Zone2"])       # แชนเนล 20-22
        col_names.extend(["Debinder / Dew Point 1", "Dew Point 2"])       # แชนเนล 23-24
        
        # สร้างแกนเวลา (Time / Index)
        time_axis = np.arange(points_per_channel)
        
        # ประกอบข้อมูลเข้าเป็น DataFrame
        df = pd.DataFrame(reshaped_data, columns=col_names[:num_channels])
        df.insert(0, "Time", time_axis)
        
        # แสดงตารางให้ผู้ใช้งานตรวจสอบค่าตัวเลขหลังจากถอดไบนารี
        st.subheader("📋 ตารางตัวเลขจำลองหลังถอดรหัสไฟล์ดิบ .DAD")
        st.dataframe(df.head(5))
        
        # ฟังก์ชันหลักในการแยกกลุ่มวาดกราฟเด็ดขาด สเกลปรับตามตัวมันเอง (Auto-Scale)
        def draw_section_graph(section_title, keywords):
            # ค้นหาคอลัมน์ที่ตรงกับคีย์เวิร์ดกลุ่มนั้นๆ
            selected_cols = [c for c in df.columns if any(k.lower() in c.lower() for k in keywords)]
            if selected_cols:
                fig = px.line(df, x="Time", y=selected_cols, title=f"{section_title} Waveform Display", template="plotly_white")
                fig.update_yaxes(autorange=True) # ปลดล็อกให้สเกลแกน Y ขยายเองอัตโนมัติ ไม่ยึดดึงสเกลกับกลุ่มอื่น
                fig.update_layout(legend_title_text='Signals', margin=dict(l=20, r=20, t=40, b=20))
                st.plotly_chart(fig, use_container_width=True)
            
        # ==========================================
        # พล็อตกราฟแยกโซนตามคำสั่งเด็ดขาด 6 ชั้นเรียงลงมา
        # ==========================================
        st.divider()
        st.subheader("📐 1. Top Zones")
        draw_section_graph("Top Zones", ["top"])
        
        st.divider()
        st.subheader("📐 2. Bottom Zones")
        draw_section_graph("Bottom Zones", ["bot"])
        
        st.divider()
        st.subheader("🔥 3. Dryer")
        draw_section_graph("Dryer", ["dryer"])
        
        st.divider()
        st.subheader("💨 4. N2")
        draw_section_graph("N2", ["n2"])
        
        st.divider()
        st.subheader("🧪 5. ppm O2")
        draw_section_graph("ppm O2", ["o2"])
        
        st.divider()
        st.subheader("⚙️ 6. Debinder & Dew Point")
        draw_section_graph("Debinder / Dew Point", ["debinder", "dew"])

    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดทางโครงสร้างไฟล์ไบนารี: {e}")
        st.info("💡 ข้อแนะนำเพิ่มเติม: หากกราฟแสดงผลออกมาเป็นเส้นหยักสลับไปมาอย่างรุนแรง แสดงว่ามิติแชนเนลในคำสั่ง `num_channels` ยังไม่ตรงกับโครงสร้างจริงของไฟล์เครื่อง Yokogawa ตัวนั้นครับ")
