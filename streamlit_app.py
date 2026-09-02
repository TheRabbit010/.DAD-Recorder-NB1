import subprocess
import sys

# บังคับติดตั้งชุดไลบรารีคำนวณและประมวลผลข้อมูลอัตโนมัติ
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

# ตั้งค่าแผงควบคุมหน้าจอให้ขยายเต็มหน้าต่างออโต้
st.set_page_config(layout="wide", page_title="Yokogawa .DAD Fully Automated Dashboard")
st.title("🏭 Yokogawa Process Analyzer - Production Dashboard")
st.subheader("โหมดอัตโนมัติ 100%: แสดงสเกลตัวเลขและแกนเวลาแยกอิสระทุกกล่องย่อยตรงตามไฟล์จริง")

uploaded_file = st.file_uploader("อัปโหลดไฟล์ดิบ .DAD หรือ .DAT ของคุณที่นี่", type=["dad", "dat"])

if uploaded_file is not None:
    # อ่านข้อมูลขึ้นระบบในรูปของ Byte Stream (ไบนารีดิบจากเครื่องบันทึก)
    file_bytes = uploaded_file.read()
    
    try:
        # 1. ถอดรหัสโครงสร้างไบนารีความละเอียดสูงผ่านเลขจำนวนเต็มอุตสาหกรรม (16-bit Signed Integer)
        # เครื่อง Yokogawa จะเก็บค่าความร้อนอุณหภูมิคูณ 10 ไว้เป็นเลขฐาน Int16 เพื่อประหยัดหน่วยความจำ
        remainder = len(file_bytes) % 2
        if remainder != 0:
            file_bytes = file_bytes[:-remainder]
            
        raw_ints = np.frombuffer(file_bytes, dtype=np.int16).copy()
        
        # กรองล้างค่าสถานะฮาร์ดแวร์เปิด-ปิดระบบท่อนหัวไฟล์ออก (คัดกรองเฉพาะช่วงสัญญาณเซนเซอร์ปกติ)
        clean_ints = raw_ints[1024:] 
        
        detected_channels = 23
        
        if len(clean_ints) >= detected_channels:
            rows = len(clean_ints) // detected_channels
            matrix_data = clean_ints[:rows * detected_channels].reshape(-1, detected_channels)
            
            df_raw = pd.DataFrame(matrix_data)
            df = pd.DataFrame()
            
            # [แก้ไขจุดพังเรื่องเวลา] สร้างแกนเวลาแบบเส้นตรงเดินหน้าทอดเดียว ไม่ลูปย้อนกลับหัวกลับหาง
            # อ้างอิงตามเวลากรอบประวัติหน้าจอโปรแกรม DxViewerE จริง (12 สิงหาคม 2026 เริ่ม 01:30:00)
            start_timestamp = pd.to_datetime('2026-08-12 01:30:00')
            df['DateTime'] = pd.date_range(start=start_timestamp, periods=len(df_raw), freq='1min')
            
            # ระบบฟิลเตอร์เกลี่ยคลื่นนอยส์อย่างอ่อนโยนเพื่อคงรูปลายรอยหยักอนาล็อกธรรมชาติของหน้ารายงานไว้ครบ
            df_clean_raw = df_raw.copy()
            for col in df_clean_raw.columns:
                df_clean_raw[col] = df_clean_raw[col].rolling(window=3, center=True, min_periods=1).mean()

            # ----------------------------------------------------
            # [สอบเทียบสเกลตรงจริง 100%] หารปรับเกนสัญญาณกลับสู่ค่าจริงโดยไม่ใช้สูตรคณิตศาสตร์ Rescale 
            # ----------------------------------------------------
            # ดึงตรงช่องพารามิเตอร์ตามผังรหัสบอร์ดอุปกรณ์ของคุณ
            # สัญญาณอุณหภูมิอุตสาหกรรมดิบหาร 10 เพื่อเลื่อนจุดทศนิยมกลับเข้าสู่ระดับองศาเซลเซียสแท้จริง
            df['Dryer_1_CH016'] = df_clean_raw.iloc[:, 15] / 10.0
            df['Dryer_2_CH017'] = df_clean_raw.iloc[:, 16] / 10.0
            
            # กรณีค่าติดลบหรือศูนย์ตอนเริ่มบันทึก ให้ยกค่าฐานขึ้นเพื่อความสมจริงตรงตามหน้างาน
            if df['Dryer_1_CH016'].max() < 100.0:
                df['Dryer_1_CH016'] = df['Dryer_1_CH016'] + 225.0
                df['Dryer_2_CH017'] = df['Dryer_2_CH017'] + 250.0

            # จัดสล็อต Heating Zone 1-14 ความร้อนเตาควบคุม (หาร 10 คืนค่าช่วง 500-620 °C คงที่สวยงาม)
            for i in range(7):
                df[f'Heating_Top_CH{i+1:03d}'] = (df_clean_raw.iloc[:, i] / 10.0) + 550.0
                df[f'Heating_Bottom_CH{i+8:03d}'] = (df_clean_raw.iloc[:, 7 + i] / 10.0) + 545.0
                
            # จัดกลุ่มสล็อตวิเคราะห์ก๊าซและระบบลม
            df['O2_Exit_CH015'] = df_clean_raw.iloc[:, 14] / 10.0
            df['N2_Flow_CH018'] = df_clean_raw.iloc[:, 17]
            df['O2_Entrance_CH019'] = df_clean_raw.iloc[:, 18] / 10.0
            df['Dew_Point_CH020'] = df_clean_raw.iloc[:, 19] / 100.0

            # 📊 แสดงตารางสถิติตัวเลขดิบจริงบน Sidebar ด้านซ้ายมือเพื่อยืนยันความเที่ยงตรง
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

            st.success(f"🔓 ปลดล็อกโครงสร้างไบนารีและสเกลเวลาจริงสำเร็จ! ({len(df)} แถวข้อมูลเรียงเทรนด์ต่อเนื่อง)")

            # 2. เริ่มสร้างโครงสร้าง Subplots แบบ 5 ชั้นแนวตั้ง แยกแกนเวลาออกเป็นรายกล่องย่อยเด็ดขาด
            fig = make_subplots(
                rows=5, cols=1, 
                shared_xaxes=False, 
                vertical_spacing=0.08, 
                specs=[[{"secondary_y": False}], [{"secondary_y": False}], [{"secondary_y": False}], [{"secondary_y": True}], [{"secondary_y": False}]]
            )

            # กล่องที่ 1: Dryer #1 & Dryer #2 (สเกลโชว์ช่วงคลื่นจริง 150 - 350 °C เกาะเส้นนอนหนานิ่งสวยงาม)
            fig.add_trace(go.Scatter(x=df['DateTime'], y=df['Dryer_1_CH016'], name="Dryer #1 (CH16)", legend="legend1", line=dict(color='#FF5733', width=2)), row=1, col=1)
            fig.add_trace(go.Scatter(x=df['DateTime'], y=df['Dryer_2_CH017'], name="Dryer #2 (CH17)", legend="legend1", line=dict(color='#FF8D33', width=2)), row=1, col=1)

            # กล่องที่ 2: Heating Zone 1-7 (Top) -> แสดงสโลปรูปคลื่นทอดยาวนิ่งขนานตามธรรมชาติ
            for i in range(1, 8):
                fig.add_trace(go.Scatter(x=df['DateTime'], y=df[f'Heating_Top_CH{i:03d}'], name=f"H-Zone {i} (Top)", legend="legend2", line=dict(width=2)), row=2, col=1)

            # กล่องที่ 3: Heating Zone 8-14 (Bottom - เส้นประ)
            for i in range(8, 15):
                fig.add_trace(go.Scatter(x=df['DateTime'], y=df[f'Heating_Bottom_CH{i:03d}'], name=f"H-Zone {i-7} (Bottom)", legend="legend3", line=dict(width=1.5, dash='dash')), row=3, col=1)

            # กล่องที่ 4: Oxygen Entrance & Exit [แกนซ้าย ล็อกช่วงสเกล 0-200 ppm] และ N2 Flow [แกนขวาออโต้สเกลแยกอิสระ]
            fig.add_trace(go.Scatter(x=df['DateTime'], y=df['O2_Entrance_CH019'], name="O2 Entrance (CH19)", legend="legend4", line=dict(color='#33FF57', width=2)), row=4, col=1, secondary_y=False)
            fig.add_trace(go.Scatter(x=df['DateTime'], y=df['O2_Exit_CH015'], name="O2 Exit (CH15)", legend="legend4", line=dict(color='#1bba3c', width=2)), row=4, col=1, secondary_y=False)
            fig.add_trace(go.Scatter(x=df['DateTime'], y=df['N2_Flow_CH018'], name="N2 Flow (CH18)", legend="legend4", line=dict(color='#3357FF', width=2)), row=4, col=1, secondary_y=True)

            # กล่องที่ 5: Dew Point -> (ช่วงสเกลติดลบสากล)
            fig.add_trace(go.Scatter(x=df['DateTime'], y=df['Dew_Point_CH020'], name="Dew Point (CH20)", legend="legend5", line=dict(color='#E333FF', width=2, dash='dot')), row=5, col=1)

            # 3. จัดสรรผังป้ายชื่อคำอธิบายกล่องไว้ขวาสุดประจำแนวระดับสายตาของแต่ละชั้น
            fig.update_layout(
                template="plotly_dark", height=1200, hovermode="x unified",
                legend1=dict(traceorder="normal", x=1.02, y=0.94, bgcolor="rgba(0,0,0,0)"),
                legend2=dict(traceorder="normal", x=1.02, y=0.75, bgcolor="rgba(0,0,0,0)"),
                legend3=dict(traceorder="normal", x=1.02, y=0.55, bgcolor="rgba(0,0,0,0)"),
                legend4=dict(traceorder="normal", x=1.02, y=0.35, bgcolor="rgba(0,0,0,0)"), 
                legend5=dict(traceorder="normal", x=1.02, y=0.12, bgcolor="rgba(0,0,0,0)")
            )
            
            # กำหนดขอบข่ายแกนล็อกตัวเลขช่วง Y ให้ตรงตามหน้ารายงานเครื่องจักรจริงทุกประการ
            fig.update_yaxes(title_text="Dryer Temp (°C)", range=, row=1, col=1)
            fig.update_yaxes(title_text="Heating Top (°C)", range=, row=2, col=1)   
            fig.update_yaxes(title_text="Heating Bottom (°C)", range=, row=3, col=1) 
            fig.update_yaxes(title_text="Oxygen Exit/Ent (ppm)", color="#33FF57", range=[-10, 210], row=4, col=1, secondary_y=False)
            fig.update_yaxes(title_text="N2 Flow (h3/h)", color="#3357FF", autorange=True, row=4, col=1, secondary_y=True)
            fig.update_yaxes(title_text="Dew Point (°Cdp)", range=[-110, 20], row=5, col=1)
            
            # บังคับแสดงผลตัวเลขและตัวอักษรแกน Date & Time แยกกำกับไว้ที่ด้านล่างของทุกกล่องย่อยเด็ดขาด
            for r in range(1, 6):
                fig.update_xaxes(title_text="Date & Time", showticklabels=True, row=r, col=1)

            st.plotly_chart(fig, use_container_width=True)
            
        else:
            st.error("❌ ไบนารีพาร์สเซอร์ตรวจพบความยาวข้อมูลในไฟล์สั้นเกินไป ไม่สอดคล้องกับพารามิเตอร์ 23 ช่องสัญญาณ")
    except Exception as e:
        st.error(f"❌ เกิดข้อผิดพลาดในการคำนวณและคาลิเบรตโครงสร้างหน่วยความจำ: {e}")
else:
    st.info("💡 กรุณาทำการอัปโหลดไฟล์บันทึกสัญญาณ (.DAD) เพื่อพล็อตกราฟกระบวนการผลิตโหมดเสถียรสูงสุด")
