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
import re
import numpy as np

st.set_page_config(layout="wide")
st.title("🏭 Integrated Process Dashboard - Final Stable Layout")
st.subheader("พล็อตกราฟรวมแกนอัตโนมัติ ทนทานต่อไฟล์ดิบทุกเวอร์ชัน")

uploaded_file = st.file_uploader("อัปโหลดไฟล์ดิบ .DAD ของคุณที่นี่", type=["dad", "dat"])

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    text_data = file_bytes.decode('latin-1', errors='ignore')
    
    # 1. สกัดตัวเลขทั้งหมดจากไฟล์ดิบ (ตัดเอาเฉพาะค่าที่สมเหตุสมผลของกระบวนการผลิต)
    all_numbers = re.findall(r'[-+]?\d*\.\d+|\b\d{2,4}\b', text_data)
    numeric_stream = [float(n) for n in all_numbers]
    clean_stream = [n for n in numeric_stream if -150.0 < n < 5000.0]
    
    if len(clean_stream) > 10:
        # บังคับหาตัวหารตามจำนวนคอลัมน์จริงเพื่อจัดโครงสร้าง
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

        fig = go.Figure()

        # ----------------------------------------------------
        # กลุ่มแกน Y ด้านซ้าย: Dryer, Heating, N2 Flow
        # ----------------------------------------------------
        # พล็อต Dryer #1 และ #2
        if 'CH_1' in df.columns:
            fig.add_trace(go.Scatter(x=df['DateTime'], y=df['CH_1'], name="Dryer #1", line=dict(color='#FF5733', width=2.5)))
        if 'CH_2' in df.columns:
            fig.add_trace(go.Scatter(x=df['DateTime'], y=df['CH_2'], name="Dryer #2", line=dict(color='#FF8D33', width=2.5)))

        # พล็อตอัตราไหล N2 Flow ไว้ฝั่งซ้ายร่วมด้วย
        if 'CH_4' in df.columns:
            fig.add_trace(go.Scatter(x=df['DateTime'], y=df['CH_4'], name="N2 Flow (h3/h)", line=dict(color='#3357FF', width=2)))

        # Heating Zone 1-7: Top (เส้นทึบ)
        heat_start_idx = 5
        for i in range(0, 7):
            ch_name = f'CH_{heat_start_idx + i}'
            if ch_name in df.columns:
                fig.add_trace(go.Scatter(x=df['DateTime'], y=df[ch_name], name=f"Heating Z{i+1} (Top)", line=dict(width=1.5)))

        # Heating Zone 8-14: Bottom (เส้นประ)
        for i in range(7, 14):
            ch_name = f'CH_{heat_start_idx + i}'
            if ch_name in df.columns:
                fig.add_trace(go.Scatter(x=df['DateTime'], y=df[ch_name], name=f"Heating Z{i+1} (Bottom)", line=dict(width=1.5, dash='dash')))

        # ----------------------------------------------------
        # กลุ่มแกน Y ด้านขวา (Right Axis): ปริมาณออกซิเจน ppm O2
        # ----------------------------------------------------
        if 'CH_3' in df.columns:
            fig.add_trace(go.Scatter(
                x=df['DateTime'], y=df['CH_3'], name="Oxygen (ppm O2)", 
                line=dict(color='#33FF57', width=2), yaxis="y2"
            ))

        # ----------------------------------------------------
        # กลุ่มแกน Y ด้านขวาเยื้อง (Far Right Axis): Dew Point
        # ----------------------------------------------------
        last_ch_name = f'CH_{detected_channels}'
        if detected_channels >= 5 and last_ch_name in df.columns:
            fig.add_trace(go.Scatter(
                x=df['DateTime'], y=df[last_ch_name], name="Dew Point", 
                line=dict(color='#E333FF', width=2, dash='dot'), yaxis="y3"
            ))

        # 3. ตกแต่ง Layout แยกระดับสเกลแกน Y (ปรับปรุงโครงสร้างแก้ ValueError)
        fig.update_layout(
            template="plotly_dark",
            height=780,
            hovermode="x unified",
            xaxis=dict(title="Timeline Index", domain=[0, 0.85]),
            
            # แกนซ้ายหลัก
            yaxis=dict(
                title="Temperature (°C) & N2 Flow (h3/h)",
                titlefont=dict(color="#FF8D33"),
                tickfont=dict(color="#FF8D33")
            ),
            
            # แกนขวาหลัก (y2)
            yaxis2=dict(
                title="Oxygen Concentration (ppm O2)",
                titlefont=dict(color="#33FF57"),
                tickfont=dict(color="#33FF57"),
                overlaying="y",
                side="right"
            ),
            
            # แกนขวาสุดแยกสเกลอิสระ (y3)
            yaxis3=dict(
                title="Dew Point (Auto-Scaled)",
                titlefont=dict(color="#E333FF"),
                tickfont=dict(color="#E333FF"),
                overlaying="y",
                side="right",
                position=0.95,
                autorange=True
            )
        )

        st.plotly_chart(fig, use_container_width=True)
        
    else:
        st.error("❌ ไม่สามารถดึงอาร์เรย์ตัวเลขที่สมบูรณ์ออกจากไฟล์ดิบนี้ได้ รบกวนตรวจสอบว่าไฟล์มีขนาด 0 KB หรือไม่")
else:
    st.info("💡 กรุณาอัปโหลดไฟล์บันทึกสัญญาณ (.DAD) เพื่อพล็อตกราฟกระบวนการผลิตรวมแบบ All-in-One")
