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
st.title("🏭 Factory Process Master Dashboard - True Machine Synced")
st.subheader("จัดลอนสัญญาณดิบเข้าช่องพารามิเตอร์ตามแท็บหน้าจอ DxViewerE จริง")

uploaded_file = st.file_uploader("อัปโหลดไฟล์ดิบ .DAD ของคุณที่นี่", type=["dad", "dat"])

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    text_data = file_bytes.decode('latin-1', errors='ignore')
    
    # 1. สกัดตัวเลขทศนิยมแท้จริงทั้งหมดจากไฟล์ดิบ โดยไม่ผ่านการบิดเบือนสเกลคณิตศาสตร์
    all_numbers = re.findall(r'[-+]?\d*\.\d+(?:[eE][-+]?\d+)?|\b\d{1,4}\b', text_data)
    numeric_stream = [float(n) for n in all_numbers]
    
    # ล้างเฉพาะค่าขยะภายนอกพิกัด เช่น ตัวเลขติดลบมหาศาล หรือเกินค่าเตาหลอม
    clean_stream = [n for n in numeric_stream if -120.0 <= n <= 2500.0]
    
    detected_channels = 23
    
    if len(clean_stream) >= detected_channels:
        rows = len(clean_stream) // detected_channels
        matrix_data = np.array(clean_stream[:rows * detected_channels]).reshape(-1, detected_channels)
        
        col_names = [f'CH_{i+1}' for i in range(detected_channels)]
        df = pd.DataFrame(matrix_data, columns=col_names)
        
        # ⏱️ แถบตั้งค่ากะเวลาทำงาน (ปรับ Default ออโต้ให้แมตช์ตามหน้าจอเครื่องบันทึก)
        st.sidebar.header("⏱️ ตั้งค่าเวลาบันทึก (Time Settings)")
        start_date = st.sidebar.date_input("เลือกวันที่เริ่มต้นขบวนการผลิต", value=pd.to_datetime('2026-08-12'))
        start_time = st.sidebar.time_input("เลือกเวลาที่เริ่มบันทึก", value=pd.to_datetime('2026-08-12 01:30:00').time())
        time_unit = st.sidebar.selectbox("ช่วงระยะเวลาห่างต่อจุดข้อมูล", ["วินาที (Seconds)", "นาที (Minutes)"], index=1) # ปรับเริ่มต้นเป็นนาทีตามหน้าจอเทรนด์
        time_value = st.sidebar.number_input("จำนวนหน่วยเวลาต่อ 1 จุด", min_value=1, value=1)
        
        freq_code = f"{time_value}s" if time_unit == "วินาที (Seconds)" else f"{time_value}min"
        start_timestamp = pd.to_datetime(f"{start_date} {start_time}")
        df['DateTime'] = pd.date_range(start=start_timestamp, periods=len(df), freq=freq_code)
        
        st.success(f"🔓 ดึงสัญญาณแท้จริงจำนวน {len(df)} แถวข้อมูลเข้าสู่แผงควบคุมหลักสำเร็จ")

        # 2. เริ่มสร้างโครงสร้าง Subplots แบบ 5 ชั้นแนวตั้ง ลิงก์แกนเวลาร่วมกัน
        fig = make_subplots(
            rows=5, 
            cols=1, 
            shared_xaxes=True, 
            vertical_spacing=0.05,
            specs=[[{"secondary_y": False}], # Dryer
                   [{"secondary_y": False}], # Heating Top
                   [{"secondary_y": False}], # Heating Bottom
                   [{"secondary_y": True}],  # เปิดแกนคู่สำหรับ Oxygen (ซ้าย) และ N2 Flow (ขวา)
                   [{"secondary_y": False}]] # Dew Point
        )

        # ----------------------------------------------------
        # กล่องที่ 1: Dryer (ถอนตามช่อง CH_4 และ CH_3 อิงตามแท็บโปรแกรม)
        # ----------------------------------------------------
        if 'CH_4' in df.columns:
            fig.add_trace(go.Scatter(x=df['DateTime'], y=df['CH_4'], name="Dryer #1", legend="legend1", line=dict(color='#FF5733', width=2)), row=1, col=1)
        if 'CH_3' in df.columns:
            fig.add_trace(go.Scatter(x=df['DateTime'], y=df['CH_3'], name="Dryer #2", legend="legend1", line=dict(color='#FF8D33', width=2)), row=1, col=1)

        # ----------------------------------------------------
        # กล่องที่ 2: Heating Zone 1-7 (Top - แมปอักษรแท้ตรงล็อกช่องเครื่องบันทึกด้านซ้าย)
        # ----------------------------------------------------
        # ช่องที่ 5 ถึง 11 คือชุด Zone #1 - Zone #7 ตามผังบอร์ดเครื่องจักร
        heat_start_idx = 5
        for i in range(0, 7):
            ch_name = f'CH_{heat_start_idx + i}'
            if ch_name in df.columns:
                fig.add_trace(go.Scatter(x=df['DateTime'], y=df[ch_name], name=f"H-Zone {i+1} (Top)", legend="legend2", line=dict(width=2)), row=2, col=1)

        # ----------------------------------------------------
        # กล่องที่ 3: Heating Zone 8-14 (Bottom - เส้นประ)
        # ----------------------------------------------------
        for i in range(7, 14):
            ch_name = f'CH_{heat_start_idx + i}'
            if ch_name in df.columns:
                fig.add_trace(go.Scatter(x=df['DateTime'], y=df[ch_name], name=f"H-Zone {i-6} (Bottom)", legend="legend3", line=dict(width=1.5, dash='dash')), row=3, col=1)

        # ----------------------------------------------------
        # กล่องที่ 4: Oxygen Exit & Entrance [ย้ายมาฝั่งซ้ายคู่กันตามสั่ง] และโยน N2 Flow ไปฝั่งขวา
        # ----------------------------------------------------
        # ดึงช่องแท็ป Oxygen ต้นไฟล์ (CH_1 และ CH_2) ลงแกนหลักฝั่งซ้าย (secondary_y=False)
        if 'CH_1' in df.columns:
            fig.add_trace(go.Scatter(x=df['DateTime'], y=df['CH_1'], name="O2 Entrance (ppm)", legend="legend4", line=dict(color='#33FF57', width=2)), row=4, col=1, secondary_y=False)
        if 'CH_2' in df.columns:
            fig.add_trace(go.Scatter(x=df['DateTime'], y=df['CH_2'], name="O2 Exit (ppm)", legend="legend4", line=dict(color='#1bba3c', width=2)), row=4, col=1, secondary_y=False)

        # โยนชุดอัตราไหล N2 Flow ถัดไป (CH_19 หรือช่องสัญญาณเสริมความดัน) ไปที่แกนขวาหลัก (secondary_y=True)
        if 'CH_19' in df.columns:
            fig.add_trace(go.Scatter(x=df['DateTime'], y=df['CH_19'], name="N2 Flow (h3/h)", legend="legend4", line=dict(color='#3357FF', width=2)), row=4, col=1, secondary_y=True)

        # ----------------------------------------------------
        # กล่องที่ 5: Dew Point (สเกลทิศทางปกติอิงตามคลื่นสัญญาณ CH_23)
        # ----------------------------------------------------
        if 'CH_23' in df.columns:
            fig.add_trace(go.Scatter(x=df['DateTime'], y=df['CH_23'], name="Dew Point", legend="legend5", line=dict(color='#E333FF', width=2, dash='dot')), row=5, col=1)

        # 3. จัดสรรผังหน้าต่างแผงควบคุม และเรียงกลุ่ม Legend Box ไว้ขวาสุดของแต่ละชั้น
        fig.update_layout(
            template="plotly_dark",
            height=1100, 
            hovermode="x unified",
            title_text="Yokogawa Process Analyzer Master Dashboard (True Machine Synced Mode)",
            legend1=dict(traceorder="normal", x=1.02, y=0.94, bgcolor="rgba(0,0,0,0)"),
            legend2=dict(traceorder="normal", x=1.02, y=0.75, bgcolor="rgba(0,0,0,0)"),
            legend3=dict(traceorder="normal", x=1.02, y=0.55, bgcolor="rgba(0,0,0,0)"),
            legend4=dict(traceorder="normal", x=1.02, y=0.35, bgcolor="rgba(0,0,0,0)"), # รวมพวก Oxygen และ N2 ไว้บล็อกขวาชั้นเดียวกันตามสั่ง
            legend5=dict(traceorder="normal", x=1.02, y=0.12, bgcolor="rgba(0,0,0,0)")
        )
        
        # ปรับขอบเขตแกนให้ออโต้สเกลตามข้อมูลดิบของเครื่องบันทึกโดยไม่ล็อกสเกลบีบอัด เพื่อให้เห็นสโลปการขยับของสัญญาณจริง
        fig.update_yaxes(title_text="Dryer Temp (°C)", autorange=True, row=1, col=1)
        fig.update_yaxes(title_text="Heating Top (°C)", autorange=True, row=2, col=1)
        fig.update_yaxes(title_text="Heating Bottom (°C)", autorange=True, row=3, col=1)
        
        # ล็อกป้ายข้อความแกนซ้ายและแกนขวาของกล่องที่ 4 แยกขาดกัน
        fig.update_yaxes(title_text="Oxygen Exit & Entrance (ppm)", color="#33FF57", autorange=True, row=4, col=1, secondary_y=False)
        fig.update_yaxes(title_text="N2 Flow (h3/h)", color="#3357FF", autorange=True, row=4, col=1, secondary_y=True)
        
        fig.update_yaxes(title_text="Dew Point (°Cdp)", autorange=True, row=5, col=1)
        fig.update_xaxes(title_text="Date & Time (Synchronized Timeline)", row=5, col=1)

        st.plotly_chart(fig, use_container_width=True)
        
    else:
        st.error("❌ ชุดตัวเลขในไฟล์ดิบสั้นเกินไป ไม่เพียงพอต่อการจัดวางระบบ 23 ช่องสัญญาณ")
else:
    st.info("💡 กรุณาอัปโหลดไฟล์บันทึกสัญญาณ (.DAD) เพื่อพล็อตกราฟเทียบผังหน้าจอเครื่องจักรเสร็จสมบูรณ์")
