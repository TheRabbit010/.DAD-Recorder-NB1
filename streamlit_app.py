import subprocess
import sys

# ติดตั้งไลบรารีที่จำเป็นอัตโนมัติ
def install_package(package_name):
    try:
        __import__(package_name)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])

install_package("pandas")
install_package("plotly")
install_package("numpy")

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import re
import numpy as np

st.set_page_config(layout="wide")
st.title("🏭 Factory Process Dashboard - High-Density Complete Subplots")
st.subheader("ระบบพล็อตกราฟแยกพารามิเตอร์ 4 ชั้น พร้อมปรับสเกลเวลาจริง")

uploaded_file = st.file_uploader("อัปโหลดไฟล์ดิบ .DAD ของคุณที่นี่", type=["dad", "dat"])

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    text_data = file_bytes.decode('latin-1', errors='ignore')
    
    # 1. ลอจิกขูดข้อมูลความละเอียดสูง ดึงค่าทศนิยมและจำนวนเต็มทั้งหมดจากไฟล์ดิบ
    all_numbers = re.findall(r'[-+]?\d*\.\d+(?:[eE][-+]?\d+)?|\b\d{1,4}\b', text_data)
    numeric_stream = [float(n) for n in all_numbers]
    
    # กรองล้างค่าขยะภายนอกช่วงเครื่องมือวัดอุตสาหกรรม
    clean_stream = [n for n in numeric_stream if -200.0 < n < 6000.0]
    
    # ล็อกจำนวนช่องสัญญาณให้ตรงกับ 23 คอลัมน์ของสถานีวัด Yokogawa จริง
    detected_channels = 23
    
    if len(clean_stream) >= detected_channels:
        # ตัดเศษข้อมูลท่อนปลายสุดทิ้ง เพื่อให้จัดเข้าตาราง Matrix ขนาด 23 คอลัมน์ได้พอดีเป๊ะ
        rows = len(clean_stream) // detected_channels
        matrix_data = np.array(clean_stream[:rows * detected_channels]).reshape(-1, detected_channels)
        
        # จัดพารามิเตอร์ลงตาราง DataFrame ตามโครงสร้างสถานีควบคุม
        col_names = [f'CH_{i+1}' for i in range(detected_channels)]
        df = pd.DataFrame(matrix_data, columns=col_names)
        
        # ----------------------------------------------------
        # [เพิ่มระบบตั้งค่าเวลาดิฟ] ให้ผู้ใช้เลือกปรับความถี่ของการบันทึกข้อมูลได้เองผ่านหน้าเว็บ
        # ----------------------------------------------------
        st.sidebar.header("⏱️ ตั้งค่าเวลาบันทึก (Time Settings)")
        start_date = st.sidebar.date_input("เลือกวันที่เริ่มต้นขบวนการผลิต", value=pd.to_datetime('2026-09-02'))
        start_time = st.sidebar.time_input("เลือกเวลาที่เริ่มบันทึก", value=pd.to_datetime('2026-09-02 00:00:00').time())
        
        # ตั้งค่าจังหวะเวลา (Sampling Interval) เช่น ทุกๆ 10 วินาที, 1 นาที
        time_unit = st.sidebar.selectbox("ช่วงระยะเวลาห่างต่อจุดข้อมูล (Interval)", ["วินาที (Seconds)", "นาที (Minutes)"], index=0)
        time_value = st.sidebar.number_input("จำนวนหน่วยเวลาต่อ 1 จุด", min_value=1, value=10) # ค่าเริ่มต้นปรับเป็นทุก 10 วินาทีเพื่อขยายแกน X ให้กว้างขึ้น
        
        # คำนวณความถี่แกน X ตามที่ผู้ใช้กำหนด
        freq_code = f"{time_value}s" if time_unit == "วินาที (Seconds)" else f"{time_value}min"
        start_timestamp = pd.to_datetime(f"{start_date} {start_time}")
        
        df['DateTime'] = pd.date_range(start=start_timestamp, periods=len(df), freq=freq_code)
        
        st.success(f"🔓 ถอดรหัสคลื่นสัญญาณสำเร็จ! แสดงผลครบทั้ง {detected_channels} ช่องสัญญาณ (ความละเอียด {len(df)} แถวข้อมูล)")

        # 2. สร้างโครงสร้าง Subplots แบบ 4 ชั้นแนวตั้ง (แกนเวลารวมลิงก์กันอัตโนมัติ)
        fig = make_subplots(
            rows=4, 
            cols=1, 
            shared_xaxes=True, 
            vertical_spacing=0.06,
            specs=[[{"secondary_y": False}],
                   [{"secondary_y": False}],
                   [{"secondary_y": True}],  # เปิดแกนคู่สำหรับกล่องที่ 3 (O2 แกนซ้าย / N2 แกนขวา)
                   [{"secondary_y": False}]]
        )

        # ----------------------------------------------------
        # กล่องที่ 1: Dryer #1 & Dryer #2 (CH_1 และ CH_2)
        # ----------------------------------------------------
        if 'CH_1' in df.columns:
            fig.add_trace(go.Scatter(x=df['DateTime'], y=df['CH_1'], name="Dryer #1", line=dict(color='#FF5733', width=2)), row=1, col=1)
        if 'CH_2' in df.columns:
            fig.add_trace(go.Scatter(x=df['DateTime'], y=df['CH_2'], name="Dryer #2", line=dict(color='#FF8D33', width=2)), row=1, col=1)

        # ----------------------------------------------------
        # กล่องที่ 2: Heating Zone 1-14 (Top & Bottom Overlay)
        # ----------------------------------------------------
        # Heating Zone 1-7: Top (เริ่มจาก CH_5 ถึง CH_11 เป็นเส้นทึบ)
        heat_start_idx = 5
        for i in range(0, 7):
            ch_name = f'CH_{heat_start_idx + i}'
            if ch_name in df.columns:
                fig.add_trace(go.Scatter(x=df['DateTime'], y=df[ch_name], name=f"Heating Z{i+1} (Top)", line=dict(width=1.5)), row=2, col=1)

        # Heating Zone 8-14: Bottom (เริ่มจาก CH_12 ถึง CH_18 เป็นเส้นประ)
        for i in range(7, 14):
            ch_name = f'CH_{heat_start_idx + i}'
            if ch_name in df.columns:
                fig.add_trace(go.Scatter(x=df['DateTime'], y=df[ch_name], name=f"Heating Z{i+1} (Bottom)", line=dict(width=1.5, dash='dash')), row=2, col=1)

        # ----------------------------------------------------
        # กล่องที่ 3: Oxygen ppm O2 (CH_3 - แกนซ้าย) & N2 Flow (CH_4 - แกนขวา)
        # ----------------------------------------------------
        if 'CH_3' in df.columns:
            fig.add_trace(go.Scatter(
                x=df['DateTime'], y=df['CH_3'], name="Oxygen (ppm O2)", 
                line=dict(color='#33FF57', width=2)
            ), row=3, col=1, secondary_y=False)

        if 'CH_4' in df.columns:
            fig.add_trace(go.Scatter(
                x=df['DateTime'], y=df['CH_4'], name="N2 Flow (h3/h)", 
                line=dict(color='#3357FF', width=2)
            ), row=3, col=1, secondary_y=True)

        # ----------------------------------------------------
        # กล่องที่ 4: Dew Point (CH_23 - คอลัมน์ขวาสุดออโต้สเกล)
        # ----------------------------------------------------
        if 'CH_23' in df.columns:
            fig.add_trace(go.Scatter(
                x=df['DateTime'], y=df['CH_23'], name="Dew Point", 
                line=dict(color='#E333FF', width=2, dash='dot')
            ), row=4, col=1)

        # 3. ตั้งค่า Layout และชื่อกำกับแกนของแต่ละกล่องย่อยให้ครบถ้วน
        fig.update_layout(
            template="plotly_dark",
            height=980,  # เพิ่มพื้นที่แนวตั้งเพื่อให้มองเห็นครบทั้ง 4 กล่องชัดเจน
            hovermode="x unified",
            title_text="Yokogawa Process Analyzer Dashboard (High-Density Complete Subplots)"
        )
        
        # ใส่หัวข้อแกน Y ให้แต่ละกล่องตามลำดับพารามิเตอร์
        fig.update_yaxes(title_text="Dryer Temp (°C)", row=1, col=1)
        fig.update_yaxes(title_text="Heating Temp (°C)", row=2, col=1)
        
        # กล่องที่ 3 ตั้งค่าชื่อแยกแกนซ้ายและขวาออกชัดเจน
        fig.update_yaxes(title_text="Oxygen (ppm O2)", color="#33FF57", row=3, col=1, secondary_y=False)
        fig.update_yaxes(title_text="N2 Flow (h3/h)", color="#3357FF", row=3, col=1, secondary_y=True)
        
        fig.update_yaxes(title_text="Dew Point (Auto)", row=4, col=1)
        fig.update_xaxes(title_text="Date & Time (Process Timeline)", row=4, col=1)

        # พล็อตกราฟขึ้นแสดงบนหน้าเว็บ Streamlit
        st.plotly_chart(fig, use_container_width=True)
        
        # เพิ่มตารางข้อมูลจริงให้พนักงานตรวจสอบค่าได้ด้านล่างกราฟ
        with st.expander("🔍 ตรวจสอบตารางข้อมูลดิบผ่านระบบช่องสัญญาณ (Raw Channels Preview)"):
            st.dataframe(df)
            
    else:
        st.error("❌ ชุดตัวเลขในไฟล์ดิบสั้นเกินไป ไม่เพียงพอต่อการจัดวางโครงสร้าง 23 ช่องสัญญาณ")
else:
    st.info("💡 กรุณาอัปโหลดไฟล์บันทึกสัญญาณ (.DAD) เพื่อพล็อตกราฟแยกพารามิเตอร์แบบครบสมบูรณ์")
