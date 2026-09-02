import subprocess
import sys

# ตรวจสอบและติดตั้ง library อัตโนมัติหากยังไม่มีในระบบ
def install_package(package_name):
    try:
        __import__(package_name)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])

# ตรวจสอบตัวที่จำเป็น
install_package("pandas")
install_package("plotly")
install_package("openpyxl")

import streamlit as st
import pandas as pd
import plotly.express as px

st.title("📊 DAD File Interactive Graph Viewer")

# 1. กล่องอัปโหลดไฟล์ผ่านหน้าเว็บ Streamlit
uploaded_file = st.file_uploader("อัปโหลดไฟล์ .DAD หรือ .DAT ของคุณที่นี่", type=["dad", "dat"])

if uploaded_file is not None:
    try:
        # ลองโหลดข้อมูลแบบคั่นด้วยช่องว่าง (Space/Tab)
        df = pd.read_csv(uploaded_file, sep=r'\s+', engine='python')
    except Exception:
        # ถ้าพัง ลองโหลดแบบคั่นด้วย Comma
        uploaded_file.seek(0)
        df = pd.read_csv(uploaded_file)
        
    st.success("โหลดข้อมูลสำเร็จ!")
    
    # แสดงตัวอย่างข้อมูล
    with st.expander("🔍 ดูตัวอย่างข้อมูลในไฟล์ (5 แถวแรก)"):
        st.write(df.head())
        
    # 2. ให้ผู้ใช้เลือกคอลัมน์แกน X และ Y จากหน้าเว็บได้เอง
    columns = df.columns.tolist()
    
    col1, col2 = st.columns(2)
    with col1:
        x_axis = st.selectbox("เลือกคอลัมน์สำหรับแกน X", options=columns, index=0)
    with col2:
        y_axis = st.selectbox("เลือกคอลัมน์สำหรับแกน Y", options=columns, index=min(1, len(columns)-1))
        
    # 3. สร้างและแสดงผล Interactive Graph
    fig = px.line(
        df, 
        x=x_axis, 
        y=y_axis, 
        title=f"กราฟความสัมพันธ์ระหว่าง {y_axis} และ {x_axis}",
        template="plotly_dark"
    )
    
    fig.update_layout(hovermode="x unified")
    
    # แสดงกราฟบน Streamlit
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("💡 กรุณาอัปโหลดไฟล์ .DAD เพื่อเริ่มต้นพล็อตกราฟ")
