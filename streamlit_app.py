import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(layout="wide")
st.title("📊 โปรแกรมแยกกราฟแสดงสัญญาณ Waveform")
st.write("ระบบจะแยกแยะข้อมูลและพล็อตกราฟตามแต่ละแชนเนลโดยใช้ Auto-Scale")

# 1. รับไฟล์ .DAD จากผู้ใช้
uploaded_file = st.file_uploader("กรุณาเลือกไฟล์ .DAD ของคุณ", type=["dad"])

if uploaded_file is not None:
    try:
        # 2. อ่านข้อมูลดิบจากไฟล์
        binary_data = uploaded_file.read()
        raw_signals = np.frombuffer(binary_data, dtype=np.int16, offset=512)
        
        total_points = len(raw_signals)
        
        # 💡 คำนวณแยกสัญญาณเป็น 4 แชนเนล (เนื่องจากสัญญาณถูกบันทึกเรียงต่อกันหรือสลับกัน)
        # ตัวอย่างนี้เป็นการแบ่งซอยสัดส่วนข้อมูลออกเป็น 4 ส่วนเท่าๆ กันเพื่อพล็อตแยกกราฟ
        num_channels = 4
        points_per_channel = total_points // num_channels
        
        # หั่นข้อมูลดิบแบ่งให้แต่ละตัวแปร
        top_data = raw_signals[0 : points_per_channel]
        bottom_data = raw_signals[points_per_channel : points_per_channel * 2]
        n2_data = raw_signals[points_per_channel * 2 : points_per_channel * 3]
        ppm_o2_data = raw_signals[points_per_channel * 3 : points_per_channel * 4]
        
        # สร้างแกนเวลาจำลองให้ตรงกับความยาวสัญญาณของแต่ละช่อง
        time_axis = np.arange(points_per_channel)
        
        # 3. เริ่มต้นพล็อตกราฟแยกจากกันเด็ดขาด (Auto-Scale ทำงานอัตโนมัติแยกตามกราฟ)
        
        # กราฟที่ 1: Top
        st.subheader("📈 1. สัญญาณ Top")
        df_top = pd.DataFrame({"Time": time_axis, "Signal": top_data})
        fig_top = px.line(df_top, x="Time", y="Signal", title="Top Waveform", template="plotly_white")
        fig_top.update_yaxes(autorange=True) # บังคับใช้ Auto-scale แกน Y
        st.plotly_chart(fig_top, use_container_width=True)
        
        st.divider() # เส้นคั่นหน้าเว็บให้ดูง่ายขึ้น
        
        # กราฟที่ 2: Bottom
        st.subheader("📈 2. สัญญาณ Bottom")
        df_bottom = pd.DataFrame({"Time": time_axis, "Signal": bottom_data})
        fig_bottom = px.line(df_bottom, x="Time", y="Signal", title="Bottom Waveform", template="plotly_white")
        fig_bottom.update_yaxes(autorange=True)
        st.plotly_chart(fig_bottom, use_container_width=True)
        
        st.divider()
        
        # กราฟที่ 3: N2
        st.subheader("📈 3. สัญญาณ N2")
        df_n2 = pd.DataFrame({"Time": time_axis, "Signal": n2_data})
        fig_n2 = px.line(df_n2, x="Time", y="Signal", title="N2 Waveform", template="plotly_white")
        fig_n2.update_yaxes(autorange=True)
        st.plotly_chart(fig_n2, use_container_width=True)
        
        st.divider()
        
        # กราฟที่ 4: ppm O2
        st.subheader("📈 4. สัญญาณ ppm O2")
        df_o2 = pd.DataFrame({"Time": time_axis, "Signal": ppm_o2_data})
        fig_o2 = px.line(df_o2, x="Time", y="Signal", title="ppm O2 Waveform", template="plotly_white")
        fig_o2.update_yaxes(autorange=True)
        st.plotly_chart(fig_o2, use_container_width=True)
        
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการประมวลผลแยกกราฟ: {e}")
