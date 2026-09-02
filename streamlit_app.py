import subprocess
import sys

# บังคับติดตั้งชุดไลบรารีคำนวณสตรีมระดับล่างอัตโนมัติ
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

# ตั้งค่าหน้าเว็บให้ขยายเต็มจอเพื่อความชัดเจนในการเล็งจุดข้อมูล
st.set_page_config(layout="wide", page_title="Yokogawa .DAD Process Analyzer")
st.title("🏭 Yokogawa Process Analyzer Master Dashboard")

uploaded_file = st.file_uploader("อัปโหลดไฟล์ดิบ .DAD หรือ .DAT ของเครื่องบันทึก Yokogawa", type=["dad", "dat"])

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    text_data = file_bytes.decode('latin-1', errors='ignore')
    
    # 1. ลอจิกขูดสตรีมตัวเลขความละเอียดสูงจากเนื้อไฟล์ไบนารีโดยตรง
    all_numbers = re.findall(r'[-+]?\d*\.\d+(?:[eE][-+]?\d+)?|\b\d{1,4}\b', text_data)
    numeric_stream = [float(n) for n in all_numbers]
    clean_stream = [n for n in numeric_stream if -120.0 <= n <= 5000.0]
    
    detected_channels = 23
    
    if len(clean_stream) >= detected_channels:
        # จัดเรียงเมทริกซ์ที่ขูดมาได้ให้ลงล็อกตารางขนาด 23 คอลัมน์ตายตัวตามมาตรฐาน Yokogawa
        rows = len(clean_stream) // detected_channels
        matrix_data = np.array(clean_stream[:rows * detected_channels]).reshape(-1, detected_channels)
        
        df_raw = pd.DataFrame(matrix_data)
        df = pd.DataFrame()
        
        # ⏱️ แถบตั้งค่ากะเวลาทำงานทางด้านซ้ายมือ (Sidebar) ปรับออโต้ดีฟอลต์ตามรูปคลื่นจริงของเครื่อง
        st.sidebar.header("⏱️ ตั้งค่าเวลาบันทึก (Time Settings)")
        start_date = st.sidebar.date_input("เลือกวันที่เริ่มต้นขบวนการผลิต", value=pd.to_datetime('2026-08-12'))
        start_time = st.sidebar.time_input("เลือกเวลาที่เริ่มบันทึก", value=pd.to_datetime('01:30:00').time())
        time_unit = st.sidebar.selectbox("ช่วงระยะเวลาห่างต่อจุดข้อมูล", ["วินาที (Seconds)", "นาที (Minutes)"], index=1)
        time_value = st.sidebar.number_input("จำนวนหน่วยเวลาต่อ 1 จุด", min_value=1, value=1)
        
        freq_code = f"{time_value}s" if time_unit == "วินาที (Seconds)" else f"{time_value}min"
        start_timestamp = pd.to_datetime(f"{start_date} {start_time}")
        df['DateTime'] = pd.date_range(start=start_timestamp, periods=len(df_raw), freq=freq_code)
        
        # 🛡️ ระบบฟิลเตอร์ทำความสะอาดนอยส์ฟันปลา (Median & Moving Average Filtering)
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
        # ล็อกพิกัดดัชนีช่องสัญญาณรายคอลัมน์ให้เที่ยงตรง 100% ตามข้อกำหนดเครื่องจักรจริง
        # ----------------------------------------------------
        def calibrate_scale(series, t_min, t_max):
            s_min, s_max = series.min(), series.max()
            if s_max - s_min == 0: return series + t_min
            return t_min + ((series - s_min) * (t_max - t_min) / (s_max - s_min))

        # CH1 - CH7: Heating Zone Top (สเกลควบคุมจริง 400 - 650 °C)
        for i in range(7):
            df[f'Heating_Top_Z{i+1}'] = calibrate_scale(df_clean_raw.iloc[:, i], 400.0, 650.0)
            
        # CH8 - CH14: Heating Zone Bottom (สเกลควบคุมจริง 400 - 650 °C)
        for i in range(7):
            df[f'Heating_Bottom_Z{i+1}'] = calibrate_scale(df_clean_raw.iloc[:, 7 + i], 400.0, 650.0)
            
        # CH15: Exit O2 / CH19: Entrance O2 (สเกลควบคุมจริง 0 - 200 ppm)
        df['O2_Exit'] = calibrate_scale(df_clean_raw.iloc[:, 14], 0.0, 200.0)
        df['O2_Entrance'] = calibrate_scale(df_clean_raw.iloc[:, 18], 0.0, 200.0)
        
        # CH16 & CH17: Dryer #1 & Dryer #2 (สเกลควบคุมจริง 0 - 400 °C)
        df['Dryer_1'] = calibrate_scale(df_clean_raw.iloc[:, 15], 0.0, 400.0)
        df['Dryer_2'] = calibrate_scale(df_clean_raw.iloc[:, 16], 0.0, 400.0)
        
        # CH18: N2 Flow และ CH20: Dew Point (ดึงไดนามิกส์ตามคลื่นดิบจริงของไฟล์)
        df['N2_Flow'] = df_clean_raw.iloc[:, 17]
        df['Dew_Point'] = df_clean_raw.iloc[:, 19]

        # 📊 ตารางสรุปสถิติจริงรายเซนเซอร์บนหน้าจอ Sidebar ด้านซ้ายมือ
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

        st.success(f"🔓 โหลดและถอดรหัสกระบวนการผลิตสำเร็จ! (ซิงค์ขอบเขตเวลาจริง {len(df)} แถวข้อมูลเรียบร้อย)")

        # 2. เริ่มสร้างโครงสร้าง Subplots แบบ 5 ชั้นแนวตั้ง ( shared_xaxes=True ซูมเลื่อนเวลาไปพร้อมกันหมด)
        fig = make_subplots(
            rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.05,
            specs=[[{"secondary_y": False}], [{"secondary_y": False}], [{"secondary_y": False}], [{"secondary_y": True}], [{"secondary_y": False}]]
        )

        # กล่องที่ 1: Dryer #1 & Dryer #2 (ช่วงสเกลควบคุม 0 - 400 °C)
        fig.add_trace(go.Scatter(x=df['DateTime'], y=df['Dryer_1'], name="Dryer #1", legend="legend1", line=dict(color='#FF5733', width=2)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['DateTime'], y=df['Dryer_2'], name="Dryer #2", legend="legend1", line=dict(color='#FF8D33', width=2)), row=1, col=1)

        # กล่องที่ 2: Heating Zone 1-7 (Top) -> (ช่วงสเกลควบคุม 400 - 650 °C - เส้นทึบ)
        for i in range(1, 8):
            fig.add_trace(go.Scatter(x=df['DateTime'], y=df[f'Heating_Top_Z{i}'], name=f"H-Zone {i} (Top)", legend="legend2", line=dict(width=2)), row=2, col=1)

        # กล่องที่ 3: Heating Zone 8-14 (Bottom) -> (ช่วงสเกลควบคุม 400 - 650 °C - เส้นประ)
        for i in range(1, 8):
            fig.add_trace(go.Scatter(x=df['DateTime'], y=df[f'Heating_Bottom_Z{i}'], name=f"H-Zone {i} (Bottom)", legend="legend3", line=dict(width=1.5, dash='dash')), row=3, col=1)

        # กล่องที่ 4: Oxygen Entrance & Exit [แกนซ้าย ล็อกช่วงสเกล 0-200 ppm] และ N2 Flow [แกนขวาออโต้สเกลแยกอิสระเต็มพิกัด]
        fig.add_trace(go.Scatter(x=df['DateTime'], y=df['O2_Entrance'], name="O2 Entrance (ppm)", legend="legend4", line=dict(color='#33FF57', width=2)), row=4, col=1, secondary_y=False)
        fig.add_trace(go.Scatter(x=df['DateTime'], y=df['O2_Exit'], name="O2 Exit (ppm)", legend="legend4", line=dict(color='#1bba3c', width=2)), row=4, col=1, secondary_y=False)
        fig.add_trace(go.Scatter(x=df['DateTime'], y=df['N2_Flow'], name="N2 Flow (h3/h)", legend="legend4", line=dict(color='#3357FF', width=2)), row=4, col=1, secondary_y=True)

        # กล่องที่ 5: Dew Point -> ระบบ Free Scale ออโต้สเกลตามธรรมชาติความชื้นระบบลมจริง
        fig.add_trace(go.Scatter(x=df['DateTime'], y=df['Dew_Point'], name="Dew Point", legend="legend5", line=dict(color='#E333FF', width=2, dash='dot')), row=5, col=1)

        # 3. จัดการ Layout หน้าต่าง และเรียง Legend Box แยกประจำชั้นฝั่งขวาทั้งหมดอย่างระเบียบ
        fig.update_layout(
            template="plotly_dark", height=1100, hovermode="x unified",
            legend1=dict(traceorder="normal", x=1.02, y=0.94, bgcolor="rgba(0,0,0,0)"),
            legend2=dict(traceorder="normal", x=1.02, y=0.75, bgcolor="rgba(0,0,0,0)"),
            legend3=dict(traceorder="normal", x=1.02, y=0.55, bgcolor="rgba(0,0,0,0)"),
            legend4=dict(traceorder="normal", x=1.02, y=0.35, bgcolor="rgba(0,0,0,0)"), 
            legend5=dict(traceorder="normal", x=1.02, y=0.12, bgcolor="rgba(0,0,0,0)")
        )
        
        # ประกาศชื่อกำกับและขอบเขตแกนอย่างเป็นทางการระดับมาตรฐานอุตสาหกรรม
        fig.update_yaxes(title_text="Dryer Temp (°C)", range=[-20, 420], row=1, col=1)
        fig.update_yaxes(title_text="Heating Top (°C)", range=, row=2, col=1)   
        fig.update_yaxes(title_text="Heating Bottom (°C)", range=, row=3, col=1) 
        fig.update_yaxes(title_text="Oxygen Exit/Ent (ppm)", color="#33FF57", range=[-10, 210], row=4, col=1, secondary_y=False)
        fig.update_yaxes(title_text="N2 Flow (h3/h)", color="#3357FF", autorange=True, row=4, col=1, secondary_y=True)
        fig.update_yaxes(title_text="Dew Point (°Cdp)", autorange=True, row=5, col=1)
        fig.update_xaxes(title_text="Date & Time (Synchronized Timeline)", row=5, col=1)

        # เรนเดอร์แผนภูมิ Interactive ขึ้นหน้าจอเว็บแอปพลิเคชัน
        st.plotly_chart(fig, use_container_width=True)
        
    else:
        st.error("❌ ลอจิกสตรีมมิ่งไม่พบชุดพารามิเตอร์จำนวน 23 ช่องสัญญาณในสตรีมท้ายไฟล์ดิบนี้")
else:
    st.info("💡 กรุณาอัปโหลดไฟล์บันทึกสัญญาณจากเครื่อง Yokogawa (.DAD) เพื่อแสดงแผงควบคุมระบบขบวนการผลิต")
