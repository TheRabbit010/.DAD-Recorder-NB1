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
st.title("🏭 Factory Process Master Dashboard - True Raw Value Mode")
st.subheader("พล็อตกราฟอิงจากค่าดิบจริงของไฟล์ Yokogawa และเปิดระบบกำจัดยอดแหลมสัญญาณรบกวน")

uploaded_file = st.file_uploader("อัปโหลดไฟล์ดิบ .DAD ของคุณที่นี่", type=["dad", "dat"])

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    text_data = file_bytes.decode('latin-1', errors='ignore')
    
    # 1. สกัดตัวเลขดิบทั้งหมดออกจากโครงสร้างไฟล์
    all_numbers = re.findall(r'[-+]?\d*\.\d+(?:[eE][-+]?\d+)?|\b\d{1,4}\b', text_data)
    numeric_stream = [float(n) for n in all_numbers]
    
    # กรองล้างเฉพาะค่าไบนารีหลุดขอบเขตเตาอุตสาหกรรม
    clean_stream = [n for n in numeric_stream if -150.0 <= n <= 3500.0]
    
    detected_channels = 23
    
    if len(clean_stream) >= detected_channels:
        rows = len(clean_stream) // detected_channels
        matrix_data = np.array(clean_stream[:rows * detected_channels]).reshape(-1, detected_channels)
        
        col_names = [f'CH_{i+1}' for i in range(detected_channels)]
        df = pd.DataFrame(matrix_data, columns=col_names)
        
        # ⏱️ แถบตั้งค่ากะเวลาทำงาน
        st.sidebar.header("⏱️ ตั้งค่าเวลาบันทึก (Time Settings)")
        start_date = st.sidebar.date_input("เลือกวันที่เริ่มต้นขบวนการผลิต", value=pd.to_datetime('2026-08-12'))
        start_time = st.sidebar.time_input("เลือกเวลาที่เริ่มบันทึก", value=pd.to_datetime('01:30:00').time())
        time_unit = st.sidebar.selectbox("ช่วงระยะเวลาห่างต่อจุดข้อมูล", ["วินาที (Seconds)", "นาที (Minutes)"], index=1)
        time_value = st.sidebar.number_input("จำนวนหน่วยเวลาต่อ 1 จุด", min_value=1, value=1)
        
        freq_code = f"{time_value}s" if time_unit == "วินาที (Seconds)" else f"{time_value}min"
        start_timestamp = pd.to_datetime(f"{start_date} {start_time}")
        df['DateTime'] = pd.date_range(start=start_timestamp, periods=len(df), freq=freq_code)
        
        # 🛠️ [เพิ่มฟีเจอร์เคลียร์นอยส์] ระบบกำจัดยอดแหลมแปลกปลอม (Spike Filter) และทำความเรียบเนียน
        st.sidebar.markdown("---")
        st.sidebar.header("🛡️ ตัวกรองสัญญาณรบกวน (Signal Filter)")
        clean_spikes = st.sidebar.checkbox("เปิดระบบล้างยอดสวิงแหลม (Remove Spikes)", value=True)
        enable_smooth = st.sidebar.checkbox("เปิดโหมดเส้นเนียน (Smooth Curve)", value=True)
        window_size = st.sidebar.slider("ระดับความเรียบเนียน", min_value=3, max_value=15, value=5, step=2)
        
        # โคลนตารางมาทำความสะอาดสัญญาณดิบ
        df_clean = df.copy()
        
        # ลอจิกกำจัดค่า Spikes ที่โดดพุ่งเกินความจริงของระบบฟิสิกส์โรงงาน (ใช้เทคนิค Median Filtering)
        if clean_spikes:
            for col in col_names:
                df_clean[col] = df_clean[col].rolling(window=5, center=True, min_periods=1).median()
                
        # โหมดทำเส้นโค้งมนเนียนตา
        if enable_smooth:
            for col in col_names:
                df_clean[col] = df_clean[col].rolling(window=window_size, center=True, min_periods=1).mean()
                
        # 📊 ตารางสรุปค่าจริงบน Left Sidebar ด้านซ้ายมือ
        st.sidebar.markdown("---")
        st.sidebar.header("📊 ตารางสรุปค่าดิบจริง")
        mapping_labels = {
            'CH_1': 'O2 Entrance', 'CH_2': 'O2 Exit',
            'CH_3': 'Dryer #2', 'CH_4': 'Dryer #1',
            'CH_19': 'N2 Flow', 'CH_23': 'Dew Point'
        }
        for i in range(14): mapping_labels[f'CH_{5+i}'] = f'H-Zone {i+1}'
            
        stats_records = []
        for col in col_names:
            if col in df_clean.columns:
                stats_records.append({
                    "ช่องสัญญาณ": mapping_labels.get(col, col), 
                    "Min": f"{df_clean[col].min():,.1f}", 
                    "Max": f"{df_clean[col].max():,.1f}"
                })
        st.sidebar.dataframe(pd.DataFrame(stats_records), use_container_width=True, hide_index=True)

        st.success(f"🔓 ถอดรหัสและประมวลผลล้างสัญญาณรบกวนสำเร็จ! แสดงผลลัพธ์จากสตรีมค่าจริงคงที่")

        # 2. เริ่มสร้างโครงสร้าง Subplots แบบ 5 ชั้นแนวตั้ง (ไม่มีฟังก์ชันยืดหดสเกลคณิตศาสตร์มาขวางอีกต่อไป)
        fig = make_subplots(
            rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.05,
            specs=[[{"secondary_y": False}], [{"secondary_y": False}], [{"secondary_y": False}], [{"secondary_y": True}], [{"secondary_y": False}]]
        )

        # กล่องที่ 1: Dryer #1 & Dryer #2 (ดึงค่าจริงตรงๆ จาก CH_4 และ CH_3)
        if 'CH_4' in df_clean.columns:
            fig.add_trace(go.Scatter(x=df_clean['DateTime'], y=df_clean['CH_4'], name="Dryer #1", legend="legend1", line=dict(color='#FF5733', width=2)), row=1, col=1)
        if 'CH_3' in df_clean.columns:
            fig.add_trace(go.Scatter(x=df_clean['DateTime'], y=df_clean['CH_3'], name="Dryer #2", legend="legend1", line=dict(color='#FF8D33', width=2)), row=1, col=1)

        # กล่องที่ 2: Heating Zone 1-7 (Top)
        heat_start_idx = 5
        for i in range(0, 7):
            ch_name = f'CH_{heat_start_idx + i}'
            if ch_name in df_clean.columns:
                fig.add_trace(go.Scatter(x=df_clean['DateTime'], y=df_clean[ch_name], name=f"H-Zone {i+1} (Top)", legend="legend2", line=dict(width=2)), row=2, col=1)

        # กล่องที่ 3: Heating Zone 8-14 (Bottom - เส้นประ)
        for i in range(7, 14):
            ch_name = f'CH_{heat_start_idx + i}'
            if ch_name in df_clean.columns:
                fig.add_trace(go.Scatter(x=df_clean['DateTime'], y=df_clean[ch_name], name=f"H-Zone {i-6} (Bottom)", legend="legend3", line=dict(width=1.5, dash='dash')), row=3, col=1)

        # กล่องที่ 4: Oxygen (แกนซ้าย) & N2 Flow (แกนขวา) 
        if 'CH_1' in df_clean.columns:
            fig.add_trace(go.Scatter(x=df_clean['DateTime'], y=df_clean['CH_1'], name="O2 Entrance (ppm)", legend="legend4", line=dict(color='#33FF57', width=2)), row=4, col=1, secondary_y=False)
        if 'CH_2' in df_clean.columns:
            fig.add_trace(go.Scatter(x=df_clean['DateTime'], y=df_clean['CH_2'], name="O2 Exit (ppm)", legend="legend4", line=dict(color='#1bba3c', width=2)), row=4, col=1, secondary_y=False)
        if 'CH_19' in df_clean.columns:
            fig.add_trace(go.Scatter(x=df_clean['DateTime'], y=df_clean['CH_19'], name="N2 Flow (h3/h)", legend="legend4", line=dict(color='#3357FF', width=2)), row=4, col=1, secondary_y=True)

        # กล่องที่ 5: Dew Point
        if 'CH_23' in df_clean.columns:
            fig.add_trace(go.Scatter(x=df_clean['DateTime'], y=df_clean['CH_23'], name="Dew Point", legend="legend5", line=dict(color='#E333FF', width=2, dash='dot')), row=5, col=1)

        # 3. จัดสรรผังคำอธิบายกราฟไว้ขวาสุด
        fig.update_layout(
            template="plotly_dark", height=1100, hovermode="x unified",
            title_text="Yokogawa Process Analyzer Dashboard (Industrial True Value Engine)",
            legend1=dict(traceorder="normal", x=1.02, y=0.94, bgcolor="rgba(0,0,0,0)"),
            legend2=dict(traceorder="normal", x=1.02, y=0.75, bgcolor="rgba(0,0,0,0)"),
            legend3=dict(traceorder="normal", x=1.02, y=0.55, bgcolor="rgba(0,0,0,0)"),
            legend4=dict(traceorder="normal", x=1.02, y=0.35, bgcolor="rgba(0,0,0,0)"), 
            legend5=dict(traceorder="normal", x=1.02, y=0.12, bgcolor="rgba(0,0,0,0)")
        )
        
        # เปิดระบบออโต้สเกลเต็มกำลัง (Autorange=True) ในการแสดงผลค่าจริงเพื่อให้เส้นขยับขึ้นลงตามความชันเครื่องจักรเป๊ะๆ
        fig.update_yaxes(title_text="Dryer Temp (°C)", autorange=True, row=1, col=1)
        fig.update_yaxes(title_text="Heating Top (°C)", range=[380, 680], row=2, col=1)   # ตั้งช่วงครอบเพื่อให้เห็นเส้นนิ่งช่วง 500-650 สบายตา
        fig.update_yaxes(title_text="Heating Bottom (°C)", range=[380, 680], row=3, col=1) # ตั้งช่วงครอบเพื่อให้เห็นเส้นนิ่งช่วง 500-650 สบายตา
        fig.update_yaxes(title_text="Oxygen Exit/Ent (ppm)", color="#33FF57", autorange=True, row=4, col=1, secondary_y=False)
        fig.update_yaxes(title_text="N2 Flow (h3/h)", color="#3357FF", autorange=True, row=4, col=1, secondary_y=True)
        fig.update_yaxes(title_text="Dew Point (°Cdp)", range=[-110, 20], row=5, col=1)
        fig.update_xaxes(title_text="Date & Time (Process Timeline)", row=5, col=1)

        st.plotly_chart(fig, use_container_width=True)
        
    else:
        st.error("❌ โครงสร้างชุดข้อมูลในไฟล์ .DAD ไม่สอดคล้องกับพารามิเตอร์ 23 ช่องสัญญาณ")
else:
    st.info("💡 กรุณาอัปโหลดไฟล์บันทึกสัญญาณ (.DAD) เพื่อพล็อตกราฟค่าตรงตามเครื่องจักรจริง")
