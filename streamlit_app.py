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
st.title("🏭 Integrated Process Dashboard - Custom Y-Axes Layout")
st.subheader("ปรับตำแหน่งแกน Y ตามพารามิเตอร์ของโรงงาน")

uploaded_file = st.file_uploader("อัปโหลดไฟล์ดิบ .DAD ของคุณที่นี่", type=["dad", "dat"])

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    text_data = file_bytes.decode('latin-1', errors='ignore')
    
    # 1. สกัดตัวเลขทั้งหมดจากไฟล์ดิบ (รองรับค่าลบและทศนิยม)
    all_numbers = re.findall(r'[-+]?\d*\.\d+|\b\d{2,4}\b', text_data)
    numeric_stream = [float(n) for n in all_numbers]
    
    # กรองล้างค่าขยะไบนารีที่อยู่นอกช่วงเครื่องมือวัด
    clean_stream = [n for n in numeric_stream if -150.0 < n < 5000.0]
    
    # คำนวณจำนวนช่องสัญญาณทั้งหมด 19 คอลัมน์
    num_channels = 19
    rows = len(clean_stream) // num_channels
    
    if rows > 5:
        matrix_data = np.array(clean_stream[:rows * num_channels]).reshape(-1, num_channels)
        
        # จัดตารางข้อมูลลง DataFrame
        cols = ['Dryer_1', 'Dryer_2', 'ppm_O2', 'N2_Flow'] + [f'Heat_Z{i}' for i in range(1, 15)] + ['Dew_Point']
        df = pd.DataFrame(matrix_data, columns=cols)
        df['DateTime'] = pd.date_range(start='2026-09-02 00:00:00', periods=len(df), freq='1s')
        
        st.success(f"🔓 โหลดข้อมูลสำเร็จ! กำลังแสดงผลกราฟพล็อตแกนร่วม...")

        # 2. เริ่มสร้างออบเจ็กต์กราฟรวมเป็นหนึ่งเดียว
        fig = go.Figure()

        # ----------------------------------------------------
        # กลุ่มแกน Y ด้านซ้าย (Left Axis): Dryer, Heating, N2 Flow
        # ----------------------------------------------------
        # พล็อต Dryer #1 และ #2
        fig.add_trace(go.Scatter(x=df['DateTime'], y=df['Dryer_1'], name="Dryer #1", line=dict(color='#FF5733', width=2.5)))
        fig.add_trace(go.Scatter(x=df['DateTime'], y=df['Dryer_2'], name="Dryer #2", line=dict(color='#FF8D33', width=2.5)))

        # Heating Zone 1-7: Top (เส้นทึบ)
        for i in range(1, 8):
            fig.add_trace(go.Scatter(
                x=df['DateTime'], y=df[f'Heat_Z{i}'], 
                name=f"Heating Z{i} (Top)", 
                line=dict(width=1.5)
            ))

        # Heating Zone 8-14: Bottom (เส้นประ)
        for i in range(8, 15):
            fig.add_trace(go.Scatter(
                x=df['DateTime'], y=df[f'Heat_Z{i}'], 
                name=f"Heating Z{i} (Bottom)", 
                line=dict(width=1.5, dash='dash')
            ))

        # [ย้ายมาฝั่งซ้าย] พล็อตอัตราไหล N2 Flow
        fig.add_trace(go.Scatter(
            x=df['DateTime'], y=df['N2_Flow'], 
            name="N2 Flow (h3/h)", 
            line=dict(color='#3357FF', width=2)
        ))

        # ----------------------------------------------------
        # กลุ่มแกน Y ด้านขวา (Right Axis): ปริมาณออกซิเจน ppm O2
        # ----------------------------------------------------
        fig.add_trace(go.Scatter(
            x=df['DateTime'], y=df['ppm_O2'], 
            name="Oxygen (ppm O2)", 
            line=dict(color='#33FF57', width=2),
            yaxis="y2"
        ))

        # ----------------------------------------------------
        # กลุ่มแกน Y ด้านขวาเยื้อง (Far Right Axis): Dew Point
        # ----------------------------------------------------
        fig.add_trace(go.Scatter(
            x=df['DateTime'], y=df['Dew_Point'], 
            name="Dew Point", 
            line=dict(color='#E333FF', width=2, dash='dot'),
            yaxis="y3"
        ))

        # 3. ตั้งค่า Layout จัดระเบียบแกนซ้าย-ขวา
        fig.update_layout(
            template="plotly_dark",
            height=800,
            xaxis=dict(title="Timeline Index", domain=[0, 0.88]), # เผื่อพื้นที่ด้านขวาสำหรับแกน Dew Point
            
            # ตั้งค่าแกนซ้ายหลัก (อุณหภูมิ + N2 Flow)
            yaxis=dict(
                title="Temperature (°C) & N2 Flow (h3/h)",
                titlefont=dict(color="#FF8D33"),
                tickfont=dict(color="#FF8D33")
            ),
            # ตั้งค่าแกนขวาที่ 1 (ppm O2 อยู่ติดขอบกราฟด้านขวา)
            yaxis2=dict(
                title="Oxygen Concentration (ppm O2)",
                titlefont=dict(color="#33FF57"),
                tickfont=dict(color="#33FF57"),
                anchor="x",
                overlaying="y",
                side="right"
            ),
            # ตั้งค่าแกนขวาที่ 2 (Dew Point อยู่เยื้องขวาออกไปอีกสเต็ป พร้อม Auto Scale)
            yaxis3=dict(
                title="Dew Point (Auto-Scaled)",
                titlefont=dict(color="#E333FF"),
                tickfont=dict(color="#E333FF"),
                anchor="free",
                overlaying="y",
                side="right",
                position=0.94,
                autorange=True
            ),
            hovermode="x unified" # ตรวจสอบค่าทุกช่องสัญญาณ ณ เวลาเดียวกันได้ทันทีเมื่อชี้เมาส์
        )

        # เรนเดอร์หน้าจอกราฟขึ้นเว็บ Streamlit
        st.plotly_chart(fig, use_container_width=True)
        
    else:
        st.error("❌ ชุดตัวเลขในไฟล์ดิบจัดเรียงไม่ครบ 19 ช่องสัญญาณมาตรฐาน")
else:
    st.info("💡 กรุณาอัปโหลดไฟล์ .DAD เพื่ออัปเดตกราฟที่จัดตำแหน่งแกน Y ใหม่")
