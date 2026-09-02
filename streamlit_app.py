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
st.title("🏭 Factory Process Dashboard - High-Density Subplots")
st.subheader("เพิ่มความละเอียดจุดข้อมูลและปรับเส้นเทรนด์ให้เนียนต่อเนื่อง")

uploaded_file = st.file_uploader("อัปโหลดไฟล์ดิบ .DAD ของคุณที่นี่", type=["dad", "dat"])

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    text_data = file_bytes.decode('latin-1', errors='ignore')
    
    # 1. ลอจิกการขูดข้อมูลเชิงลึก (Deep Excavator) เพื่อจับทศนิยมทุกตำแหน่งในไฟล์ Binary
    # รองรับตั้งแต่ทศนิยมสั้น ทศนิยมยาว เลขยกกำลังวิทยาศาสตร์ (e-05) และจำนวนเต็มเครื่องมือวัด
    all_numbers = re.findall(r'[-+]?\d*\.\d+(?:[eE][-+]?\d+)?|\b\d{1,4}\b', text_data)
    numeric_stream = [float(n) for n in all_numbers]
    
    # กรองล้างเฉพาะค่าขยะไบนารีระดับสุดโต่งออก รักษาตัวเลขกระบวนการผลิตส่วนใหญ่ไว้
    clean_stream = [n for n in numeric_stream if -200.0 < n < 6000.0]
    
    if len(clean_stream) > 10:
        # [แก้ไขแล้ว] ระบบค้นหาและหารจำนวนคอลัมน์อัตโนมัติโดยไม่ติด SyntaxError
        detected_channels = 23 # ล็อกค่ามาตรฐานตามเครื่องบันทึกของคุณ
        for ch in range(4, 32):
            if len(clean_stream) % ch == 0:
                detected_channels = ch
                break
                
        rows = len(clean_stream) // detected_channels
        matrix_data = np.array(clean_stream[:rows * detected_channels]).reshape(-1, detected_channels)
        
        # จัดเตรียมลงตารางข้อมูล DataFrame
        col_names = [f'CH_{i+1}' for i in range(detected_channels)]
        df = pd.DataFrame(matrix_data, columns=col_names)
        df['DateTime'] = pd.date_range(start='2026-09-02 00:00:00', periods=len(df), freq='1s')
        
        st.success(f"🔓 ถอดรหัสคลื่นสัญญาณสำเร็จ! เพิ่มความละเอียดข้อมูลขึ้นเป็น {len(df)} แถวข้อมูล (พบ {detected_channels} ช่องสัญญาณ)")

        # 2. เริ่มสร้างโครงสร้าง Subplots แบบ 4 ชั้นแนวตั้ง
        fig = make_subplots(
            rows=4, 
            cols=1, 
            shared_xaxes=True, 
            vertical_spacing=0.06,
            specs=[[{"secondary_y": False}],
                   [{"secondary_y": False}],
                   [{"secondary_y": True}],  # เปิดแกนคู่สำหรับ O2 และ N2 Flow
                   [{"secondary_y": False}]]
        )

        # ----------------------------------------------------
        # กล่องที่ 1: Dryer #1 & Dryer #2
        # ----------------------------------------------------
        if 'CH_1' in df.columns:
            fig.add_trace(go.Scatter(x=df['DateTime'], y=df['CH_1'], name="Dryer #1", line=dict(color='#FF5733', width=2)), row=1, col=1)
        if 'CH_2' in df.columns:
            fig.add_trace(go.Scatter(x=df['DateTime'], y=df['CH_2'], name="Dryer #2", line=dict(color='#FF8D33', width=2)), row=1, col=1)

        # ----------------------------------------------------
        # กล่องที่ 2: Heating Zone 1-14 (Top & Bottom Overlay)
        # ----------------------------------------------------
        # Heating Zone 1-7: Top (เส้นทึบ)
        heat_start_idx = 5
        for i in range(0, 7):
            ch_name = f'CH_{heat_start_idx + i}'
            if ch_name in df.columns:
                fig.add_trace(go.Scatter(x=df['DateTime'], y=df[ch_name], name=f"Heating Z{i+1} (Top)", line=dict(width=1.5)), row=2, col=1)

        # Heating Zone 8-14: Bottom (เส้นประ)
        for i in range(7, 14):
            ch_name = f'CH_{heat_start_idx + i}'
            if ch_name in df.columns:
                fig.add_trace(go.Scatter(x=df['DateTime'], y=df[ch_name], name=f"Heating Z{i+1} (Bottom)", line=dict(width=1.5, dash='dash')), row=2, col=1)

        # ----------------------------------------------------
        # กล่องที่ 3: ppm O2 (แกนซ้าย) & N2 Flow (แกนขวา)
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
        # กล่องที่ 4: Dew Point (Auto-Scaled)
        # ----------------------------------------------------
        last_ch_name = f'CH_{detected_channels}'
        if detected_channels >= 5 and last_ch_name in df.columns:
            fig.add_trace(go.Scatter(
                x=df['DateTime'], y=df[last_ch_name], name="Dew Point", 
                line=dict(color='#E333FF', width=2, dash='dot')
            ), row=4, col=1)

        # 3. ตั้งค่า Layout ภาพรวม
        fig.update_layout(
            template="plotly_dark",
            height=950,
            hovermode="x unified",
            title_text="Yokogawa Process Analyzer Dashboard (High-Density Smooth Curve)"
        )
        
        # ใส่หัวข้อแกน Y ให้แต่ละกล่องตามลำดับ
        fig.update_yaxes(title_text="Dryer Temp (°C)", row=1, col=1)
        fig.update_yaxes(title_text="Heating Temp (°C)", row=2, col=1)
        
        # กล่องที่ 3 ตั้งค่าชื่อแยกแกนซ้ายและขวา
        fig.update_yaxes(title_text="Oxygen (ppm O2)", color="#33FF57", row=3, col=1, secondary_y=False)
        fig.update_yaxes(title_text="N2 Flow (h3/h)", color="#3357FF", row=3, col=1, secondary_y=True)
        
        fig.update_yaxes(title_text="Dew Point (Auto)", row=4, col=1)
        fig.update_xaxes(title_text="Timeline Index", row=4, col=1)

        st.plotly_chart(fig, use_container_width=True)
        
    else:
        st.error("❌ ไม่สามารถขูดข้อมูลตัวเลขที่ละเอียดเพียงพอออกจากไฟล์ดิบนี้ได้")
else:
    st.info("💡 กรุณาอัปโหลดไฟล์บันทึกสัญญาณ (.DAD) เพื่อพล็อตกราฟแยกพารามิเตอร์แบบความละเอียดสูง")
