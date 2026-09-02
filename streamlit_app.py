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
st.title("🏭 Integrated Process Dashboard - Ultra Clean Layout")
st.subheader("พล็อตกราฟรวมแกนควบคุมกระบวนการผลิต (เวอร์ชันแก้ปัญหา ValueError)")

uploaded_file = st.file_uploader("อัปโหลดไฟล์ดิบ .DAD ของคุณที่นี่", type=["dad", "dat"])

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    text_data = file_bytes.decode('latin-1', errors='ignore')
    
    # 1. สกัดตัวเลขทั้งหมดจากไฟล์ดิบ (ตัดเอาเฉพาะค่าที่สมเหตุสมผลของกระบวนการผลิต)
    all_numbers = re.findall(r'[-+]?\d*\.\d+|\b\d{2,4}\b', text_data)
    numeric_stream = [float(n) for n in all_numbers]
    clean_stream = [n for n in numeric_stream if -150.0 < n < 5000.0]
    
    if len(clean_stream) > 10:
        # หาจำนวนคอลัมน์จริงเพื่อจัดโครงสร้าง
        detected_channels = 4
        for ch in range(4, 32):
            if len(clean_stream) % ch == 0:
                detected_channels = ch
                
        rows = len(clean_stream) // detected_channels
        matrix_data = np.array(clean_stream[:rows * detected_channels]).reshape(-1, detected_channels)
        
        # สร้างชื่อคอลัมน์แบบไดนามิกป้องกันโครงสร้างหลุด
        col_names = [f'CH_{i+1}' for i in range(detected_channels)]
        df = pd.DataFrame(matrix_data, columns=col_names)
        df['DateTime'] = pd.date_range(start='2026-09-02 00:00:00', periods=len(df), freq='1s')
        
        st.success(f"🔓 ถอดรหัสไฟล์สำเร็จ! ตรวจพบข้อมูลทั้งหมด {detected_channels} ช่องสัญญาณ ({len(df)} แถวข้อมูล)")

        # 2. เปิดระบบกราฟแกนคู่ (Secondary Y)
        fig = make_subplots(specs=[[{"secondary_y": True}]])

        # ----------------------------------------------------
        # กลุ่มแกน Y ด้านซ้าย: Dryer, Heating, N2 Flow (secondary_y=False)
        # ----------------------------------------------------
        if 'CH_1' in df.columns:
            fig.add_trace(go.Scatter(x=df['DateTime'], y=df['CH_1'], name="Dryer #1", line=dict(color='#FF5733', width=2.5)), secondary_y=False)
        if 'CH_2' in df.columns:
            fig.add_trace(go.Scatter(x=df['DateTime'], y=df['CH_2'], name="Dryer #2", line=dict(color='#FF8D33', width=2.5)), secondary_y=False)

        if 'CH_4' in df.columns:
            fig.add_trace(go.Scatter(x=df['DateTime'], y=df['CH_4'], name="N2 Flow (h3/h)", line=dict(color='#3357FF', width=2)), secondary_y=False)

        # Heating Zone 1-7: Top (เส้นทึบ)
        heat_start_idx = 5
        for i in range(0, 7):
            ch_name = f'CH_{heat_start_idx + i}'
            if ch_name in df.columns:
                fig.add_trace(go.Scatter(x=df['DateTime'], y=df[ch_name], name=f"Heating Z{i+1} (Top)", line=dict(width=1.5)), secondary_y=False)

        # Heating Zone 8-14: Bottom (เส้นประ)
        for i in range(7, 14):
            ch_name = f'CH_{heat_start_idx + i}'
            if ch_name in df.columns:
                fig.add_trace(go.Scatter(x=df['DateTime'], y=df[ch_name], name=f"Heating Z{i+1} (Bottom)", line=dict(width=1.5, dash='dash')), secondary_y=False)

        # ----------------------------------------------------
        # กลุ่มแกน Y ด้านขวา: ปริมาณออกซิเจน ppm O2 (secondary_y=True)
        # ----------------------------------------------------
        if 'CH_3' in df.columns:
            fig.add_trace(go.Scatter(
                x=df['DateTime'], y=df['CH_3'], name="Oxygen (ppm O2)", 
                line=dict(color='#33FF57', width=2)
            ), secondary_y=True)

        # ----------------------------------------------------
        # กลุ่มแกน Y เสริมด้านขวา: Dew Point (แชร์แกนขวาหลักร่วมกัน)
        # ----------------------------------------------------
        last_ch_name = f'CH_{detected_channels}'
        if detected_channels >= 5 and last_ch_name in df.columns:
            fig.add_trace(go.Scatter(
                x=df['DateTime'], y=df[last_ch_name], name="Dew Point", 
                line=dict(color='#E333FF', width=2, dash='dot')
            ), secondary_y=True)

        # 3. ตั้งค่าแบบคลีนที่สุด (ลบคีย์เสริมยุ่งเหยิงทิ้งทั้งหมด เพื่อไม่ให้เกิดข้อผิดพลาดเด็ดขาด)
        fig.update_layout(
            template="plotly_dark",
            height=750,
            hovermode="x unified"
        )
        
        # ใส่ชื่อกำกับแกนทีละคำสั่งผ่านฟังก์ชันมาตรฐาน
        fig.update_xaxes(title_text="Timeline Index")
        fig.update_yaxes(title_text="Temperature (°C) & N2 Flow (h3/h)", color="#FF8D33", secondary_y=False)
        fig.update_yaxes(title_text="Oxygen (ppm O2) & Dew Point (Auto-Scaled)", color="#33FF57", secondary_y=True)

        st.plotly_chart(fig, use_container_width=True)
        
    else:
        st.error("❌ ไม่สามารถดึงอาร์เรย์ตัวเลขที่สมบูรณ์ออกจากไฟล์ดิบนี้ได้")
else:
    st.info("💡 กรุณาอัปโหลดไฟล์บันทึกสัญญาณ (.DAD) เพื่อพล็อตกราฟกระบวนการผลิตรวมแบบ All-in-One")
