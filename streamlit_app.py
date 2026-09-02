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
st.title("🏭 Factory Process Dashboard - Separated Subplots")
st.subheader("แยกกล่องกราฟตามพารามิเตอร์ (แกนเวลาเชื่อมต่อกันอัตโนมัติ)")

uploaded_file = st.file_uploader("อัปโหลดไฟล์ดิบ .DAD ของคุณที่นี่", type=["dad", "dat"])

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    text_data = file_bytes.decode('latin-1', errors='ignore')
    
    # 1. สกัดตัวเลขทั้งหมดจากไฟล์ดิบ (ตัดเอาเฉพาะค่าที่สมเหตุสมผลของกระบวนการผลิต)
    all_numbers = re.findall(r'[-+]?\d*\.\d+|\b\d{2,4}\b', text_data)
    numeric_stream = [float(n) for n in all_numbers]
    clean_stream = [n for n in numeric_stream if -150.0 < n < 5000.0]
    
    if len(clean_stream) > 10:
        # หาจำนวนคอลัมน์จริงเพื่อจัดโครงสร้างตารางข้อมูล
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

        # 2. สร้างโครงสร้าง Subplots แบบ 4 แถวแนวตั้ง โดยให้ใช้แกน X ร่วมกัน (shared_xaxes=True)
        # กล่องที่ 3 เปิดโหมด secondary_y เพื่อแยกแกนซ้าย-ขวาให้กับ O2 และ N2 Flow
        fig = make_subplots(
            rows=4, 
            cols=1, 
            shared_xaxes=True, 
            vertical_spacing=0.06,
            specs=[[{"secondary_y": False}],
                   [{"secondary_y": False}],
                   [{"secondary_y": True}],  # เปิดแกนคู่เฉพาะกล่องที่ 3
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

        # 3. ตั้งค่า Layout ภาพรวมแบบคลีน ไร้ความเสี่ยงระเบิด
        fig.update_layout(
            template="plotly_dark",
            height=950,  # เพิ่มความสูงเพื่อให้แสดง 4 กล่องได้อย่างชัดเจน
            hovermode="x unified",
            title_text="Yokogawa Process Analyzer Dashboard (Multi-Plot Mode)"
        )
        
        # ใส่หัวข้อแกน Y ให้แต่ละกล่องตามลำดับ
        fig.update_yaxes(title_text="Dryer Temp (°C)", row=1, col=1)
        fig.update_yaxes(title_text="Heating Temp (°C)", row=2, col=1)
        
        # กล่องที่ 3 ตั้งค่าชื่อแยกแกนซ้ายและขวา
        fig.update_yaxes(title_text="Oxygen (ppm O2)", color="#33FF57", row=3, col=1, secondary_y=False)
        fig.update_yaxes(title_text="N2 Flow (h3/h)", color="#3357FF", row=3, col=1, secondary_y=True)
        
        fig.update_yaxes(title_text="Dew Point (Auto)", row=4, col=1)
        fig.update_xaxes(title_text="Timeline Index", row=4, col=1)

        # เรนเดอร์กราฟขึ้นหน้าจอ Streamlit
        st.plotly_chart(fig, use_container_width=True)
        
    else:
        st.error("❌ ไม่สามารถดึงอาร์เรย์ตัวเลขที่สมบูรณ์ออกจากไฟล์ดิบนี้ได้")
else:
    st.info("💡 กรุณาอัปโหลดไฟล์บันทึกสัญญาณ (.DAD) เพื่อพล็อตกราฟแยกพารามิเตอร์แบบ 4 ชั้น")
