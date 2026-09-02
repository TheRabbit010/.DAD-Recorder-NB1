import subprocess
import sys

# ตรวจสอบและติดตั้ง library อัตโนมัติหากยังไม่มีในระบบ
def install_package(package_name):
    try:
        __import__(package_name)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])

install_package("pandas")
install_package("plotly")
install_package("openpyxl")
install_package("numpy")

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import re
import numpy as np

st.set_page_config(layout="wide")
st.title("📊 DxViewerE (.DAD) - Dryer Zone Analysis")
st.subheader("เปรียบเทียบ Top & Bottom แยกตามกล่อง Dryer Zone #1 และ Zone #2")

uploaded_file = st.file_uploader("อัปโหลดไฟล์ .DAD จากเครื่องบันทึก DxViewerE", type=["dad", "dat"])

if uploaded_file is not None:
    # 1. โหลดและถอดรหัสข้อมูลดิบจากไฟล์
    file_bytes = uploaded_file.read()
    decoded_text = file_bytes.decode('latin-1', errors='ignore')
    
    # แพทเทิร์นค้นหาวันที่-เวลาจากสัญญาณ DxViewerE
    datetime_pattern = r'(\d{4}[-/]\d{2}[-/]\d{2}\s+\d{2}:\d{2}:\d{2})'
    lines = decoded_text.splitlines()
    records = []
    
    for line in lines:
        match = re.search(datetime_pattern, line)
        if match:
            dt_str = match.group(1)
            remaining_part = line[line.find(dt_str) + len(dt_str):]
            # ดึงตัวเลขทศนิยมทั้งหมดในบรรทัดข้อมูลนั้น
            numbers = re.findall(r'[-+]?\d*\.\d+|\d+', remaining_part)
            
            # รองรับดึงค่าอย่างน้อย 4 คอลัมน์ (Z1 Top, Z1 Bottom, Z2 Top, Z2 Bottom)
            if len(numbers) >= 4:
                float_nums = [float(n) for n in numbers[:4]]
                records.append([dt_str] + float_nums)

    # จัดการแปลงเป็น DataFrame ตารางข้อมูล
    if len(records) > 0:
        df = pd.DataFrame(records, columns=['DateTime', 'Z1_Top', 'Z1_Bottom', 'Z2_Top', 'Z2_Bottom'])
        df['DateTime'] = pd.to_datetime(df['DateTime'], errors='coerce')
        df = df.dropna(subset=['DateTime'])
    else:
        # โหมดจำลองข้อมูลอัตโนมัติหากระบบอ่านโครงสร้างข้อความพิเศษไม่สำเร็จ
        st.warning("⚠️ กำลังใช้โครงสร้างสแกนจำลองแบบแถวเนื่องจากไฟล์ Binary มีการบีบอัดสูง")
        try:
            all_floats = np.frombuffer(file_bytes, dtype=np.float32).tolist()
            chunks = [all_floats[i:i+5] for i in range(0, len(all_floats), 5) if len(all_floats[i:i+5]) == 5]
            df = pd.DataFrame(chunks, columns=['Index', 'Z1_Top', 'Z1_Bottom', 'Z2_Top', 'Z2_Bottom'])
            df['DateTime'] = pd.date_range(start='2026-01-01', periods=len(df), freq='1s')
        except Exception:
            df = pd.DataFrame()

    # 2. เริ่มสร้างกราฟแยกกลุ่มตามโซน (Subplots 2 ชั้นแนวตั้ง)
    if not df.empty:
        st.success(f"🔓 แยกโครงสร้างกลุ่มข้อมูลสำเร็จ ({len(df)} แถว)")
        
        # แสดงตัวเลือกเปิด/ปิดการพล็อตข้อมูลเฉพาะบางตัวแปรได้จากหน้าเว็บ
        st.sidebar.header("⚙️ ตั้งค่าการแสดงผล")
        show_temp = st.sidebar.checkbox("Temperature (°C)", value=True)
        show_o2 = st.sidebar.checkbox("ppm O2", value=True)
        show_n2 = st.sidebar.checkbox("N2 Flow (h3/h)", value=True)

        # สร้าง Subplots 2 แถว 1 คอลัมน์ (แชร์แกนเวลาร่วมกัน)
        fig = make_subplots(
            rows=2, 
            cols=1, 
            shared_xaxes=True, 
            vertical_spacing=0.1,
            subplot_titles=(
                "🔥 Dryer Zone #1 (Top & Bottom Comparison)", 
                "🔥 Dryer Zone #2 (Top & Bottom Comparison)"
            )
        )

        # --- แถวที่ 1: พล็อตข้อมูล Dryer Zone #1 ---
        # เส้น Z1 Top
        fig.add_trace(go.Scatter(
            x=df['DateTime'], y=df['Z1_Top'],
            name="Z1 Top", mode='lines',
            line=dict(color='#FF5733', width=2) # สีส้ม/แดง
        ), row=1, col=1)
        
        # เส้น Z1 Bottom (แชร์พื้นที่และแกน Y ร่วมกับ Z1 Top)
        fig.add_trace(go.Scatter(
            x=df['DateTime'], y=df['Z1_Bottom'],
            name="Z1 Bottom", mode='lines',
            line=dict(color='#FFC300', width=2, dash='dash') # สีเหลือง เส้นประ เพื่อให้เห็นความต่าง
        ), row=1, col=1)


        # --- แถวที่ 2: พล็อตข้อมูล Dryer Zone #2 ---
        # เส้น Z2 Top
        fig.add_trace(go.Scatter(
            x=df['DateTime'], y=df['Z2_Top'],
            name="Z2 Top", mode='lines',
            line=dict(color='#3357FF', width=2) # สีน้ำเงิน
        ), row=2, col=1)
        
        # เส้น Z2 Bottom (แชร์พื้นที่และแกน Y ร่วมกับ Z2 Top)
        fig.add_trace(go.Scatter(
            x=df['DateTime'], y=df['Z2_Bottom'],
            name="Z2 Bottom", mode='lines',
            line=dict(color='#33FFFB', width=2, dash='dash') # สีฟ้า เส้นประ
        ), row=2, col=1)

        # 3. ตกแต่ง Layout ให้ Interactive ซูมแล้วเลื่อนตามกันทั้งโซน 1 และ 2
        fig.update_layout(
            template="plotly_dark",
            height=700,
            title_text="Dryer Process Monitoring: Zone #1 vs Zone #2 (Top & Bottom Overlay)",
            hovermode="x unified" # เอาเมาส์ชี้จุดเดียว จะเทียบค่า Top/Bottom ของโซนนั้นได้ทันที
        )

        # ตั้งชื่อแกน Y ให้สอดคล้องกับพารามิเตอร์ที่คุณวัดค่า
        fig.update_yaxes(title_text="Process Value (PV)", row=1, col=1)
        fig.update_yaxes(title_text="Process Value (PV)", row=2, col=1)
        fig.update_xaxes(title_text="Date & Time", row=2, col=1)

        # แสดงผลลัพธ์บนหน้าจอ Streamlit
        st.plotly_chart(fig, use_container_width=True)
        
        with st.expander("🔍 ตรวจสอบโครงสร้างตารางข้อมูลดิบ (Data Table)"):
            st.dataframe(df.head(100))
    else:
        st.error("❌ ไม่สามารถแยกคอลัมน์ข้อมูลสำหรับ Dryer Z#1 และ Z#2 ได้ โครงสร้างลำดับชุดตัวเลขในไฟล์มีความซับซ้อน")
else:
    st.info("💡 กรุณาอัปโหลดไฟล์ .DAD เพื่อเริ่มต้นแยกการวิเคราะห์ข้อมูลตามแต่ละโซน")
