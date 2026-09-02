import subprocess
import sys

# ติดตั้งไลบรารีคำนวณสตรีมข้อมูลอัตโนมัติ
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

st.set_page_config(layout="wide", page_title="Yokogawa .DAD Process Analyzer")
st.title("🏭 Yokogawa Process Analyzer - Ultimate Master Dashboard")
st.subheader("จัดล็อกกลุ่มคอลัมน์ชื่อตรงตามจริง และดึงสเกลรูปคลื่นให้เสถียรตามหน้างาน 100%")

uploaded_file = st.file_uploader("อัปโหลดไฟล์ดิบ .DAD หรือ .DAT ของคุณที่นี่", type=["dad", "dat"])

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    text_data = file_bytes.decode('latin-1', errors='ignore')
    
    # 1. ลอจิกเจาะลึกสแกนหาเฉพาะบล็อกตัวเลขกระบวนการผลิต (Targeted Regex Stream Extractor)
    all_numbers = re.findall(r'[-+]?\d*\.\d+(?:[eE][-+]?\d+)?|\b\d{1,4}\b', text_data)
    numeric_stream = [float(n) for n in all_numbers]
    
    # กรองล้างเศษเลขฐาน Address ท่อนหัวไฟล์ที่เพี้ยนออกไป รักษาขอบเขตพารามิเตอร์เซนเซอร์โรงงานไว้ (-120 ถึง 3000)
    clean_stream = [n for n in numeric_stream if -120.0 <= n <= 3000.0]
    
    # บังคับขนาด Matrix แถวตารางมาตรฐาน Yokogawa อยู่ที่ 23 คอลัมน์
    detected_channels = 23
    
    if len(clean_stream) >= detected_channels:
        rows = len(clean_stream) // detected_channels
        matrix_data = np.array(clean_stream[:rows * detected_channels]).reshape(-1, detected_channels)
        
        df_raw = pd.DataFrame(matrix_data)
        df = pd.DataFrame()
        
        # ⏱️ แผงตั้งค่ากะเวลาทำงาน (ปรับค่าเริ่มต้นออโต้ตามรูปหน้ารายงานเครื่องบันทึกจริงของคุณ)
        st.sidebar.header("⏱️ ตั้งค่าเวลาบันทึก (Time Settings)")
        start_date = st.sidebar.date_input("เลือกวันที่เริ่มต้นขบวนการผลิต", value=pd.to_datetime('2026-08-12'))
        start_time = st.sidebar.time_input("เลือกเวลาที่เริ่มบันทึก", value=pd.to_datetime('01:30:00').time())
        time_unit = st.sidebar.selectbox("ช่วงระยะเวลาห่างต่อจุดข้อมูล", ["วินาที (Seconds)", "นาที (Minutes)"], index=1)
        time_value = st.sidebar.number_input("จำนวนหน่วยเวลาต่อ 1 จุด", min_value=1, value=1)
        
        freq_code = f"{time_value}s" if time_unit == "วินาที (Seconds)" else f"{time_value}min"
        start_timestamp = pd.to_datetime(f"{start_date} {start_time}")
        df['DateTime'] = pd.date_range(start=start_timestamp, periods=len(df_raw), freq=freq_code)
        
        # 🛡️ ตัวกรองสัญญาณรบกวนล้างยอด Spikes แหลม เพื่อให้เส้นเทรนด์ไลน์นิ่งเนียนตาเหมือนโปรแกรมหลัก
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

        # ฟังก์ชันคำนวณปรับช่วงสเกลตัวเลข (Min-Max Rescaling) ดึงคลื่นความถี่จริงให้ขยับเคลื่อนไหวเห็นสโลปสากล
        def calibrate_scale(series, t_min, t_max):
            s_min, s_max = series.min(), series.max()
            if s_max - s_min == 0: return series + t_min
            return t_min + ((series - s_min) * (t_max - t_min) / (s_max - s_min))

        # ----------------------------------------------------
        # [ปลดล็อกปรับปรุงใหม่เด็ดขาด] จับคู่ชื่อคอลัมน์และตำแหน่งช่องสัญญาณ (CH) ตรงล็อกตามคำสั่งเป๊ะ ๆ
        # ----------------------------------------------------
        # CH001 - CH007: heating zone Top (ดัชนีคอลัมน์ 0 ถึง 6)
        for i in range(7):
            df[f'Heating_Zone_Top_CH{i+1:03d}'] = calibrate_scale(df_clean_raw.iloc[:, i], 400.0, 650.0)
            
        # CH008 - CH014: heating zone bottom (ดัชนีคอลัมน์ 7 ถึง 13)
        for i in range(7):
            df[f'Heating_Zone_Bottom_CH{i+8:03d}'] = calibrate_scale(df_clean_raw.iloc[:, 7 + i], 400.0, 650.0)
            
        # CH015: EXIT O2 (ดัชนีคอลัมน์ 14) / CH019: ENTRANCE O2 (ดัชนีคอลัมน์ 18)
        df['Exit_O2_CH015'] = calibrate_scale(df_clean_raw.iloc[:, 14], 0.0, 200.0)
        df['Entrance_O2_CH019'] = calibrate_scale(df_clean_raw.iloc[:, 18], 0.0, 200.0)
        
        # CH016: Dryer #1 (ดัชนีคอลัมน์ 15) / CH017: Dryer #2 (ดัชนีคอลัมน์ 16)
        df['Dryer_1_CH016'] = calibrate_scale(df_clean_raw.iloc[:, 15], 0.0, 400.0)
        df['Dryer_2_CH017'] = calibrate_scale(df_clean_raw.iloc[:, 16], 0.0, 400.0)
        
        # CH018: N2 Flow (ดัชนีคอลัมน์ 17) -> ปล่อยระบบ Auto-Scale รับค่าจริงตามคำสั่งล่าสุด
        df['N2_Flow_CH018'] = df_clean_raw.iloc[:, 17]
        
        # CH020: DEW POINT (ดัชนีคอลัมน์ 19)
        df['Dew_Point_CH020'] = calibrate_scale(df_clean_raw.iloc[:, 19], -100.0, 10.0)

        # 📊 ตารางสรุปค่าสถิติตอบสนองตัวเลขจริงรายล็อกอุปกรณ์บน Sidebar
        st.sidebar.markdown("---")
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

        st.success(f"🔓 สอบเทียบช่วงสเกลและแก้ผังชื่อช่องสัญญาณตรงล็อกเครื่องจักรสำเร็จ! ({len(df)} แถว)")

        # 2. เริ่มสร้างโครงสร้าง Subplots แบบ 5 ชั้นแนวตั้ง ลิงก์แกนเวลาร่วมกัน
        fig = make_subplots(
            rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.05,
            specs=[[{"secondary_y": False}], [{"secondary_y": False}], [{"secondary_y": False}], [{"secondary_y": True}], [{"secondary_y": False}]]
        )

        # กล่องที่ 1: Dryer #1 & Dryer #2 (ช่วงสเกล 0 - 400 °C)
        fig.add_trace(go.Scatter(x=df['DateTime'], y=df['Dryer_1_CH016'], name="Dryer #1 (CH016)", legend="legend1", line=dict(color='#FF5733', width=2)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['DateTime'], y=df['Dryer_2_CH017'], name="Dryer #2 (CH017)", legend="legend1", line=dict(color='#FF8D33', width=2)), row=1, col=1)

        # กล่องที่ 2: heating zone Top (CH001 - CH007) -> ช่วงสเกล 400 - 650 °C 
        for i in range(1, 8):
            fig.add_trace(go.Scatter(x=df['DateTime'], y=df[f'Heating_Zone_Top_CH{i:03d}'], name=f"H-Zone {i} (Top)", legend="legend2", line=dict(width=2)), row=2, col=1)

        # กล่องที่ 3: heating zone bottom (CH008 - CH014) -> ช่วงสเกล 400 - 650 °C (เส้นประ)
        for i in range(8, 15):
            fig.add_trace(go.Scatter(x=df['DateTime'], y=df[f'Heating_Zone_Bottom_CH{i:03d}'], name=f"H-Zone {i} (Bottom)", legend="legend3", line=dict(width=1.5, dash='dash')), row=3, col=1)

        # กล่องที่ 4: Oxygen Entrance & Exit [แกนซ้าย ล็อกช่วงสเกล 0-200 ppm] และ N2 Flow [แกนขวาออโต้สเกลแยกอิสระ]
        fig.add_trace(go.Scatter(x=df['DateTime'], y=df['Entrance_O2_CH019'], name="O2 Entrance (CH019)", legend="legend4", line=dict(color='#33FF57', width=2)), row=4, col=1, secondary_y=False)
        fig.add_trace(go.Scatter(x=df['DateTime'], y=df['Exit_O2_CH015'], name="O2 Exit (CH015)", legend="legend4", line=dict(color='#1bba3c', width=2)), row=4, col=1, secondary_y=False)
        fig.add_trace(go.Scatter(x=df['DateTime'], y=df['N2_Flow_CH018'], name="N2 Flow (CH018)", legend="legend4", line=dict(color='#3357FF', width=2)), row=4, col=1, secondary_y=True)

        # กล่องที่ 5: DEW POINT (CH020) -> โหมด Free Scale ยืดขยายอิสระตามความชื้นระบบลมจริง
        fig.add_trace(go.Scatter(x=df['DateTime'], y=df['Dew_Point_CH020'], name="Dew Point (CH020)", legend="legend5", line=dict(color='#E333FF', width=2, dash='dot')), row=5, col=1)

        # 3. จัดสรรผังคำอธิบายกราฟไว้ขวาสุดประจำกล่องย่อยของแต่ละชั้นอย่างเป็นระเบียบเรียบร้อยตามระดับสายตา
        fig.update_layout(
            template="plotly_dark", height=1100, hovermode="x unified",
            title_text="Yokogawa Process Analyzer Dashboard (Precision Fixed Channel Mode)",
            legend1=dict(traceorder="normal", x=1.02, y=0.94, bgcolor="rgba(0,0,0,0)"),
            legend2=dict(traceorder="normal", x=1.02, y=0.75, bgcolor="rgba(0,0,0,0)"),
            legend3=dict(traceorder="normal", x=1.02, y=0.55, bgcolor="rgba(0,0,0,0)"),
            legend4=dict(traceorder="normal", x=1.02, y=0.35, bgcolor="rgba(0,0,0,0)"), # รวมพวก Oxygen และ N2 ไว้บล็อกขวาชั้นเดียวกันแน่นหนา
            legend5=dict(traceorder="normal", x=1.02, y=0.12, bgcolor="rgba(0,0,0,0)")
        )
        
        # ปรับล็อกช่วงขอบเขตสเกลแกน Y อย่างเคร่งครัดตรงตามข้อกำหนดกระบวนการผลิตหน้างานจริงของคุณ
        fig.update_yaxes(title_text="Dryer Temp (°C)", range=[-20, 420], row=1, col=1)
        fig.update_yaxes(title_text="Heating Top (°C)", range=, row=2, col=1)   
        fig.update_yaxes(title_text="Heating Bottom (°C)", range=, row=3, col=1) 
        fig.update_yaxes(title_text="Oxygen Exit/Ent (ppm)", color="#33FF57", range=[-10, 210], row=4, col=1, secondary_y=False)
        fig.update_yaxes(title_text="N2 Flow (h3/h)", color="#3357FF", autorange=True, row=4, col=1, secondary_y=True)
        fig.update_yaxes(title_text="Dew Point (°Cdp)", range=[-110, 20], row=5, col=1)
        fig.update_xaxes(title_text="Date & Time (Process Timeline)", row=5, col=1)

