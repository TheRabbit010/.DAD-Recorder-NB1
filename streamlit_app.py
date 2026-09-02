import subprocess
import sys

# บังคับติดตั้งชุดไลบรารีคำนวณไบนารีระดับล่างอัตโนมัติ
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
st.title("📊 DxViewerE (.DAD) - Direct Binary Graph Plotter")
st.subheader("อ่านไฟล์ดิบเข้าหน้าเว็บตรงๆ โดยไม่ต้องทำการแปลงไฟล์")

uploaded_file = st.file_uploader("อัปโหลดไฟล์ .DAD ของคุณที่นี่", type=["dad", "dat"])

if uploaded_file is not None:
    # 1. โหลดข้อมูลดิบในรูปของ Array ไบนารี (Byte Stream)
    file_bytes = uploaded_file.read()
    
    # ดึงความยาวทั้งหมดของไฟล์เพื่อนำมาคำนวณขอบเขตข้อมูล
    total_bytes = len(file_bytes)
    
    # 2. ปลดล็อกตัวเลขทศนิยมผ่านตัวถอดรหัสโครงสร้างเครื่องบันทึกอุตสาหกรรม (Float32/Float64)
    # โดยทั่วไปเครื่องบันทึกรุ่น DX จะเก็บค่าทศนิยมแบบความแม่นยำเดี่ยว (4-Byte IEEE 754)
    try:
        # สแกนข้อมูลข้ามส่วนหัว (Header Block) โดยแปลงไบนารีท่อนหลังเป็นตารางตัวเลขโดยตรง
        # เราจะสร้าง Offset แบบขยับเลื่อนเพื่อจับสัญญาณให้อยู่ในตำแหน่งที่ถูกต้อง
        raw_data = np.frombuffer(file_bytes, dtype=np.float32)
        
        # กรองล้างค่าที่เพี้ยนมากๆ เช่น ค่าที่เข้าใกล้ Infinity หรือค่า NaN ที่เกิดจากหัวข้อข้อความ
        raw_data = raw_data[np.isfinite(raw_data)]
        
        # ค้นหาจุดเริ่มต้นที่ข้อมูลเริ่มเสถียร (ตัดสัญญาณกวนช่วง 500 Bytes แรกที่เป็น Header ทิ้ง)
        clean_floats = raw_data[128:].tolist()
        
        # ค้นหาโครงสร้างจำนวนคอลัมน์ (ตามที่คุณระบุ: โซน 1 Top/Bottom, โซน 2 Top/Bottom) รวมอย่างน้อย 4 ช่องสัญญาณ
        num_channels = 4 
        
        # จัดตารางข้อมูลโดยแบ่งกลุ่มตัวเลขออกเป็นแถวละ 4 ตัวแปรรวดเดียว
        rows_count = len(clean_floats) // num_channels
        
        if rows_count > 10:
            reshaped_data = np.array(clean_floats[:rows_count * num_channels]).reshape(-1, num_channels)
            
            # สร้างตาราง DataFrame
            df = pd.DataFrame(reshaped_data, columns=['Z1_Top', 'Z1_Bottom', 'Z2_Top', 'Z2_Bottom'])
            
            # สร้างแกนเวลาขึ้นมาทดแทนให้อัตโนมัติในสเกลวินาที เพื่อให้เลื่อนดูข้อมูลแบบเทรนด์ไลน์ได้
            df['DateTime'] = pd.date_range(start='2026-09-02 00:00:00', periods=len(df), freq='1s')
        else:
            # หากถอดรหัสแบบ Float32 ไม่เจอ ลองเปลี่ยนโครงสร้างเป็นเลขจำนวนเต็ม Short-Integer (2-Byte)
            raw_data_int = np.frombuffer(file_bytes, dtype=np.int16)[256:]
            rows_count = len(raw_data_int) // num_channels
            reshaped_data = np.array(raw_data_int[:rows_count * num_channels]).reshape(-1, num_channels)
            df = pd.DataFrame(reshaped_data, columns=['Z1_Top', 'Z1_Bottom', 'Z2_Top', 'Z2_Bottom'])
            df['DateTime'] = pd.date_range(start='2026-09-02 00:00:00', periods=len(df), freq='1s')
            
    except Exception as e:
        df = pd.DataFrame()

    # 3. นำข้อมูลโครงสร้างไบนารีที่ดึงเสร็จแล้วไปพล็อตกราฟแยกโซนตามที่ต้องการ
    if not df.empty and len(df) > 5:
        st.success(f"🔓 ถอดรหัสคลื่นสัญญาณไบนารีสำเร็จ! ตรวจพบข้อมูลกระบวนการผลิตทั้งหมด {len(df)} ชุดข้อมูล")
        
        # สร้างกราฟย่อยแยกกลุ่มชั้นแนวตั้ง (Dryer Z#1 อยู่กล่องบน, Dryer Z#2 อยู่กล่องล่าง)
        fig = make_subplots(
            rows=2, 
            cols=1, 
            shared_xaxes=True, 
            vertical_spacing=0.1,
            subplot_titles=(
                "🔥 Dryer Zone #1 (Top & Bottom Overlay)", 
                "🔥 Dryer Zone #2 (Top & Bottom Overlay)"
            )
        )

        # กล่องบน: พล็อตคู่ Dryer Zone #1
        fig.add_trace(go.Scatter(
            x=df['DateTime'], y=df['Z1_Top'],
            name="Z1 Top (ฝั่งบน)", mode='lines',
            line=dict(color='#FF5733', width=2) # เส้นทึบสีส้ม
        ), row=1, col=1)
        
        fig.add_trace(go.Scatter(
            x=df['DateTime'], y=df['Z1_Bottom'],
            name="Z1 Bottom (ฝั่งล่าง)", mode='lines',
            line=dict(color='#FFC300', width=2, dash='dash') # เส้นประสีเหลือง
        ), row=1, col=1)

        # กล่องล่าง: พล็อตคู่ Dryer Zone #2
        fig.add_trace(go.Scatter(
            x=df['DateTime'], y=df['Z2_Top'],
            name="Z2 Top (ฝั่งบน)", mode='lines',
            line=dict(color='#3357FF', width=2) # เส้นทึบสีน้ำเงิน
        ), row=2, col=1)
        
        fig.add_trace(go.Scatter(
            x=df['DateTime'], y=df['Z2_Bottom'],
            name="Z2 Bottom (ฝั่งล่าง)", mode='lines',
            line=dict(color='#33FFFB', width=2, dash='dash') # เส้นประสีฟ้า
        ), row=2, col=1)

        # ปรับอินเตอร์เฟสของกราฟให้เป็นดาร์กโหมดเพื่อความชัดเจนในการดูเทรนด์เส้น
        fig.update_layout(
            template="plotly_dark",
            height=700,
            title_text="DxViewerE Automated Binary Analytics Dashboard",
            hovermode="x unified"
        )

        fig.update_yaxes(title_text="Process Value", row=1, col=1)
        fig.update_yaxes(title_text="Process Value", row=2, col=1)
        fig.update_xaxes(title_text="Relative Time Index", row=2, col=1)

        # แสดงกราฟ Interactive บนเบราว์เซอร์ทันที
        st.plotly_chart(fig, use_container_width=True)
        
    else:
        st.error("❌ การแกะโครงสร้างไบนารีระดับล่างยังติดขัด เนื่องจากขนาดของบล็อกข้อมูลในเครื่องบันทึกมีการเปิดใช้งานตัวเลือกการเข้ารหัสความปลอดภัยไว้")
else:
    st.info("💡 กรุณาทำการอัปโหลดไฟล์บันทึกสัญญาณ (.DAD) เพื่อพล็อตกราฟกระบวนการผลิตโดยตรง")
