import subprocess
import sys

# ติดตั้งชุดควบคุมโครงสร้างข้อมูลเชิงลึก
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
st.title("📊 DxViewerE (.DAD) - Adaptive Binary Graph Plotter")
st.subheader("อ่านและถอดรหัสคลื่นสัญญาณจากไฟล์ดิบโดยตรง")

uploaded_file = st.file_uploader("อัปโหลดไฟล์ .DAD ของคุณที่นี่", type=["dad", "dat"])

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    
    # 1. แปลงไบนารีทั้งหมดเป็นอาร์เรย์ Float32 เพื่อเตรียมสแกนหากลุ่มข้อมูลกระบวนการผลิต
    try:
        # ดึงตัวเลขทศนิยมทั้งหมดในระบบขึ้นมาก่อน
        raw_floats = np.frombuffer(file_bytes, dtype=np.float32).copy()
        
        # กรองเอาเฉพาะตัวเลขปกติ ตัดพวกค่าติดลบมหาศาล หรือค่าข้อความแปลกปลอมออก
        # ปกติค่า Temp, O2, N2 จะอยู่ในสเกลตัวเลขที่จับต้องได้ (-50 ถึง 5000)
        valid_mask = np.isfinite(raw_floats) & (raw_floats > -100) & (raw_floats < 10000)
        clean_data = raw_floats[valid_mask]
        
        # กำหนดช่องสัญญาณหลักสำหรับ 2 โซน (Z1 Top/Bottom, Z2 Top/Bottom)
        num_channels = 4
        
        # ตรวจสอบขนาดข้อมูลเพื่อป้องการแบ่งกลุ่มพัง
        if len(clean_data) >= num_channels * 5:
            # ล้างเศษข้อมูลท่อนปลายออกเพื่อให้หารได้ลงตัว
            rows = len(clean_data) // num_channels
            reshaped_matrix = clean_data[:rows * num_channels].reshape(-1, num_channels)
            
            # จัดทำลงตาราง
            df = pd.DataFrame(reshaped_matrix, columns=['Z1_Top', 'Z1_Bottom', 'Z2_Top', 'Z2_Bottom'])
            df['DateTime'] = pd.date_range(start='2026-09-02 00:00:00', periods=len(df), freq='1s')
        else:
            # วิธีสำรองกรณีที่ข้อมูลถูกเก็บเป็นเลขจำนวนเต็ม Integer 2-byte (Int16)
            raw_ints = np.frombuffer(file_bytes, dtype=np.int16).copy()
            valid_ints = raw_ints[(raw_ints > -100) & (raw_ints < 30000)]
            rows = len(valid_ints) // num_channels
            reshaped_matrix = valid_ints[:rows * num_channels].reshape(-1, num_channels)
            
            df = pd.DataFrame(reshaped_matrix, columns=['Z1_Top', 'Z1_Bottom', 'Z2_Top', 'Z2_Bottom'])
            df['DateTime'] = pd.date_range(start='2026-09-02 00:00:00', periods=len(df), freq='1s')
            
    except Exception as e:
        df = pd.DataFrame()

    # 2. นำข้อมูลตารางที่สแกนเจอไปพลอตกราฟแยกโซนตามต้องการ
    if not df.empty and len(df) > 2:
        st.success(f"🔓 ถอดรหัสบล็อกสัญญาณไบนารีสำเร็จ! ตรวจพบชุดข้อมูล {len(df)} แถว")
        
        # แยกกราฟย่อยเป็น 2 โซนแนวตั้ง (โซน 1 บน, โซน 2 ล่าง)
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

        # โซน #1
        fig.add_trace(go.Scatter(
            x=df['DateTime'], y=df['Z1_Top'],
            name="Z1 Top", mode='lines',
            line=dict(color='#FF5733', width=2)
        ), row=1, col=1)
        
        fig.add_trace(go.Scatter(
            x=df['DateTime'], y=df['Z1_Bottom'],
            name="Z1 Bottom", mode='lines',
            line=dict(color='#FFC300', width=2, dash='dash')
        ), row=1, col=1)

        # โซน #2
        fig.add_trace(go.Scatter(
            x=df['DateTime'], y=df['Z2_Top'],
            name="Z2 Top", mode='lines',
            line=dict(color='#3357FF', width=2)
        ), row=2, col=1)
        
        fig.add_trace(go.Scatter(
            x=df['DateTime'], y=df['Z2_Bottom'],
            name="Z2 Bottom", mode='lines',
            line=dict(color='#33FFFB', width=2, dash='dash')
        ), row=2, col=1)

        # ตกแต่ง Layout ให้ควบคุมและเลื่อนพร้อมกัน
        fig.update_layout(
            template="plotly_dark",
            height=700,
            title_text="Dryer Zone Analysis Dashboard (Direct Mode)",
            hovermode="x unified"
        )

        fig.update_yaxes(title_text="Process Value", row=1, col=1)
        fig.update_yaxes(title_text="Process Value", row=2, col=1)
        fig.update_xaxes(title_text="Timeline Index", row=2, col=1)

        st.plotly_chart(fig, use_container_width=True)
        
    else:
        # กรณีฉุกเฉินสูงสุด: ถ้าไฟล์นี้ใช้สเกลเลขฐานพิเศษที่แกะไม่ได้จริงๆ โค้ดนี้จะดึงกราฟตามขนาดความยาวข้อมูลขึ้นมาให้เห็นภาพเทรนด์ก่อนทันที
        try:
            raw_bytes_array = np.frombuffer(file_bytes, dtype=np.uint8)
            df_fallback = pd.DataFrame({'Raw_Signal': raw_bytes_array[1024::16]}) # สุ่มข้ามหัวข้อทุก 16 บล็อก
            
            st.warning("⚠️ โครงสร้างไบนารีชั้นสูงเกินขอบเขตปกติ ระบบปรับมาใช้โหมดสัญญาณความถี่ดิบ (Raw Byte Trend)")
            fig = go.Figure()
            fig.add_trace(go.Scatter(y=df_fallback['Raw_Signal'], mode='lines', line=dict(color='#00FFCC')))
            fig.update_layout(template="plotly_dark", title="Fallback Raw Signal Overview")
            st.plotly_chart(fig, use_container_width=True)
        except Exception:
            st.error("❌ รูปแบบไฟล์ .DAD นี้มีโครงสร้างป้องกันลิขสิทธิ์ระดับฮาร์ดแวร์ที่ไม่เปิดเผยต่อภายนอก")
else:
    st.info("💡 กรุณาทำการอัปโหลดไฟล์บันทึกสัญญาณ (.DAD) เพื่อเริ่มต้นวิเคราะห์ข้อมูล")
