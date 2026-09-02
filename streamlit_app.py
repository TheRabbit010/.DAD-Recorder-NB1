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
import numpy as np

st.set_page_config(layout="wide")
st.title("🏭 Factory Process Master Dashboard - Line Harvester Engine")
st.subheader("พล็อตกราฟ 5 ชั้น ปลดล็อกและจัดคอลัมน์จากไฟล์ Yokogawa .DAD อัตโนมัติ")

uploaded_file = st.file_uploader("อัปโหลดไฟล์ดิบ .DAD ของคุณที่นี่", type=["dad", "dat"])

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    text_data = file_bytes.decode('latin-1', errors='ignore')
    
    # 1. ลอจิกควานหาข้อความตัวเลขรายบรรทัดแบบยืดหยุ่นสูง (Universal Token Harvester)
    lines = text_data.splitlines()
    all_numeric_rows = []
    
    for line in lines:
        tokens = line.split()
        row_values = []
        for token in tokens:
            try:
                # ทำความสะอาดตัวหนังสือแปลกปลอมและกรองให้เหลือเฉพาะทศนิยม/จำนวนเต็ม
                cleaned = ''.join(c for c in token if c.isdigit() or c in '.-+eE')
                if cleaned:
                    row_values.append(float(cleaned))
            except ValueError:
                continue
        # บันทึกเฉพาะบรรทัดที่มีพารามิเตอร์การวัดซ่อนอยู่ (มีตัวเลขอย่างน้อย 1 ช่องขึ้นไป)
        if len(row_values) > 0:
            all_numeric_rows.append(row_values)

    if len(all_numeric_rows) > 5:
        # หาจำนวนช่องสัญญาณจริงจากโครงสร้างแถวส่วนใหญ่ในไฟล์
        detected_channels = max(len(r) for r in all_numeric_rows)
        
        # ปรับความยาวของทุกแถวให้เท่ากันเพื่อไม่ให้เมทริกซ์แตก (Padding Logic)
        normalized_data = []
        for r in all_numeric_rows:
            if len(r) < detected_channels:
                r = r + [np.nan] * (detected_channels - len(r))
            normalized_data.append(r[:detected_channels])
            
        df_raw = pd.DataFrame(normalized_data)
        
        # กรองล้างแถวขยะส่วนหัวที่เป็นเลขที่อยู่ Address ทิ้ง
        df_raw = df_raw.dropna(thresh=min(5, detected_channels)).reset_index(drop=True)
        df = pd.DataFrame()
        
        # ⏱️ แถบตั้งค่าเวลาทำงานด้านซ้ายมือ (Sidebar)
        st.sidebar.header("⏱️ ตั้งค่าเวลาบันทึก (Time Settings)")
        start_date = st.sidebar.date_input("เลือกวันที่เริ่มต้นขบวนการผลิต", value=pd.to_datetime('2026-08-12'))
        start_time = st.sidebar.time_input("เลือกเวลาที่เริ่มบันทึก", value=pd.to_datetime('01:30:00').time())
        time_unit = st.sidebar.selectbox("ช่วงระยะเวลาห่างต่อจุดข้อมูล", ["วินาที (Seconds)", "นาที (Minutes)"], index=1)
        time_value = st.sidebar.number_input("จำนวนหน่วยเวลาต่อ 1 จุด", min_value=1, value=1)
        
        freq_code = f"{time_value}s" if time_unit == "วินาที (Seconds)" else f"{time_value}min"
        start_timestamp = pd.to_datetime(f"{start_date} {start_time}")
        df['DateTime'] = pd.date_range(start=start_timestamp, periods=len(df_raw), freq=freq_code)
        
        # 🛡️ ระบบฟิลเตอร์เคลียร์นอยส์สไปก์และลดสัญญาณรบกวน (Moving Average)
        st.sidebar.markdown("---")
        st.sidebar.header("🛡️ ตัวกรองสัญญาณรบกวน (Signal Filter)")
        clean_spikes = st.sidebar.checkbox("เปิดระบบล้างยอดสวิงแหลม (Remove Spikes)", value=True)
        enable_smooth = st.sidebar.checkbox("เปิดโหมดเส้นเนียน (Smooth Curve)", value=True)
        window_size = st.sidebar.slider("ระดับความเรียบเนียน", min_value=3, max_value=15, value=5, step=2)
        
        df_clean_raw = df_raw.copy()
        if clean_spikes:
            for col in df_clean_raw.columns:
                df_clean_raw[col] = df_clean_raw[col].rolling(window=5, center=True, min_periods=1).median()
        if enable_smooth:
            for col in df_clean_raw.columns:
                df_clean_raw[col] = df_clean_raw[col].rolling(window=window_size, center=True, min_periods=1).mean()

        # ----------------------------------------------------
        # ล็อกตำแหน่งช่องสัญญาณตามข้อมูลจริงที่คุณระบุมา (CH1 - CH20)
        # ----------------------------------------------------
        # CH1 - CH7 คือ Heating Zone Top
        for i in range(min(7, detected_channels)):
            df[f'Heating_Top_Z{i+1}'] = df_clean_raw.iloc[:, i]
            
        # CH8 - CH14 คือ Heating Zone Bottom
        for i in range(min(7, max(0, detected_channels - 7))):
            df[f'Heating_Bottom_Z{i+1}'] = df_clean_raw.iloc[:, 7 + i]
            
        # CH15 คือ Exit O2 / CH16 Dryer #1 / CH17 Dryer #2 / CH18 N2 Flow / CH19 Entrance O2 / CH20 Dew Point
        if detected_channels > 14: df['O2_Exit'] = df_clean_raw.iloc[:, 14]
        if detected_channels > 15: df['Dryer_1'] = df_clean_raw.iloc[:, 15]
        if detected_channels > 16: df['Dryer_2'] = df_clean_raw.iloc[:, 16]
        if detected_channels > 17: df['N2_Flow'] = df_clean_raw.iloc[:, 17]
        if detected_channels > 18: df['O2_Entrance'] = df_clean_raw.iloc[:, 18]
        if detected_channels > 19: df['Dew_Point'] = df_clean_raw.iloc[:, 19]

        st.success(f"🔓 ถอดรหัสผ่านระบบสแกนบรรทัดสำเร็จ! กำลังสร้างแดชบอร์ดข้อมูล ({len(df)} แถวข้อมูล)")

        # 2. เริ่มสร้างโครงสร้าง Subplots แบบ 5 ชั้นแนวตั้ง ลิงก์แกนเวลาร่วมกัน
        fig = make_subplots(
            rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.05,
            specs=[[{"secondary_y": False}], [{"secondary_y": False}], [{"secondary_y": False}], [{"secondary_y": True}], [{"secondary_y": False}]]
        )

        # กล่องที่ 1: Dryer #1 & Dryer #2
        if 'Dryer_1' in df.columns:
            fig.add_trace(go.Scatter(x=df['DateTime'], y=df['Dryer_1'], name="Dryer #1", legend="legend1", line=dict(color='#FF5733', width=2)), row=1, col=1)
        if 'Dryer_2' in df.columns:
            fig.add_trace(go.Scatter(x=df['DateTime'], y=df['Dryer_2'], name="Dryer #2", legend="legend1", line=dict(color='#FF8D33', width=2)), row=1, col=1)

        # กล่องที่ 2: Heating Zone 1-7 (Top)
        for i in range(1, 8):
            if f'Heating_Top_Z{i}' in df.columns:
                fig.add_trace(go.Scatter(x=df['DateTime'], y=df[f'Heating_Top_Z{i}'], name=f"H-Zone {i} (Top)", legend="legend2", line=dict(width=2)), row=2, col=1)

        # กล่องที่ 3: Heating Zone 8-14 (Bottom - เส้นประ)
        for i in range(1, 8):
            if f'Heating_Bottom_Z{i}' in df.columns:
                fig.add_trace(go.Scatter(x=df['DateTime'], y=df[f'Heating_Bottom_Z{i}'], name=f"H-Zone {i} (Bottom)", legend="legend3", line=dict(width=1.5, dash='dash')), row=3, col=1)

        # กล่องที่ 4: Oxygen Entrance & Exit [แกนซ้าย] และ N2 Flow [แกนขวาออโต้สเกลแยกอิสระ]
        if 'O2_Entrance' in df.columns:
            fig.add_trace(go.Scatter(x=df['DateTime'], y=df['O2_Entrance'], name="O2 Entrance (ppm)", legend="legend4", line=dict(color='#33FF57', width=2)), row=4, col=1, secondary_y=False)
        if 'O2_Exit' in df.columns:
            fig.add_trace(go.Scatter(x=df['DateTime'], y=df['O2_Exit'], name="O2 Exit (ppm)", legend="legend4", line=dict(color='#1bba3c', width=2)), row=4, col=1, secondary_y=False)
        if 'N2_Flow' in df.columns:
            fig.add_trace(go.Scatter(x=df['DateTime'], y=df['N2_Flow'], name="N2 Flow (h3/h)", legend="legend4", line=dict(color='#3357FF', width=2)), row=4, col=1, secondary_y=True)

        # กล่องที่ 5: Dew Point
        if 'Dew_Point' in df.columns:
            fig.add_trace(go.Scatter(x=df['DateTime'], y=df['Dew_Point'], name="Dew Point", legend="legend5", line=dict(color='#E333FF', width=2, dash='dot')), row=5, col=1)

        # 3. จัดสรรผังคำอธิบายกราฟไว้ขวาสุดประจำกล่องย่อยของแต่ละชั้นอย่างเป็นระเบียบ
        fig.update_layout(
            template="plotly_dark", height=1100, hovermode="x unified",
            title_text="Yokogawa Process Analyzer Dashboard (Line Harvester Engine)",
            legend1=dict(traceorder="normal", x=1.02, y=0.94, bgcolor="rgba(0,0,0,0)"),
            legend2=dict(traceorder="normal", x=1.02, y=0.75, bgcolor="rgba(0,0,0,0)"),
            legend3=dict(traceorder="normal", x=1.02, y=0.55, bgcolor="rgba(0,0,0,0)"),
            legend4=dict(traceorder="normal", x=1.02, y=0.35, bgcolor="rgba(0,0,0,0)"), 
            legend5=dict(traceorder="normal", x=1.02, y=0.12, bgcolor="rgba(0,0,0,0)")
        )
        
        # ตั้งค่าระบบปรับสเกลอัตโนมัติ (Autorange=True) เพื่อคืนรูปความชันและไดนามิกที่ถูกต้อง 100%
        fig.update_yaxes(title_text="Dryer Temp (°C)", autorange=True, row=1, col=1)
        fig.update_yaxes(title_text="Heating Top (°C)", autorange=True, row=2, col=1)   
        fig.update_yaxes(title_text="Heating Bottom (°C)", autorange=True, row=3, col=1) 
        fig.update_yaxes(title_text="Oxygen Exit/Ent (ppm)", color="#33FF57", autorange=True, row=4, col=1, secondary_y=False)
        fig.update_yaxes(title_text="N2 Flow (h3/h)", color="#3357FF", autorange=True, row=4, col=1, secondary_y=True)
        fig.update_yaxes(title_text="Dew Point (°Cdp)", autorange=True, row=5, col=1)
        fig.update_xaxes(title_text="Date & Time (Process Timeline)", row=5, col=1)

        st.plotly_chart(fig, use_container_width=True)
        
    else:
        st.error("❌ ลอจิกไม่พบข้อมูลตัวเลขที่สามารถจัดสรรตารางได้ในไฟล์นี้")
else:
    st.info("💡 กรุณาอัปโหลดไฟล์บันทึกสัญญาณ (.DAD) เพื่อพล็อตกราฟตามผังเซนเซอร์เครื่องจักรจริง")
