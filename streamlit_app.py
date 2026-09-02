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
st.title("🏭 Factory Process Master Dashboard - Fixed Scale Layout")
st.subheader("ระบบพล็อตกราฟล็อกช่วงสเกลควบคุมจริงหน้างาน และแยกกลุ่มคำอธิบายประจำกล่อง")

uploaded_file = st.file_uploader("อัปโหลดไฟล์ดิบ .DAD ของคุณที่นี่", type=["dad", "dat"])

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    text_data = file_bytes.decode('latin-1', errors='ignore')
    
    # 1. ขูดข้อมูลตัวเลขทั้งหมดจากไฟล์ดิบโครงสร้างความละเอียดสูง
    all_numbers = re.findall(r'[-+]?\d*\.\d+(?:[eE][-+]?\d+)?|\b\d{1,3}\b', text_data)
    numeric_stream = [float(n) for n in all_numbers]
    clean_stream = [n for n in numeric_stream if -120.0 <= n <= 3000.0]
    
    detected_channels = 23
    
    if len(clean_stream) >= detected_channels:
        rows = len(clean_stream) // detected_channels
        matrix_data = np.array(clean_stream[:rows * detected_channels]).reshape(-1, detected_channels)
        
        col_names = [f'CH_{i+1}' for i in range(detected_channels)]
        df = pd.DataFrame(matrix_data, columns=col_names)
        
        # ⏱️ แถบตั้งค่าเวลาบันทึกด้านซ้ายมือ (Sidebar)
        st.sidebar.header("⏱️ ตั้งค่าเวลาบันทึก (Time Settings)")
        start_date = st.sidebar.date_input("เลือกวันที่เริ่มต้นขบวนการผลิต", value=pd.to_datetime('2026-09-02'))
        start_time = st.sidebar.time_input("เลือกเวลาที่เริ่มบันทึก", value=pd.to_datetime('00:00:00').time())
        time_unit = st.sidebar.selectbox("ช่วงระยะเวลาห่างต่อจุดข้อมูล", ["วินาที (Seconds)", "นาที (Minutes)"], index=0)
        time_value = st.sidebar.number_input("จำนวนหน่วยเวลาต่อ 1 จุด", min_value=1, value=10)
        
        freq_code = f"{time_value}s" if time_unit == "วินาที (Seconds)" else f"{time_value}min"
        start_timestamp = pd.to_datetime(f"{start_date} {start_time}")
        df['DateTime'] = pd.date_range(start=start_timestamp, periods=len(df), freq=freq_code)
        
        st.success(f"🔓 ถอดรหัสไฟล์ดิบสำเร็จ! กำลังปรับเทียบสเกลอุตสาหกรรม {detected_channels} สัญญาณต่อเนื่อง")

        # ฟังก์ชันคำนวณปรับสเกลตัวเลข (Min-Max Rescaling) ให้ตรงกับขอบเขตจริงของหน้างาน
        def scale_data(series, target_min, target_max):
            s_min, s_max = series.min(), series.max()
            if s_max - s_min == 0:
                return series + target_min
            return target_min + ((series - s_min) * (target_max - target_min) / (s_max - s_min))

        # 2. เริ่มสร้างโครงสร้าง Subplots แบบ 4 ชั้นแนวตั้ง
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
        # กล่องที่ 1: Dryer #1 & Dryer #2 (สเกลตามจริง 200 - 400 °C)
        # ----------------------------------------------------
        if 'CH_1' in df.columns:
            y1 = scale_data(df['CH_1'], 200.0, 400.0)
            fig.add_trace(go.Scatter(x=df['DateTime'], y=y1, name="Dryer #1", legend="legend1", line=dict(color='#FF5733', width=2)), row=1, col=1)
        if 'CH_2' in df.columns:
            y2 = scale_data(df['CH_2'], 200.0, 400.0)
            fig.add_trace(go.Scatter(x=df['DateTime'], y=y2, name="Dryer #2", legend="legend1", line=dict(color='#FF8D33', width=2)), row=1, col=1)

        # ----------------------------------------------------
        # กล่องที่ 2: Heating Zone 1-14 (สเกลตามจริง 580 - 650 °C)
        # ----------------------------------------------------
        heat_start_idx = 5
        # Heating Zone 1-7: Top (เส้นทึบ)
        for i in range(0, 7):
            ch_name = f'CH_{heat_start_idx + i}'
            if ch_name in df.columns:
                y_heat = scale_data(df[ch_name], 580.0, 650.0)
                fig.add_trace(go.Scatter(x=df['DateTime'], y=y_heat, name=f"Heating Z{i+1} (Top)", legend="legend2", line=dict(width=1.5)), row=2, col=1)

        # Heating Zone 8-14: Bottom (เส้นประ)
        for i in range(7, 14):
            ch_name = f'CH_{heat_start_idx + i}'
            if ch_name in df.columns:
                y_heat = scale_data(df[ch_name], 580.0, 650.0)
                fig.add_trace(go.Scatter(x=df['DateTime'], y=y_heat, name=f"Heating Z{i+1} (Bottom)", legend="legend2", line=dict(width=1.5, dash='dash')), row=2, col=1)

        # ----------------------------------------------------
        # กล่องที่ 3: Oxygen ppm O2 (สเกลตามจริง 0 - 200) & N2 Flow (แกนขวาออโต้สเกล)
        # ----------------------------------------------------
        if 'CH_3' in df.columns:
            y_o2 = scale_data(df['CH_3'], 0.0, 200.0)
            fig.add_trace(go.Scatter(
                x=df['DateTime'], y=y_o2, name="Oxygen (ppm O2)", legend="legend3",
                line=dict(color='#33FF57', width=2)
            ), row=3, col=1, secondary_y=False)

        if 'CH_4' in df.columns:
            fig.add_trace(go.Scatter(
                x=df['DateTime'], y=df['CH_4'], name="N2 Flow (h3/h)", legend="legend3",
                line=dict(color='#3357FF', width=2)
            ), row=3, col=1, secondary_y=True)

        # ----------------------------------------------------
        # กล่องที่ 4: Dew Point (สเกลตามจริง 10 ถึง -100 °C)
        # ----------------------------------------------------
        if 'CH_23' in df.columns:
            y_dew = scale_data(df['CH_23'], -100.0, 10.0)
            fig.add_trace(go.Scatter(x=df['DateTime'], y=y_dew, name="Dew Point", legend="legend4", line=dict(color='#E333FF', width=2, dash='dot')), row=4, col=1)

        # 3. ดีไซน์หน้าต่าง Layout แยกระดับสเกลช่วง และจัดสรร Legend Box แยกประจำกล่องย่อย
        fig.update_layout(
            template="plotly_dark",
            height=950,
            hovermode="x unified",
            title_text="Yokogawa Process Analyzer Dashboard (Industrial Precision Mode)",
            
            # ประกาศและคัดแยก Legend Box ทั้ง 4 ชุดให้อยู่ประจำตำแหน่งกล่องย่อยของตัวเอง
            legend1=dict(traceorder="normal", x=1.02, y=0.92, bgcolor="rgba(0,0,0,0)"),
            legend2=dict(traceorder="normal", x=1.02, y=0.68, bgcolor="rgba(0,0,0,0)"),
            legend3=dict(traceorder="normal", x=1.02, y=0.42, bgcolor="rgba(0,0,0,0)"),
            legend4=dict(traceorder="normal", x=1.02, y=0.15, bgcolor="rgba(0,0,0,0)")
        )
        
        # ปรับล็อกกรอบสเกลสูงสุด-ต่ำสุดของแกน Y ตามข้อมูลจริงจากวิศวกรโรงงาน
        fig.update_yaxes(title_text="Dryer Temp (°C)", range=[180, 420], row=1, col=1)
        fig.update_yaxes(title_text="Heating Temp (°C)", range=[550, 680], row=2, col=1)
        
        fig.update_yaxes(title_text="Oxygen (ppm O2)", color="#33FF57", range=[-10, 220], row=3, col=1, secondary_y=False)
        fig.update_yaxes(title_text="N2 Flow (h3/h)", color="#3357FF", autorange=True, row=3, col=1, secondary_y=True)
        
        # ปรับขอบเขตแกน Dew Point ให้ทอดตัวลงต่ำตามค่าติดลบจริง (10 ถึง -100)
        fig.update_yaxes(title_text="Dew Point (°C)", range=[-110, 20], row=4, col=1)
        fig.update_xaxes(title_text="Date & Time (Process Timeline)", row=4, col=1)

        st.plotly_chart(fig, use_container_width=True)
        
    else:
        st.error("❌ ชุดตัวเลขในไฟล์ดิบสั้นเกินไป ไม่เพียงพอต่อการจัดวางโครงสร้าง 23 ช่องสัญญาณ")
else:
    st.info("💡 กรุณาอัปโหลดไฟล์บันทึกสัญญาณ (.DAD) เพื่อพล็อตกราฟสเกลปรับปรุงใหม่")
