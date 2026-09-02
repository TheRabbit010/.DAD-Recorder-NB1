import subprocess
import sys

# ตรวจสอบและติดตั้ง library อัตโนมัติหากยังไม่มีในระบบ
def install_package(package_name):
    try:
        __import__(package_name)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])

install_package("pandas")
install_package("plotly")
install_package("openpyxl")

import streamlit as st
import pandas as pd
import plotly.express as px
import io

st.title("📊 DAD File Interactive Graph Viewer")

uploaded_file = st.file_uploader("อัปโหลดไฟล์ .DAD หรือ .DAT ของคุณที่นี่", type=["dad", "dat"])

if uploaded_file is not None:
    df = None
    
    # ดึงข้อมูลดิบในรูปของ Bytes เผื่อกรณีเกิด Error จะได้ใช้ซ้ำได้
    file_bytes = uploaded_file.read()
    
    # รายชื่อการเข้ารหัส (Encodings) ที่จะลองสุ่มเปิดเพื่อแก้ UnicodeDecodeError
    encodings_to_try = ['utf-8', 'cp1252', 'tis-620', 'latin1', 'utf-16']
    
    # พยายามอ่านไฟล์ข้อความด้วย Encoding แบบต่างๆ
    for encoding in encodings_to_try:
        try:
            # แปลง Bytes กลับเป็น String บัฟเฟอร์
            string_data = file_bytes.decode(encoding)
            string_io = io.StringIO(string_data)
            
            # ลองโหลดแบบคั่นด้วยช่องว่าง (Space/Tab)
            df = pd.read_csv(string_io, sep=r'\s+', engine='python')
            
            # ตรวจสอบว่าได้คอลัมน์และข้อมูลมาจริงไหม
            if len(df.columns) >= 1 and len(df) > 0:
                st.success(f"加 โหลดข้อมูลสำเร็จด้วยรหัสภาษา: {encoding}")
                break
        except Exception:
            # ถ้าวิธีแรกพัง ลองแบบคั่นด้วย Comma
            try:
                string_io = io.StringIO(string_data)
                df = pd.read_csv(string_io)
                if len(df.columns) >= 1 and len(df) > 0:
                    st.success(f"加 โหลดข้อมูลสำเร็จด้วยรหัสภาษา (Comma): {encoding}")
                    break
            except Exception:
                continue

    # บล็อกกรณีฉุกเฉิน: ถ้าไฟล์นั้นเป็นไฟล์ Binary (ไม่สามารถ decode เป็น text ได้เลย)
    if df is None:
        try:
            # พยายามเปิดอ่านเป็นตารางเลขฐาน 16 หรือโครงสร้าง Binary แบบกว้างๆ
            bytes_io = io.BytesIO(file_bytes)
            df = pd.read_csv(bytes_io, sep=r'\s+', engine='python', on_bad_lines='skip')
            st.warning("⚠️ ไฟล์ของคุณอาจไม่ใช่ข้อความธรรมดา (Binary File) ระบบกำลังพยายามจัดรูปตารางแบบจำลอง")
        except Exception as e:
            st.error(f"❌ ไม่สามารถอ่านไฟล์นี้ได้: โครงสร้างไฟล์ไม่รองรับตารางข้อความมาตรฐาน")

    # ส่วนแสดงผลกราฟ (ทำงานเมื่อดึง DataFrame สำเร็จ)
    if df is not None and not df.empty:
        with st.expander("🔍 ดูตัวอย่างข้อมูลในไฟล์ (5 แถวแรก)"):
            st.write(df.head())
            
        columns = df.columns.tolist()
        
        col1, col2 = st.columns(2)
        with col1:
            x_axis = st.selectbox("เลือกคอลัมน์สำหรับแกน X", options=columns, index=0)
        with col2:
            y_axis = st.selectbox("เลือกคอลัมน์สำหรับแกน Y", options=columns, index=min(1, len(columns)-1))
            
        try:
            # บังคับแปลงข้อมูลในคอลัมน์ที่เลือกให้เป็นตัวเลข (ถ้าแปลงไม่ได้จะกลายเป็น NaN)
            df_plot = df.copy()
            df_plot[x_axis] = pd.to_numeric(df_plot[x_axis], errors='coerce')
            df_plot[y_axis] = pd.to_numeric(df_plot[y_axis], errors='coerce')
            df_plot = df_plot.dropna(subset=[x_axis, y_axis])

            fig = px.line(
                df_plot, 
                x=x_axis, 
                y=y_axis, 
                title=f"กราฟความสัมพันธ์ระหว่าง {y_axis} และ {x_axis}",
                template="plotly_dark"
            )
            fig.update_layout(hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)
        except Exception as graph_err:
            st.error(f"ไม่สามารถพล็อตกราฟจากคอลัมน์ที่เลือกได้เนื่องจากข้อมูลไม่ใช่ตัวเลข: {graph_err}")
else:
    st.info("💡 กรุณาอัปโหลดไฟล์ .DAD เพื่อเริ่มต้นพล็อตกราฟ")
