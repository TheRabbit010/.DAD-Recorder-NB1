import subprocess
import sys

# ติดตั้งไลบรารีวิเคราะห์ข้อมูลเชิงอุตสาหกรรมอัตโนมัติ
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
st.title("🏭 Yokogawa Process Master Dashboard - Structural Sync Mode")
st.subheader("ซิงค์แกนเวลาจริงและจัดตำแหน่งพารามิเตอร์ตามช่องสัญญาณเครื่องบันทึกจริง")

uploaded_file = st.file_uploader("อัปโหลดไฟล์ดิบ .DAD ของคุณที่นี่", type=["dad", "dat"])

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    
    # 1. ถอดรหัสไฟล์แบบควานหาข้อมูลโครงสร้าง (Structural Text Decoder)
    text_data = file_bytes.decode('latin-1', errors='ignore')
    lines = text_data.splitlines()
    
    # แพทเทิร์นค้นหาวันเวลาจริงที่ Yokogawa บันทึกฝังไว้ (เช่น 2026/09/02 10:15:30)
    datetime_pattern = r'(\d{4}[-/]\d{2}[-/]\d{2}\s+\d{2}:\d{2}:\d{2})'
    
    records = []
    for line in lines:
        match = re.search(datetime_pattern, line)
        if match:
            dt_str = match.group(1)
            # ดึงเฉพาะตัวเลขที่ต่อท้ายวันเวลานั้นๆ ออกมา
            remaining = line[line.find(dt_str) + len(dt_str):]
            numbers = re.findall(r'[-+]?\d*\.\d+(?:[eE][-+]?\d+)?|\b\d{1,4}\b', remaining)
            if len(numbers) >= 23: # สกัดเฉพาะแถวที่มีข้อมูลเซนเซอร์ครบถ้วนจริง
                records.append([dt_str] + [float(n) for n in numbers[:23]])

    # 2. กรณีสกัดผ่านบรรทัดตรงๆ สำเร็จ ระบบจะตั้งค่าแมปปิ้งตามผังเครื่องบันทึก Yokogawa
    if len(records) > 0:
        raw_df = pd.DataFrame(records)
        df = pd.DataFrame()
        df['DateTime'] = pd.to_datetime(raw_df[0], errors='coerce')
        
        # คาลิเบรตจับคู่ตำแหน่งเซนเซอร์ให้ตรงตามช่วงสเกลเพื่อแก้ปัญหาสัญญาณสลับช่อง (Sequence Sync)
        # โค้ดจะวิ่งไปค้นหาว่าคอลัมน์ดิบไหน มีช่วงตัวเลขตรงกับอุปกรณ์ตัวใดจริงหน้างาน
        used_indices = set()
        
        def find_best_channel(target_min, target_max):
            best_idx = None
            min_error = float('inf')
            for idx in range(1, 24):
                if idx in used_indices or idx >= len(raw_df.columns): continue
                vals = pd.to_numeric(raw_df[idx], errors='coerce').dropna()
                if len(vals) > 0:
                    # หาช่องที่ค่าเฉลี่ยหรือสัดส่วนข้อมูลส่วนใหญ่วิ่งอยู่ในขอบเขตอุปกรณ์นั้น
                    in_range_ratio = ((vals >= target_min) & (vals <= target_max)).sum() / len(vals)
                    if in_range_ratio > 0.4: # ถ้ายืนพื้นอยู่ในช่วงสเกลเกิน 40% ให้ล็อกช่องนี้ทันที
                        used_indices.add(idx)
                        return raw_df[idx]
            # หากหาตัวแมปไม่ได้ ให้หยิบค่าเริ่มต้นตามลำดับเพื่อความปลอดภัย
            for idx in range(1, 24):
                if idx not in used_indices and idx < len(raw_df.columns):
                    used_indices.add(idx)
                    return raw_df[idx]
            return pd.Series([0.0]*len(raw_df))

        # จัดสรรแมปคอลัมน์ใหม่ตามพฤติกรรมสเกลจริงของเซนเซอร์
        df['Dryer_1'] = find_best_channel(0.0, 400.0)
        df['Dryer_2'] = find_best_channel(0.0, 400.0)
        df['Oxygen_O2'] = find_best_channel(0.0, 200.0)
        df['N2_Flow'] = find_best_channel(0.0, 5000.0) # สเกลอัตราไหลปกติ
        
        # แมปช่อง Heating Zone 1-14 (ช่วง 400 - 650 'C)
        for i in range(14):
            df[f'Heat_Z{i+1}'] = find_best_channel(400.0, 650.0)
            
        # แมปช่อง Dew Point (ช่วง -100 ถึง 10 'Cdp)
        df['Dew_Point'] = find_best_channel(-110.0, 20.0)
        df = df.dropna(subset=['DateTime']).sort_values('DateTime').reset_index(drop=True)
        
        st.success(f"🔓 ซิงค์โครงสร้างเวลาและตำแหน่งเซนเซอร์สำเร็จ! ตรวจพบช่วงบันทึกจริง: {df['DateTime'].min()} ถึง {df['DateTime'].max()} (รวม {len(df)} แถวข้อมูล)")
    else:
        # บล็อกกรณีฉุกเฉิน: หากไฟล์บีบอัดสูงจนหา String เวลาไม่เจอ จะกลับไปใช้โหมดเสถียรความถี่คงที่
        st.warning("⚠️ ไม่พบ String เวลาตรงๆ ในไฟล์ไบนารี ระบบเปิดโหมดจำลองเวลาเสถียรเพื่อพล็อตกราฟต่อ")
        clean_stream = [float(n) for n in re.findall(r'[-+]?\d*\.\d+|\b\d{1,3}\b', text_data) if -120.0 <= float(n) <= 3000.0]
        rows = len(clean_stream) // 23
        matrix_data = np.array(clean_stream[:rows * 23]).reshape(-1, 23)
        df = pd.DataFrame(matrix_data, columns=[f'CH_{i+1}' for i in range(23)])
        
        # สร้างสเกลเวลาขยายออกกว้างขึ้นตาม Sidebar
        st.sidebar.header("⏱️ ตั้งค่าเวลาบันทึก (Time Settings)")
        start_date = st.sidebar.date_input("วันที่เริ่มต้น", value=pd.to_datetime('2026-09-02'))
        start_time = st.sidebar.time_input("เวลาที่เริ่มบันทึก", value=pd.to_datetime('00:00:00').time())
        time_value = st.sidebar.number_input("ระยะห่างข้อมูลต่อนาที (Minutes/Point)", min_value=1, value=1)
        
        df['DateTime'] = pd.date_range(start=f"{start_date} {start_time}", periods=len(df), freq=f"{time_value}min")
        
        # จัดชื่อคอลัมน์แบบจับคู่ชั่วคราว
        df.rename(columns={'CH_1':'Dryer_1', 'CH_2':'Dryer_2', 'CH_3':'Oxygen_O2', 'CH_4':'N2_Flow', 'CH_23':'Dew_Point'}, inplace=True)
        for i in range(14): df.rename(columns={f'CH_{5+i}': f'Heat_Z{i+1}'}, inplace=True)

    # 3. เริ่มสร้างโครงสร้าง Subplots แบบ 5 ชั้นแนวตั้ง และจัดวางกราฟเข้าตำแหน่งแกน
    if not df.empty:
        fig = make_subplots(
            rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.05,
            specs=[[{"secondary_y": False}], [{"secondary_y": False}], [{"secondary_y": False}], [{"secondary_y": True}], [{"secondary_y": False}]]
        )

        # กล่องที่ 1: Dryer #1 & Dryer #2 (0 - 400 °C)
        fig.add_trace(go.Scatter(x=df['DateTime'], y=df['Dryer_1'], name="Dryer #1", legend="legend1", line=dict(color='#FF5733', width=2)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['DateTime'], y=df['Dryer_2'], name="Dryer #2", legend="legend1", line=dict(color='#FF8D33', width=2)), row=1, col=1)

        # กล่องที่ 2: Heating Zone 1-7 (Top - 400 - 650 °C)
        for i in range(1, 8):
            fig.add_trace(go.Scatter(x=df['DateTime'], y=df[f'Heat_Z{i}'], name=f"H-Zone {i} (Top)", legend="legend2", line=dict(width=1.5)), row=2, col=1)

        # กล่องที่ 3: Heating Zone 8-14 (Bottom - 400 - 650 °C)
        for i in range(8, 15):
            fig.add_trace(go.Scatter(x=df['DateTime'], y=df[f'Heat_Z{i}'], name=f"H-Zone {i} (Bottom)", legend="legend3", line=dict(width=1.5, dash='dash')), row=3, col=1)

        # กล่องที่ 4: Oxygen (แกนซ้าย 0-200) & N2 Flow (แกนขวา Free Scale)
        fig.add_trace(go.Scatter(x=df['DateTime'], y=df['Oxygen_O2'], name="Oxygen (ppm O2)", legend="legend4", line=dict(color='#33FF57', width=2)), row=4, col=1, secondary_y=False)
        fig.add_trace(go.Scatter(x=df['DateTime'], y=df['N2_Flow'], name="N2 Flow (h3/h)", legend="legend4", line=dict(color='#3357FF', width=2)), row=4, col=1, secondary_y=True)

        # กล่องที่ 5: Dew Point (10 ถึง -100 °Cdp - โหมด Free Scale ยืดหยุ่น)
        fig.add_trace(go.Scatter(x=df['DateTime'], y=df['Dew_Point'], name="Dew Point", legend="legend5", line=dict(color='#E333FF', width=2, dash='dot')), row=5, col=1)

        # 4. ตั้งค่า Layout จัดกลุ่มป้ายชื่อขวาสุด และกำหนดขอบเขตแกน Y สากล
        fig.update_layout(
            template="plotly_dark", height=1100, hovermode="x unified",
            title_text="Yokogawa Process Analyzer Dashboard (Time & Channel Synced Engine)",
            legend1=dict(traceorder="normal", x=1.02, y=0.94, bgcolor="rgba(0,0,0,0)"),
            legend2=dict(traceorder="normal", x=1.02, y=0.75, bgcolor="rgba(0,0,0,0)"),
            legend3=dict(traceorder="normal", x=1.02, y=0.55, bgcolor="rgba(0,0,0,0)"),
            legend4=dict(traceorder="normal", x=1.02, y=0.35, bgcolor="rgba(0,0,0,0)"),
            legend5=dict(traceorder="normal", x=1.02, y=0.12, bgcolor="rgba(0,0,0,0)")
        )
        
        # บังคับช่วงล็อกสเกลแกน Y ให้เที่ยงตรงตามหน้างาน
        fig.update_yaxes(title_text="Dryer Temp (°C)", range=[-10, 420], row=1, col=1)
        fig.update_yaxes(title_text="Heating Top (°C)", range=[380, 680], row=2, col=1)
        fig.update_yaxes(title_text="Heating Bottom (°C)", range=[380, 680], row=3, col=1)
        fig.update_yaxes(title_text="Oxygen (ppm O2)", color="#33FF57", range=[-10, 210], row=4, col=1, secondary_y=False)
        fig.update_yaxes(title_text="N2 Flow (h3/h)", color="#3357FF", autorange=True, row=4, col=1, secondary_y=True)
        fig.update_yaxes(title_text="Dew Point (°Cdp)", range=[-110, 20], row=5, col=1)
        fig.update_xaxes(title_text="Date & Time (Synchronized Timeline)", row=5, col=1)

        st.plotly_chart(fig, use_container_width=True)
else:
    st.info("💡 กรุณาอัปโหลดไฟล์บันทึกสัญญาณ (.DAD) เพื่อพล็อตกราฟซิงค์แกนเวลาจริงและจัดล็อกพารามิเตอร์")
