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
st.title("🏭 Factory Process Master Dashboard - Scale Mapped Edition")
st.subheader("จัดกลุ่มพารามิเตอร์ตามช่วงสเกลจริงหน้างาน และแยก Legend Box ประจำกล่องย่อย")

uploaded_file = st.file_uploader("อัปโหลดไฟล์ดิบ .DAD ของคุณที่นี่", type=["dad", "dat"])

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    text_data = file_bytes.decode('latin-1', errors='ignore')
    
    # 1. ขูดตัวเลขทั้งหมดจากไฟล์ดิบขึ้นมาก่อนโดยไม่มีเงื่อนไข
    all_numbers = re.findall(r'[-+]?\d*\.\d+(?:[eE][-+]?\d+)?|\b\d{1,4}\b', text_data)
    raw_stream = [float(n) for n in all_numbers]
    
    # 2. ปรับลอจิกการคัดกรองตัวเลขแยกใส่ตะกร้าตามช่วงสเกลจริงที่คุณระบุมา (Scale-Based Demultiplexing)
    dryer_vals = [n for n in raw_stream if 180.0 <= n <= 450.0]
    heating_vals = [n for n in raw_stream if 500.0 <= n <= 700.0]
    oxygen_vals = [n for n in raw_stream if 0.0 <= n <= 200.0]
    dew_vals = [n for n in raw_stream if -110.0 <= n <= 20.0]
    
    # หาความยาวขั้นต่ำสุดของทุกกลุ่มข้อมูลเพื่อป้องกันตารางพัง
    min_len = min(len(dryer_vals)//2, len(heating_vals)//14, len(oxygen_vals)//2, len(dew_vals))
    
    if min_len > 2:
        # จัดการสกัดชุดตัวเลขลงโครงสร้าง DataFrame แยกแต่ละช่องสัญญาณแท้จริง
        data = {}
        
        # กล่องที่ 1: Dryer (2 ช่อง)
        data['Dryer_1'] = dryer_vals[0:min_len*2:2]
        data['Dryer_2'] = dryer_vals[1:min_len*2:2]
        
        # กล่องที่ 2: Heating Zone 1-14 (14 ช่อง)
        for i in range(14):
            data[f'Heat_Z{i+1}'] = heating_vals[i::14][:min_len]
            
        # กล่องที่ 3: Oxygen และ N2 Flow
        data['Oxygen_O2'] = oxygen_vals[0:min_len*2:2]
        data['N2_Flow'] = oxygen_vals[1:min_len*2:2]
        
        # กล่องที่ 4: Dew Point
        data['Dew_Point'] = dew_vals[:min_len]
        
        df = pd.DataFrame(data)
        
        # ⏱️ แถบตั้งค่าเวลาบันทึกด้านซ้ายมือ (Sidebar)
        st.sidebar.header("⏱️ ตั้งค่าเวลาบันทึก (Time Settings)")
        start_date = st.sidebar.date_input("เลือกวันที่เริ่มต้น", value=pd.to_datetime('2026-09-02'))
        start_time = st.sidebar.time_input("เลือกเวลาที่เริ่มบันทึก", value=pd.to_datetime('00:00:00').time())
        time_unit = st.sidebar.selectbox("ช่วงระยะเวลาห่างต่อจุดข้อมูล", ["วินาที (Seconds)", "นาที (Minutes)"], index=0)
        time_value = st.sidebar.number_input("จำนวนหน่วยเวลาต่อ 1 จุด", min_value=1, value=10)
        
        freq_code = f"{time_value}s" if time_unit == "วินาที (Seconds)" else f"{time_value}min"
        start_timestamp = pd.to_datetime(f"{start_date} {start_time}")
        df['DateTime'] = pd.date_range(start=start_timestamp, periods=len(df), freq=freq_code)
        
        st.success(f"🔓 ตรวจสอบและคัดแยกตำแหน่งพารามิเตอร์สำเร็จ! นำข้อมูล {len(df)} แถวเข้าสู่ระบบพล็อตโครงสร้าง")

        # 3. สร้างโครงสร้าง Subplots แบบ 4 ชั้นแนวตั้ง
        fig = make_subplots(
            rows=4, 
            cols=1, 
            shared_xaxes=True, 
            vertical_spacing=0.06,
            specs=[[{"secondary_y": False}],
                   [{"secondary_y": False}],
                   [{"secondary_y": True}], # เปิดแกนคู่สำหรับกล่องที่ 3
                   [{"secondary_y": False}]]
        )

        # ----------------------------------------------------
        # กล่องที่ 1: Dryer #1 & Dryer #2 (สเกล 200 - 400 'C)
        # ----------------------------------------------------
        fig.add_trace(go.Scatter(x=df['DateTime'], y=df['Dryer_1'], name="Dryer #1", legend="legend1", line=dict(color='#FF5733', width=2)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['DateTime'], y=df['Dryer_2'], name="Dryer #2", legend="legend1", line=dict(color='#FF8D33', width=2)), row=1, col=1)

        # ----------------------------------------------------
        # กล่องที่ 2: Heating Zone 1-14 (สเกล 580 - 650 'C)
        # ----------------------------------------------------
        # Heating Zone 1-7: Top (เส้นทึบ)
        for i in range(1, 8):
            fig.add_trace(go.Scatter(x=df['DateTime'], y=df[f'Heat_Z{i}'], name=f"Heating Z{i} (Top)", legend="legend2", line=dict(width=1.5)), row=2, col=1)

        # Heating Zone 8-14: Bottom (เส้นประ)
        for i in range(8, 15):
            fig.add_trace(go.Scatter(x=df['DateTime'], y=df[f'Heat_Z{i}'], name=f"Heating Z{i} (Bottom)", legend="legend2", line=dict(width=1.5, dash='dash')), row=2, col=1)

        # ----------------------------------------------------
        # กล่องที่ 3: Oxygen ppm O2 (สเกล 0 - 200) & N2 Flow (แกนขวา)
        # ----------------------------------------------------
        fig.add_trace(go.Scatter(
            x=df['DateTime'], y=df['Oxygen_O2'], name="Oxygen (ppm O2)", legend="legend3",
            line=dict(color='#33FF57', width=2)
        ), row=3, col=1, secondary_y=False)

        fig.add_trace(go.Scatter(
            x=df['DateTime'], y=df['N2_Flow'], name="N2 Flow (h3/h)", legend="legend3",
            line=dict(color='#3357FF', width=2)
        ), row=3, col=1, secondary_y=True)

        # ----------------------------------------------------
        # กล่องที่ 4: Dew Point (สเกล 10 ถึง -100 'C)
        # ----------------------------------------------------
        fig.add_trace(go.Scatter(x=df['DateTime'], y=df['Dew_Point'], name="Dew Point", legend="legend4", line=dict(color='#E333FF', width=2, dash='dot')), row=4, col=1)

        # 4. ดีไซน์หน้าต่าง Layout ปลดล็อกสเกลช่วง และจัดสรร Legend Box แยกประจำตำแหน่งกล่องย่อย
        fig.update_layout(
            template="plotly_dark",
            height=950,
            hovermode="x unified",
            title_text="Yokogawa Process Analyzer Dashboard (Scale Mapped Engine)",
            
            # ย้ายและจัดระเบียบ Legend Box ประจำกล่อง 1-4 ให้แยกเป็นบล็อกของตัวเอง
            legend1=dict(traceorder="normal", x=1.02, y=0.92, bgcolor="rgba(0,0,0,0)"),
            legend2=dict(traceorder="normal", x=1.02, y=0.68, bgcolor="rgba(0,0,0,0)"),
            legend3=dict(traceorder="normal", x=1.02, y=0.42, bgcolor="rgba(0,0,0,0)"),
            legend4=dict(traceorder="normal", x=1.02, y=0.15, bgcolor="rgba(0,0,0,0)")
        )
        
        # ปรับขอบเขตสเกลช่วงแกน Y ในแต่ละกล่องย่อยให้สอดคล้องกับพารามิเตอร์กระบวนการผลิตของคุณจริง
        fig.update_yaxes(title_text="Dryer Temp (°C)", range=[150, 450], row=1, col=1)
        fig.update_yaxes(title_text="Heating Temp (°C)", range=[550, 680], row=2, col=1)
        
        fig.update_yaxes(title_text="Oxygen (ppm O2)", color="#33FF57", range=[0, 220], row=3, col=1, secondary_y=False)
        fig.update_yaxes(title_text="N2 Flow (h3/h)", color="#3357FF", autorange=True, row=3, col=1, secondary_y=True)
        
        # ปรับแกน Dew Point ให้ติดลบลงด้านล่างตามธรรมชาติของจุดน้ำค้าง (10 ถึง -100)
        fig.update_yaxes(title_text="Dew Point (°C)", range=[-110, 20], row=4, col=1)
        fig.update_xaxes(title_text="Date & Time (Process Timeline)", row=4, col=1)

        st.plotly_chart(fig, use_container_width=True)
        
    else:
        st.error("❌ การจัดกลุ่มล้มเหลว: ช่วงข้อมูลในไฟล์จริงไม่สอดคล้องกับระดับสเกลโรงงานที่กำหนด")
else:
    st.info("💡 กรุณาอัปโหลดไฟล์บันทึกสัญญาณ (.DAD) เพื่อตรวจสอบกราฟสเกลปรับปรุงใหม่")
