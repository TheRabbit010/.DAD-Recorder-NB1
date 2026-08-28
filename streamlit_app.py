import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(layout="wide")
st.title("📊 โปรแกรมอ่านและพล็อตกราฟไฟล์ .DAD")

# 1. สร้างช่องสำหรับอัปโหลดไฟล์ดิบ .DAD จากเครื่องผู้ใช้
uploaded_file = st.file_uploader("กรุณาเลือกไฟล์ .DAD ของคุณ", type=["dad"])

if uploaded_file is not None:
    try:
        # 2. อ่านข้อมูลดิบจากไฟล์ในรูปแบบ Binary (Byte) เข้ามาในหน่วยความจำ
        binary_data = uploaded_file.read()
        
        # 💡 [สำคัญ] ขั้นตอนการถอดรหัสสัญญาณไบนารี 
        # เนื่องจากไฟล์จากเครื่องวัด Yokogawa จะมีส่วนหัวไฟล์ (Header) และข้อมูลดิบที่ต่างกัน
        # ตัวอย่างนี้เป็นการสาธิตการดึงค่า Byte แปลงเป็นตัวเลขสัญญาน (เช่น 16-bit Short Integer)
        # คุณอาจต้องปรับค่า offset หรือชนิดข้อมูล (dtype) ตามโครงสร้างไฟล์จริงของคุณ
        
        raw_signals = np.frombuffer(binary_data, dtype=np.int16, offset=512) # สมมติว่า header ยาว 512 bytes
        
        # 3. จัดข้อมูลให้อยู่ในรูปแบบตาราง (Dataframe) เพื่อนำไปพล็อต
        # สมมติสร้างแกนเวลา (Time) และแกนสัญญาณพิกัดแรงดัน (Voltage)
        time_axis = np.arange(len(raw_signals))
        
        df = pd.DataFrame({
            "Time": time_axis,
            "Signal": raw_signals
        })
        
        # แสดงข้อมูล 5 แถวแรกที่ถอดรหัสได้
        st.subheader("📋 ตัวอย่างข้อมูลดิบที่อ่านได้จากไฟล์ .DAD")
        st.dataframe(df.head())
        
        # 4. พล็อตกราฟ Interactive ด้วย Plotly
        st.subheader("📈 กราฟแสดงสัญญาณ Waveform")
        fig = px.line(df, x="Time", y="Signal", title="Waveform from .DAD File")
        st.plotly_chart(fig, use_container_width=True)
        
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการอ่านไฟล์: {e}")
        st.info("คำแนะนำ: หากโครงสร้างไบนารีซับซ้อน แนะนำให้ใช้โปรแกรม DxViewerE แปลงไฟล์เป็น .CSV แล้วใช้คำสั่ง pd.read_csv() จะง่ายและแม่นยำที่สุดครับ")

