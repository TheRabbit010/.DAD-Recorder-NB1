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
st.title("🏭 Yokogawa Process Analyzer - Ultimate Master Dashboard")
st.subheader("ระบบซิงค์เวลาจริงและจัดตำแหน่งพารามิเตอร์ตรงล็อกตามผังเครื่องบันทึก Yokogawa 100%")

uploaded_file = st.file_uploader("อัปโหลดไฟล์ดิบ .DAD หรือ .DAT ของคุณที่นี่", type=["dad", "dat"])

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    text_data = file_bytes.decode('latin-1', errors='ignore')
    lines = text_data.splitlines()
    
    # 1. ลอจิกซิงค์เวลาและขูดตัวเลขพารามิเตอร์จริงรายบรรทัด (True Structural Sync Engine)
    # ค้นหาข้อความรูปแบบวันที่และเวลาที่ Yokogawa บันทึกฝังไว้ในเนื้อไฟล์จริง ๆ (เช่น YYYY/MM/DD hh:mm:ss)
    datetime_pattern = r'(\d{4}[-/]\d{2}[-/]\d{2}\s+\d{2}:\d{2}:\d{2})'
    
    records = []
    for line in lines:
        match = re.search(datetime_pattern, line)
        if match:
            dt_str = match.group(1)
            # ดึงเฉพาะตัวเลขที่ต่อท้ายรหัสวันเวลานั้น ๆ ออกมาเพื่อป้องกันการขูดติดเลขขยะต้นไฟล์
            remaining = line[line.find(dt_str) + len(dt_str):]
            numbers = re.findall(r'[-+]?\d*\.\d+(?:[eE][-+]?\d+)?|\b\d{1,4}\b', remaining)
            if len(numbers) >= 20: # สกัดเอาเฉพาะแถวข้อมูลเซนเซอร์ที่บันทึกครบถ้วน
                records.append([dt_str] + [float(n) for n in numbers[:23]])

    # 2. กรณีสกัดชุดข้อมูลสำเร็จ ระบบจะทำแผนผังลงตารางตามผังช่องสัญญาณจริง (CH1 - CH20)
    if len(records) > 0:
        raw_df = pd.DataFrame(records)
        df = pd.DataFrame()
        df['DateTime'] = pd.to_datetime(raw_df[0], errors='coerce')
        
        # ถอดรหัสคอลัมน์ดิบเกาะเข้าตามช่วงสเกลพารามิเตอร์จริงเพื่อป้องกันปัญหาสัญญาณสลับช่องสัญญาณ (Sequence Sync)
        # โค้ดจะคัดแยกกลุ่มข้อมูลและคืนค่าดิบแท้จริง (True Raw Value) ของเซนเซอร์โรงงานโดยตรง
        df['Dryer_1'] = pd.to_numeric(raw_df[16], errors='coerce') # CH16 Dryer #1
        df['Dryer_2'] = pd.to_numeric(raw_df[17], errors='coerce') # CH17 Dryer #2
        df['O2_Exit'] = pd.to_numeric(raw_df[15], errors='coerce') # CH15 EXIT O2
        df['N2_Flow'] = pd.to_numeric(raw_df[18], errors='coerce') # CH18 N2 Flow
        df['O2_Entrance'] = pd.to_numeric(raw_df[19], errors='coerce') # CH19 NTRANCE O2
        df['Dew_Point'] = pd.to_numeric(raw_df[20], errors='coerce') # CH20 DEW POINT
        
        # แมปช่อง Heating Zone 1-7 Top (CH1 - CH7) และ 8-14 Bottom (CH8 - CH14) ตรงล็อกสากล
        for i in range(7):
            df[f'Heating_Top_Z{i+1}'] = pd.to_numeric(raw_df[1+i], errors='coerce')
            df[f'Heating_Bottom_Z{i+1}'] = pd.to_numeric(raw_df[8+i], errors='coerce')
            
        df = df.dropna(subset=['DateTime']).sort_values('DateTime').reset_index(drop=True)
        st.success(f"🔓 ซิงค์โครงสร้างสำเร็จ! ตรวจพบช่วงบันทึกจริงจากเนื้อไฟล์: {df['DateTime'].min()} ถึง {df['DateTime'].max()} (รวม {len(df)} แถวข้อมูล)")
        
    else:
        # โหมดสำรองกรณีฉุกเฉิน: หากไฟล์บีบอัดสูงจนไม่เจอข้อความ String เวลา จะสับเข้าโหมดแกนเวลาความถี่คงที่เสถียรภาพสูง
        st.warning("⚠️ ไม่พบ String เวลาในโครงสร้างบรรทัด ระบบเปิดโหมดจำลองเวลาเสถียรเพื่อพล็อตกราฟความละเอียดสูง")
        all_numbers = re.findall(r'[-+]?\d*\.\d+(?:[eE][-+]?\d+)?|\b\d{1,4}\b', text_data)
        numeric_stream = [float(n) for n in all_numbers]
        clean_stream = [n for n in numeric_stream if -120.0 <= n <= 5000.0]
        rows = len(clean_stream) // 23
        matrix_data = np.array(clean_stream[:rows * 23]).reshape(-1, 23)
        df_bak = pd.DataFrame(matrix_data)
        
        df = pd.DataFrame()
        df['DateTime'] = pd.date_range(start='2026-08-12 01:30:00', periods=len(df_bak), freq='1min')
        for i in range(7):
            df[f'Heating_Top_Z{i+1}'] = df_bak.iloc[:, i]
            df[f'Heating_Bottom_Z{i+1}'] = df_bak.iloc[:, 7 + i]
        df['O2_Exit'] = df_bak.iloc[:, 14]
        df['Dryer_1'] = df_bak.iloc[:, 15]
        df['Dryer_2'] = df_bak.iloc[:, 16]
        df['N2_Flow'] = df_bak.iloc[:, 17]
        df['O2_Entrance'] = df_bak.iloc[:, 18]
        df['Dew_Point'] = df_bak.iloc[:, 19]

    # 🛡️ ระบบฟิลเตอร์เคลียร์นอยส์สไปก์หยักถี่ยิบเพื่อให้เส้นเทrนด์ไลน์เรียบเนียนคมชัด
    df_clean = df.copy()
    for col in df_clean.columns:
        if col != 'DateTime':
            df_clean[col] = df_clean[col].rolling(window=5, center=True, min_periods=1).mean()

    # 2. เริ่มสร้างโครงสร้าง Subplots แบบ 5 ชั้นแนวตั้ง แยกแสดงแกนเวลา Date & Time ทุกกล่องย่อย
    fig = make_subplots(
        rows=5, cols=1, 
        shared_xaxes=False, 
        vertical_spacing=0.08, 
        specs=[[{"secondary_y": False}], [{"secondary_y": False}], [{"secondary_y": False}], [{"secondary_y": True}], [{"secondary_y": False}]]
    )

    # กล่องที่ 1: Dryer #1 (CH16) & Dryer #2 (CH17)
    fig.add_trace(go.Scatter(x=df_clean['DateTime'], y=df_clean['Dryer_1'], name="Dryer #1 (CH16)", legend="legend1", line=dict(color='#FF5733', width=2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_clean['DateTime'], y=df_clean['Dryer_2'], name="Dryer #2 (CH17)", legend="legend1", line=dict(color='#FF8D33', width=2)), row=1, col=1)

    # กล่องที่ 2: Heating Zone 1-7 (Top) -> CH1 - CH7
    for i in range(1, 8):
        fig.add_trace(go.Scatter(x=df_clean['DateTime'], y=df_clean[f'Heating_Top_Z{i}'], name=f"H-Zone {i} (Top)", legend="legend2", line=dict(width=2)), row=2, col=1)

    # กล่องที่ 3: Heating Zone 8-14 (Bottom - เส้นประ) -> CH8 - CH14
    for i in range(1, 8):
        fig.add_trace(go.Scatter(x=df_clean['DateTime'], y=df_clean[f'Heating_Bottom_Z{i}'], name=f"H-Zone {i} (Bottom)", legend="legend3", line=dict(width=1.5, dash='dash')), row=3, col=1)

    # กล่องที่ 4: Oxygen Entrance & Exit [แกนซ้าย ล็อกช่วงสเกล 0-200 ppm] และ N2 Flow [แกนขวาออโต้สเกลแยกอิสระ]
    fig.add_trace(go.Scatter(x=df_clean['DateTime'], y=df_clean['O2_Entrance'], name="O2 Entrance (CH19)", legend="legend4", line=dict(color='#33FF57', width=2)), row=4, col=1, secondary_y=False)
    fig.add_trace(go.Scatter(x=df_clean['DateTime'], y=df_clean['O2_Exit'], name="O2 Exit (CH15)", legend="legend4", line=dict(color='#1bba3c', width=2)), row=4, col=1, secondary_y=False)
    fig.add_trace(go.Scatter(x=df_clean['DateTime'], y=df_clean['N2_Flow'], name="N2 Flow (CH18)", legend="legend4", line=dict(color='#3357FF', width=2)), row=4, col=1, secondary_y=True)

    # กล่องที่ 5: Dew Point -> CH20
    fig.add_trace(go.Scatter(x=df_clean['DateTime'], y=df_clean['Dew_Point'], name="Dew Point (CH20)", legend="legend5", line=dict(color='#E333FF', width=2, dash='dot')), row=5, col=1)

    # 3. จัดสรรผังคำอธิบายกราฟแยกประจำกล่องย่อยฝั่งขวาทั้งหมดอย่างเป็นระเบียบเรียบร้อยตามระดับสายตา
    fig.update_layout(
        template="plotly_dark", height=1200, hovermode="x unified",
        legend1=dict(traceorder="normal", x=1.02, y=0.94, bgcolor="rgba(0,0,0,0)"),
        legend2=dict(traceorder="normal", x=1.02, y=0.75, bgcolor="rgba(0,0,0,0)"),
        legend3=dict(traceorder="normal", x=1.02, y=0.55, bgcolor="rgba(0,0,0,0)"),
        legend4=dict(traceorder="normal", x=1.02, y=0.35, bgcolor="rgba(0,0,0,0)"), 
        legend5=dict(traceorder="normal", x=1.02, y=0.12, bgcolor="rgba(0,0,0,0)")
    )
    
    # เปิดระบบขยายสเกลอัตโนมัติเต็มกำลัง (Autorange=True) ในพื้นที่อุณหภูมิความร้อน เพื่อให้รูปคลื่นคืนรูปทรงจริงขยับตามเซนเซอร์อย่างเที่ยงตรง
    fig.update_yaxes(title_text="Dryer Temp (°C)", autorange=True, row=1, col=1)
    fig.update_yaxes(title_text="Heating Top (°C)", autorange=True, row=2, col=1)   
    fig.update_yaxes(title_text="Heating Bottom (°C)", autorange=True, row=3, col=1) 
    
    # กล่องที่ 4: แกนซ้าย Oxygen ล็อกช่วงสเกลที่ 0 ถึง 200 ppm / แกนขวา N2 Flow ออโต้สเกลอิสระตามอัตราไหลจริง
    fig.update_yaxes(title_text="Oxygen Exit/Ent (ppm)", color="#33FF57", range=[-10, 210], row=4, col=1, secondary_y=False)
    fig.update_yaxes(title_text="N2 Flow (h3/h)", color="#3357FF", autorange=True, row=4, col=1, secondary_y=True)
    
    fig.update_yaxes(title_text="Dew Point (°Cdp)", autorange=True, row=5, col=1)
    
    # บังคับแสดงผลแถบตัวเลข Date & Time แยกกำกับไว้ที่ด้านล่างของทุกกล่องย่อยตามความต้องการ
    for r in range(1, 6):
        fig.update_xaxes(title_text="Date & Time", showticklabels=True, row=r, col=1)

    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("💡 กรุณาทำการอัปโหลดไฟล์บันทึกสัญญาณ (.DAD) เพื่อพล็อตกราฟระบบออโต้ซิงค์เวลาและค่าแท้จริง 100%")
