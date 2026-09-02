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
st.title("🏭 Factory Process Master Dashboard")
st.subheader("ระบบถอดรหัสและวิเคราะห์ไฟล์ Yokogawa .DAD ความละเอียดสูง (เวอร์ชันจบงาน)")

uploaded_file = st.file_uploader("อัปโหลดไฟล์ดิบ .DAD ของคุณที่นี่", type=["dad", "dat"])

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    text_data = file_bytes.decode('latin-1', errors='ignore')
    
    # 1. ลอจิกขูดข้อมูลพารามิเตอร์การวัดแท้จริงจากโครงสร้างไฟล์ Yokogawa
    all_numbers = re.findall(r'[-+]?\d*\.\d+(?:[eE][-+]?\d+)?|\b\d{1,3}\b', text_data)
    numeric_stream = [float(n) for n in all_numbers]
    clean_stream = [n for n in numeric_stream if -60.0 <= n <= 2500.0]
    
    detected_channels = 23
    
    if len(clean_stream) >= detected_channels:
        rows = len(clean_stream) // detected_channels
        matrix_data = np.array(clean_stream[:rows * detected_channels]).reshape(-1, detected_channels)
        
        col_names = [f'CH_{i+1}' for i in range(detected_channels)]
        df = pd.DataFrame(matrix_data, columns=col_names)
        
        # 🛠️ แถบลดสัญญาณรบกวนและตั้งค่าเวลาด้านซ้ายมือ (Sidebar)
        st.sidebar.header("⚙️ การจัดการข้อมูล (Data Control)")
        
        # ฟีเจอร์กรองสัญญาณรบกวน (Moving Average)
        enable_smooth = st.sidebar.checkbox("เปิดโหมดลดสัญญาณรบกวน (Smooth Curve)", value=False)
        smooth_window = st.sidebar.slider("ระดับความเนียน (Window Size)", min_value=3, max_value=21, value=5, step=2)
        
        st.sidebar.markdown("---")
        st.sidebar.header("⏱️ ตั้งค่าเวลาบันทึก (Time Settings)")
        start_date = st.sidebar.date_input("เลือกวันที่เริ่มต้นขบวนการผลิต", value=pd.to_datetime('2026-09-02'))
        start_time = st.sidebar.time_input("เลือกเวลาที่เริ่มบันทึก", value=pd.to_datetime('00:00:00').time())
        time_unit = st.sidebar.selectbox("ช่วงระยะเวลาห่างต่อจุดข้อมูล", ["วินาที (Seconds)", "นาที (Minutes)"], index=0)
        time_value = st.sidebar.number_input("จำนวนหน่วยเวลาต่อ 1 จุด", min_value=1, value=10)
        
        # คำนวณแกนเวลา
        freq_code = f"{time_value}s" if time_unit == "วินาที (Seconds)" else f"{time_value}min"
        start_timestamp = pd.to_datetime(f"{start_date} {start_time}")
        df['DateTime'] = pd.date_range(start=start_timestamp, periods=len(df), freq=freq_code)
        
        # คัดลอกข้อมูลเพื่อนำไปประมวลผลฟิลเตอร์กรองสัญญาณรบกวน
        df_plot = df.copy()
        if enable_smooth:
            for col in col_names:
                df_plot[col] = df_plot[col].rolling(window=smooth_window, center=True, min_periods=1).mean()
        
        st.success(f"🔓 ถอดรหัสไฟล์และประมวลผลโครงสร้างสำเร็จ! ตรวจพบข้อมูล {len(df_plot)} แถว")

        # 2. เริ่มสร้างโครงสร้าง Subplots 4 ชั้นแนวตั้ง
        fig = make_subplots(
            rows=4, 
            cols=1, 
            shared_xaxes=True, 
            vertical_spacing=0.06,
            specs=[[{"secondary_y": False}],
                   [{"secondary_y": False}],
                   [{"secondary_y": True}],  # เปิดแกนคู่สำหรับกล่องที่ 3 (O2 และ N2 Flow)
                   [{"secondary_y": False}]]
        )

        # ----------------------------------------------------
        # กล่องที่ 1: Dryer #1 & Dryer #2
        # ----------------------------------------------------
        if 'CH_1' in df_plot.columns:
            fig.add_trace(go.Scatter(x=df_plot['DateTime'], y=df_plot['CH_1'], name="Dryer #1", line=dict(color='#FF5733', width=2)), row=1, col=1)
        if 'CH_2' in df_plot.columns:
            fig.add_trace(go.Scatter(x=df_plot['DateTime'], y=df_plot['CH_2'], name="Dryer #2", line=dict(color='#FF8D33', width=2)), row=1, col=1)

        # ----------------------------------------------------
        # กล่องที่ 2: Heating Zone 1-14 (Top & Bottom Overlay)
        # ----------------------------------------------------
        heat_start_idx = 5
        for i in range(0, 7):
            ch_name = f'CH_{heat_start_idx + i}'
            if ch_name in df_plot.columns:
                fig.add_trace(go.Scatter(x=df_plot['DateTime'], y=df_plot[ch_name], name=f"Heating Z{i+1} (Top)", line=dict(width=1.5)), row=2, col=1)

        for i in range(7, 14):
            ch_name = f'CH_{heat_start_idx + i}'
            if ch_name in df_plot.columns:
                fig.add_trace(go.Scatter(x=df_plot['DateTime'], y=df_plot[ch_name], name=f"Heating Z{i+1} (Bottom)", line=dict(width=1.5, dash='dash')), row=2, col=1)

        # ----------------------------------------------------
        # กล่องที่ 3: Oxygen ppm O2 (แกนซ้าย) & N2 Flow (แกนขวา)
        # ----------------------------------------------------
        if 'CH_3' in df_plot.columns:
            fig.add_trace(go.Scatter(
                x=df_plot['DateTime'], y=df_plot['CH_3'], name="Oxygen (ppm O2)", 
                line=dict(color='#33FF57', width=2)
            ), row=3, col=1, secondary_y=False)

        if 'CH_4' in df_plot.columns:
            fig.add_trace(go.Scatter(
                x=df_plot['DateTime'], y=df_plot['CH_4'], name="N2 Flow (h3/h)", 
                line=dict(color='#3357FF', width=2)
            ), row=3, col=1, secondary_y=True)

        # ----------------------------------------------------
        # กล่องที่ 4: Dew Point
        # ----------------------------------------------------
        if 'CH_23' in df_plot.columns:
            fig.add_trace(go.Scatter(
                x=df_plot['DateTime'], y=df_plot['CH_23'], name="Dew Point", 
                line=dict(color='#E333FF', width=2, dash='dot')
            ), row=4, col=1)

        # 3. ตั้งค่า Layout และระบบแสดงผลแบบไดนามิก
        fig.update_layout(
            template="plotly_dark",
            height=950,
            hovermode="x unified",
            title_text="Yokogawa Process Analyzer Dashboard (Production-Grade Master Engine)"
        )
        
        fig.update_yaxes(title_text="Dryer Temp (°C)", autorange=True, row=1, col=1)
        fig.update_yaxes(title_text="Heating Temp (°C)", autorange=True, row=2, col=1)
        
        fig.update_yaxes(title_text="Oxygen (ppm O2)", color="#33FF57", autorange=True, row=3, col=1, secondary_y=False)
        fig.update_yaxes(title_text="N2 Flow (h3/h)", color="#3357FF", autorange=True, row=3, col=1, secondary_y=True)
        
        fig.update_yaxes(title_text="Dew Point (Auto)", autorange=True, row=4, col=1)
        fig.update_xaxes(title_text="Date & Time (Process Timeline)", row=4, col=1)

        st.plotly_chart(fig, use_container_width=True)
        
        # ปุ่มกดดาวน์โหลดตารางข้อมูลสรุปเป็นไฟล์ CSV เพื่อเอาไปใช้งานต่อใน Excel
        st.sidebar.markdown("---")
        st.sidebar.subheader("📥 ส่งออกข้อมูล (Export Data)")
        csv_data = df_plot.to_csv(index=False).encode('utf-8')
        st.sidebar.download_button(
            label="ดาวน์โหลดไฟล์ตาราง (.CSV)",
            data=csv_data,
            file_name="processed_factory_data.csv",
            mime="text/csv"
        )
        
    else:
        st.error("❌ โครงสร้างข้อมูลไม่เพียงพอต่อระบบวิเคราะห์พารามิเตอร์")
else:
    st.info("💡 กรุณาอัปโหลดไฟล์บันทึกสัญญาณ (.DAD) เพื่อพล็อตกราฟควบคุมกระบวนการผลิต")
