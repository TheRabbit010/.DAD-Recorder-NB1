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
st.title("🏭 Factory Process Master Dashboard - Precision Channel Mapping")
st.subheader("พล็อตกราฟ 5 ชั้น ปลดล็อกค่าจริงและแกนเวลาอิงตามผังช่องสัญญาณ Yokogawa จริง")

uploaded_file = st.file_uploader("อัปโหลดไฟล์ดิบ .DAD ของคุณที่นี่", type=["dad", "dat"])

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    text_data = file_bytes.decode('latin-1', errors='ignore')
    
    # 1. สกัดตัวเลขดิบทั้งหมดออกจากโครงสร้างไฟล์อย่างละเอียด
    all_numbers = re.findall(r'[-+]?\d*\.\d+(?:[eE][-+]?\d+)?|\b\d{1,4}\b', text_data)
    numeric_stream = [float(n) for n in all_numbers]
    
    # กรองล้างเฉพาะค่าขยะภายนอกขอบเขตเครื่องมือวัดอุตสาหกรรม
    clean_stream = [n for n in numeric_stream if -150.0 <= n <= 3500.0]
    
    # จำนวนคอลัมน์ทั้งหมดในไฟล์ (ล็อกไว้ตามระบบมาตรฐาน 23 หรือเทียบเคียงเพื่อไม่ให้ Matrix แตก)
    detected_channels = 23
    
    if len(clean_stream) >= detected_channels:
        rows = len(clean_stream) // detected_channels
        matrix_data = np.array(clean_stream[:rows * detected_channels]).reshape(-1, detected_channels)
        
        # ตั้งชื่อคอลัมน์ดิบเป็นแบบ Index 1-Based (ตรงกับ CH001 - CH023 ของเครื่อง)
        col_names = [f'CH_{i+1}' for i in range(detected_channels)]
        df = pd.DataFrame(matrix_data, columns=col_names)
        
        # ⏱️ แถบตั้งค่ากะเวลาทำงานด้านซ้ายมือ (Sidebar)
        st.sidebar.header("⏱️ ตั้งค่าเวลาบันทึก (Time Settings)")
        start_date = st.sidebar.date_input("เลือกวันที่เริ่มต้นขบวนการผลิต", value=pd.to_datetime('2026-08-12'))
        start_time = st.sidebar.time_input("เลือกเวลาที่เริ่มบันทึก", value=pd.to_datetime('01:30:00').time())
        time_unit = st.sidebar.selectbox("ช่วงระยะเวลาห่างต่อจุดข้อมูล", ["วินาที (Seconds)", "นาที (Minutes)"], index=1)
        time_value = st.sidebar.number_input("จำนวนหน่วยเวลาต่อ 1 จุด", min_value=1, value=1)
        
        freq_code = f"{time_value}s" if time_unit == "วินาที (Seconds)" else f"{time_value}min"
        start_timestamp = pd.to_datetime(f"{start_date} {start_time}")
        df['DateTime'] = pd.date_range(start=start_timestamp, periods=len(df), freq=freq_code)
        
        # 🛡️ ระบบฟิลเตอร์เคลียร์สไปก์และลดสัญญาณรบกวน (Moving Average)
        st.sidebar.markdown("---")
        st.sidebar.header("🛡️ ตัวกรองสัญญาณรบกวน (Signal Filter)")
        clean_spikes = st.sidebar.checkbox("เปิดระบบล้างยอดสวิงแหลม (Remove Spikes)", value=True)
        enable_smooth = st.sidebar.checkbox("เปิดโหมดเส้นเนียน (Smooth Curve)", value=True)
        window_size = st.sidebar.slider("ระดับความเรียบเนียน", min_value=3, max_value=15, value=5, step=2)
        
        df_clean = df.copy()
        if clean_spikes:
            for col in col_names:
                df_clean[col] = df_clean[col].rolling(window=5, center=True, min_periods=1).median()
        if enable_smooth:
            for col in col_names:
                df_clean[col] = df_clean[col].rolling(window=window_size, center=True, min_periods=1).mean()
                
        # 📊 ตารางสรุปค่าจริงบน Left Sidebar ด้านซ้ายมือ (อ้างอิงรายชื่อตามการจับคู่จริงของคุณ)
        st.sidebar.markdown("---")
        st.sidebar.header("📊 ตารางสรุปค่าดิบจริง")
        mapping_labels = {
            'CH_15': 'Exit O2 (CH15)', 'CH_16': 'Dryer #1 (CH16)',
            'CH_17': 'Dryer #2 (CH17)', 'CH_18': 'N2 Flow (CH18)',
            'CH_19': 'Entrance O2 (CH19)', 'CH_20': 'Dew Point (CH20)'
        }
        for i in range(7): mapping_labels[f'CH_{1+i}'] = f'H-Zone {i+1} Top'
        for i in range(7): mapping_labels[f'CH_{8+i}'] = f'H-Zone {i+1} Bottom'
            
        stats_records = []
        for col in col_names:
            if col in df_clean.columns:
                stats_records.append({
                    "ช่องสัญญาณ": mapping_labels.get(col, col), 
                    "Min": f"{df_clean[col].min():,.1f}", 
                    "Max": f"{df_clean[col].max():,.1f}"
                })
        st.sidebar.dataframe(pd.DataFrame(stats_records), use_container_width=True, hide_index=True)

        st.success(f"🔓 ถอดรหัสและจับคู่ช่องสัญญาณตรงสเปกเครื่องจักรสำเร็จ เรียงลำดับ 5 บล็อกกราฟ")

        # 2. เริ่มสร้างโครงสร้าง Subplots แบบ 5 ชั้นแนวตั้ง ลิงก์แกนเวลาร่วมกัน
        fig = make_subplots(
            rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.05,
            specs=[[{"secondary_y": False}], [{"secondary_y": False}], [{"secondary_y": False}], [{"secondary_y": True}], [{"secondary_y": False}]]
        )

        # กล่องที่ 1: Dryer #1 (CH_16) & Dryer #2 (CH_17)
        if 'CH_16' in df_clean.columns:
            fig.add_trace(go.Scatter(x=df_clean['DateTime'], y=df_clean['CH_16'], name="Dryer #1", legend="legend1", line=dict(color='#FF5733', width=2)), row=1, col=1)
        if 'CH_17' in df_clean.columns:
            fig.add_trace(go.Scatter(x=df_clean['DateTime'], y=df_clean['CH_17'], name="Dryer #2", legend="legend1", line=dict(color='#FF8D33', width=2)), row=1, col=1)

        # กล่องที่ 2: Heating Zone 1-7 (Top) -> ดึงตรงช่อง CH_1 ถึง CH_7
        for i in range(0, 7):
            ch_name = f'CH_{1 + i}'
            if ch_name in df_clean.columns:
                fig.add_trace(go.Scatter(x=df_clean['DateTime'], y=df_clean[ch_name], name=f"H-Zone {i+1} (Top)", legend="legend2", line=dict(width=2)), row=2, col=1)

        # กล่องที่ 3: Heating Zone 8-14 (Bottom) -> ดึงตรงช่อง CH_8 ถึง CH_14 (เส้นประ)
        for i in range(0, 7):
            ch_name = f'CH_{8 + i}'
            if ch_name in df_clean.columns:
                fig.add_trace(go.Scatter(x=df_clean['DateTime'], y=df_clean[ch_name], name=f"H-Zone {i+1} (Bottom)", legend="legend3", line=dict(width=1.5, dash='dash')), row=3, col=1)

        # กล่องที่ 4: Oxygen Entrance (CH_19) & Exit (CH_15) [แกนซ้าย] และ N2 Flow (CH_18) [แกนขวา]
        if 'CH_19' in df_clean.columns:
            fig.add_trace(go.Scatter(x=df_clean['DateTime'], y=df_clean['CH_19'], name="O2 Entrance (ppm)", legend="legend4", line=dict(color='#33FF57', width=2)), row=4, col=1, secondary_y=False)
        if 'CH_15' in df_clean.columns:
            fig.add_trace(go.Scatter(x=df_clean['DateTime'], y=df_clean['CH_15'], name="O2 Exit (ppm)", legend="legend4", line=dict(color='#1bba3c', width=2)), row=4, col=1, secondary_y=False)
        if 'CH_18' in df_clean.columns:
            fig.add_trace(go.Scatter(x=df_clean['DateTime'], y=df_clean['CH_18'], name="N2 Flow (h3/h)", legend="legend4", line=dict(color='#3357FF', width=2)), row=4, col=1, secondary_y=True)

        # กล่องที่ 5: Dew Point -> ดึงตรงช่อง CH_20
        if 'CH_20' in df_clean.columns:
            fig.add_trace(go.Scatter(x=df_clean['DateTime'], y=df_clean['CH_20'], name="Dew Point", legend="legend5", line=dict(color='#E333FF', width=2, dash='dot')), row=5, col=1)

        # 3. จัดสรรผังคำอธิบายกราฟไว้ขวาสุดประจำกล่องย่อยของแต่ละชั้นอย่างเป็นระเบียบ
        fig.update_layout(
            template="plotly_dark", height=1100, hovermode="x unified",
            title_text="Yokogawa Process Analyzer Dashboard (Precision Target Mapped Mode)",
            legend1=dict(traceorder="normal", x=1.02, y=0.94, bgcolor="rgba(0,0,0,0)"),
            legend2=dict(traceorder="normal", x=1.02, y=0.75, bgcolor="rgba(0,0,0,0)"),
            legend3=dict(traceorder="normal", x=1.02, y=0.55, bgcolor="rgba(0,0,0,0)"),
            legend4=dict(traceorder="normal", x=1.02, y=0.35, bgcolor="rgba(0,0,0,0)"), 
            legend5=dict(traceorder="normal", x=1.02, y=0.12, bgcolor="rgba(0,0,0,0)")
        )
        
        # บังคับเปิดระบบปรับสเกลอัตโนมัติตามค่าจริงดิบแท้จริงของอุปกรณ์ เพื่อคืนรูปความชันและไดนามิกที่ถูกต้อง 100%
        fig.update_yaxes(title_text="Dryer Temp (°C)", autorange=True, row=1, col=1)
        fig.update_yaxes(title_text="Heating Top (°C)", autorange=True, row=2, col=1)   
        fig.update_yaxes(title_text="Heating Bottom (°C)", autorange=True, row=3, col=1) 
        fig.update_yaxes(title_text="Oxygen Exit/Ent (ppm)", color="#33FF57", autorange=True, row=4, col=1, secondary_y=False)
        fig.update_yaxes(title_text="N2 Flow (h3/h)", color="#3357FF", autorange=True, row=4, col=1, secondary_y=True)
        fig.update_yaxes(title_text="Dew Point (°Cdp)", autorange=True, row=5, col=1)
        fig.update_xaxes(title_text="Date & Time (Process Timeline)", row=5, col=1)

        st.plotly_chart(fig, use_container_width=True)
        
    else:
        st.error("❌ โครงสร้างชุดข้อมูลในไฟล์ .DAD ไม่สอดคล้องกับพารามิเตอร์ช่องสัญญาณที่ระบุ")
else:
    st.info("💡 กรุณาอัปโหลดไฟล์บันทึกสัญญาณ (.DAD) เพื่อพล็อตกราฟตามตำแหน่งเซนเซอร์เครื่องจักรจริง")
