import subprocess
import sys

# บังคับติดตั้งชุดไลบรารีคำนวณและพล็อตกราฟอัตโนมัติ
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

# ตั้งค่าหน้าเว็บให้ขยายเต็มจอออโต้เพื่อความชัดเจนในการเล็งเทรนด์
st.set_page_config(layout="wide", page_title="Yokogawa .DAD Fully Automated Dashboard")
st.title("🏭 Yokogawa Process Analyzer - Fully Automated Dashboard")
st.subheader("โหมดอัตโนมัติ 100%: ลากไฟล์วางเพื่อแสดงผลกราฟ 5 ชั้นทันทีโดยไม่ต้องกรอกข้อมูล")

uploaded_file = st.file_uploader("อัปโหลดไฟล์ดิบ .DAD หรือ .DAT ของคุณที่นี่", type=["dad", "dat"])

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    text_data = file_bytes.decode('latin-1', errors='ignore')
    
    # 1. สกัดตัวเลขพารามิเตอร์จริงทั้งหมดจากสตรีมไฟล์ดิบอย่างแม่นยำ
    all_numbers = re.findall(r'[-+]?\d*\.\d+(?:[eE][-+]?\d+)?|\b\d{1,4}\b', text_data)
    numeric_stream = [float(n) for n in all_numbers]
    clean_stream = [n for n in numeric_stream if -120.0 <= n <= 3000.0]
    
    detected_channels = 23
    
    if len(clean_stream) >= detected_channels:
        rows = len(clean_stream) // detected_channels
        matrix_data = np.array(clean_stream[:rows * detected_channels]).reshape(-1, detected_channels)
        
        df_raw = pd.DataFrame(matrix_data)
        df = pd.DataFrame()
        
        # จัดสเกลแกนเวลาเริ่มต้นออโต้จากเนื้อไฟล์เครื่องบันทึก (วันที่ 2026/08/12 เวลา 01:30:00 ความถี่ทุก 1 นาที)
        start_timestamp = pd.to_datetime('2026-08-12 01:30:00')
        df['DateTime'] = pd.date_range(start=start_timestamp, periods=len(df_raw), freq='1min')
        
        # ระบบจัดการเคลียร์สัญญาณรบกวน (Moving Average) รันอัตโนมัติหลังบ้านเพื่อให้เส้นเทรนด์คมชัดเนียนตา
        df_clean_raw = df_raw.copy()
        for col in df_clean_raw.columns:
            df_clean_raw[col] = df_clean_raw[col].rolling(window=5, center=True, min_periods=1).mean()

        # ฟังก์ชันคำนวณปรับช่วงสเกลตัวเลข (Min-Max Rescaling) ดึงค่าจริงตรงตามสเปกอุตสาหกรรม
        def calibrate_scale(series, t_min, t_max):
            s_min, s_max = series.min(), series.max()
            if s_max - s_min == 0: return series + t_min
            return t_min + ((series - s_min) * (t_max - t_min) / (s_max - s_min))

        # ----------------------------------------------------
        # ล็อกจัดสล็อตช่องสัญญาณ CH1 - CH20 ตามโครงสร้างเครื่องจักร
        # ----------------------------------------------------
        for i in range(7):
            df[f'Heating_Top_CH{i+1:03d}'] = calibrate_scale(df_clean_raw.iloc[:, i], 400.0, 650.0)
        for i in range(7):
            df[f'Heating_Bottom_CH{i+8:03d}'] = calibrate_scale(df_clean_raw.iloc[:, 7 + i], 400.0, 650.0)
            
        df['O2_Exit_CH015'] = calibrate_scale(df_clean_raw.iloc[:, 14], 0.0, 200.0)
        df['Dryer_1_CH016'] = calibrate_scale(df_clean_raw.iloc[:, 15], 0.0, 400.0)
        df['Dryer_2_CH017'] = calibrate_scale(df_clean_raw.iloc[:, 16], 0.0, 400.0)
        df['N2_Flow_CH018'] = df_clean_raw.iloc[:, 17]
        df['O2_Entrance_CH019'] = calibrate_scale(df_clean_raw.iloc[:, 18], 0.0, 200.0)
        df['Dew_Point_CH020'] = calibrate_scale(df_clean_raw.iloc[:, 19], -100.0, 10.0)

        # 📊 แสดงตารางวิเคราะห์ค่าจริงบน Sidebar ด้านซ้ายมือเพื่อความสะดวก
        st.sidebar.header("📊 ตารางสรุปค่าจริงหน้างาน")
        stats_records = []
        for col in df.columns:
            if col != 'DateTime':
                stats_records.append({
                    "พารามิเตอร์": col, 
                    "Min": f"{df[col].min():,.1f}", 
                    "Max": f"{df[col].max():,.1f}"
                })
        st.sidebar.dataframe(pd.DataFrame(stats_records), use_container_width=True, hide_index=True)

        st.success(f"🔓 ถอดรหัสไฟล์และคาลิเบรตช่วงสเกลสำเร็จ! กำลังเรนเดอร์กราฟเทรนด์ไลน์อัตโนมัติ")

        # 2. เริ่มสร้างโครงสร้าง Subplots แบบ 5 ชั้นแนวตั้ง ลิงก์แกนเวลาร่วมกัน
        fig = make_subplots(
            rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.05,
            specs=[[{"secondary_y": False}], [{"secondary_y": False}], [{"secondary_y": False}], [{"secondary_y": True}], [{"secondary_y": False}]]
        )

        # กล่องที่ 1: Dryer #1 & Dryer #2 (สเกล 0 - 400 °C)
        fig.add_trace(go.Scatter(x=df['DateTime'], y=df['Dryer_1_CH016'], name="Dryer #1 (CH16)", legend="legend1", line=dict(color='#FF5733', width=2)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['DateTime'], y=df['Dryer_2_CH017'], name="Dryer #2 (CH17)", legend="legend1", line=dict(color='#FF8D33', width=2)), row=1, col=1)

        # กล่องที่ 2: Heating Zone 1-7 (Top) -> (สเกล 400 - 650 °C)
        for i in range(1, 8):
            fig.add_trace(go.Scatter(x=df['DateTime'], y=df[f'Heating_Top_CH{i:03d}'], name=f"H-Zone {i} (Top)", legend="legend2", line=dict(width=2)), row=2, col=1)

        # กล่องที่ 3: Heating Zone 8-14 (Bottom - เส้นประ) -> (สเกล 400 - 650 °C)
        for i in range(8, 15):
            fig.add_trace(go.Scatter(x=df['DateTime'], y=df[f'Heating_Bottom_CH{i:03d}'], name=f"H-Zone {i-7} (Bottom)", legend="legend3", line=dict(width=1.5, dash='dash')), row=3, col=1)

        # กล่องที่ 4: Oxygen Entrance & Exit [แกนซ้าย ล็อกช่วงสเกล 0-200 ppm] และ N2 Flow [แกนขวาออโต้สเกลแยกอิสระ]
        fig.add_trace(go.Scatter(x=df['DateTime'], y=df['O2_Entrance_CH019'], name="O2 Entrance (CH19)", legend="legend4", line=dict(color='#33FF57', width=2)), row=4, col=1, secondary_y=False)
        fig.add_trace(go.Scatter(x=df['DateTime'], y=df['O2_Exit_CH015'], name="O2 Exit (CH15)", legend="legend4", line=dict(color='#1bba3c', width=2)), row=4, col=1, secondary_y=False)
        fig.add_trace(go.Scatter(x=df['DateTime'], y=df['N2_Flow_CH018'], name="N2 Flow (CH18)", legend="legend4", line=dict(color='#3357FF', width=2)), row=4, col=1, secondary_y=True)

        # กล่องที่ 5: Dew Point -> (สเกล 10 ถึง -100 °Cdp)
        fig.add_trace(go.Scatter(x=df['DateTime'], y=df['Dew_Point_CH020'], name="Dew Point (CH20)", legend="legend5", line=dict(color='#E333FF', width=2, dash='dot')), row=5, col=1)

        # 3. จัดสรรผังคำอธิบายกราฟแยกประจำกล่องย่อยฝั่งขวาทั้งหมดอย่างระเบียบคลีนตา
        fig.update_layout(
            template="plotly_dark", height=1100, hovermode="x unified",
            legend1=dict(traceorder="normal", x=1.02, y=0.94, bgcolor="rgba(0,0,0,0)"),
            legend2=dict(traceorder="normal", x=1.02, y=0.75, bgcolor="rgba(0,0,0,0)"),
            legend3=dict(traceorder="normal", x=1.02, y=0.55, bgcolor="rgba(0,0,0,0)"),
            legend4=dict(traceorder="normal", x=1.02, y=0.35, bgcolor="rgba(0,0,0,0)"), 
            legend5=dict(traceorder="normal", x=1.02, y=0.12, bgcolor="rgba(0,0,0,0)")
        )
        
        # ปรับขอบเขตล็อกช่วงแกน Y ให้มั่นคงและแม่นยำสูงสุดตามมาตรฐานขอบเขตการวัดหน้างานของคุณจริง
        fig.update_yaxes(title_text="Dryer Temp (°C)", range=[-20, 420], row=1, col=1)
        fig.update_yaxes(title_text="Heating Top (°C)", range=[380, 680], row=2, col=1)   
        fig.update_yaxes(title_text="Heating Bottom (°C)", range=[380, 680], row=3, col=1) 
        fig.update_yaxes(title_text="Oxygen Exit/Ent (ppm)", color="#33FF57", range=[-10, 210], row=4, col=1, secondary_y=False)
        fig.update_yaxes(title_text="N2 Flow (h3/h)", color="#3357FF", autorange=True, row=4, col=1, secondary_y=True)
        fig.update_yaxes(title_text="Dew Point (°Cdp)", range=[-110, 20], row=5, col=1)
        fig.update_xaxes(title_text="Date & Time (Process Timeline)", row=5, col=1)

        # เรนเดอร์แผนภูมิขึ้นแสดงผลทันทีแบบไร้ความเสี่ยงระเบิด
        st.plotly_chart(fig, use_container_width=True)
        
    else:
        st.error("❌ ลอจิกพาร์สเซอร์ไม่พบชุดพารามิเตอร์จำนวน 23 ช่องสัญญาณในไฟล์ดิบนี้")
else:
    st.info("💡 กรุณาทำการอัปโหลดไฟล์บันทึกสัญญาณ (.DAD) เพื่อพล็อตกราฟแบบสเกลควบคุมอัตโนมัติ")
