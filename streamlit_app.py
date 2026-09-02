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
install_package("numpy")

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import re

st.set_page_config(layout="wide")
st.title("📊 DxViewerE (.DAD) - Robust Dryer Zone Plotter")
st.subheader("เวอร์ชันถอดรหัสไดนามิก - เลือกจัดกลุ่มช่องสัญญาณได้ด้วยตนเอง")

uploaded_file = st.file_uploader("อัปโหลดไฟล์ .DAD จากเครื่องบันทึก DxViewerE", type=["dad", "dat"])

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    
    # 1. พยายามถอดรหัสแบบยืดหยุ่นสูง เพื่อดึงตัวเลขทศนิยมออกมาให้ได้มากที่สุด
    decoded_text = file_bytes.decode('latin-1', errors='ignore')
    lines = decoded_text.splitlines()
    
    # ค้นหาแพทเทิร์น วันที่-เวลา
    datetime_pattern = r'(\d{4}[-/]\d{2}[-/]\d{2}\s+\d{2}:\d{2}:\d{2})'
    
    records = []
    max_cols = 0
    
    for line in lines:
        match = re.search(datetime_pattern, line)
        if match:
            dt_str = match.group(1)
            remaining_part = line[line.find(dt_str) + len(dt_str):]
            # ดึงตัวเลขทศนิยมหรือจำนวนเต็มทั้งหมดที่ต่อท้ายวันเวลา
            numbers = re.findall(r'[-+]?\d*\.\d+|\d+', remaining_part)
            if numbers:
                float_nums = [float(n) for n in numbers]
                max_cols = max(max_cols, len(float_nums))
                records.append([dt_str] + float_nums)

    # 2. นำข้อมูลที่ขูดมาได้สร้างเป็น DataFrame แบบยืดหยุ่นคอลัมน์
    if len(records) > 0:
        # สร้างชื่อคอลัมน์จำลองตามจำนวนตัวเลขที่มากที่สุดที่หาได้ในแต่ละบรรทัด
        col_names = ['DateTime'] + [f'Channel_{i+1}' for i in range(max_cols)]
        
        # ปรับความยาวของแถวให้เท่ากันเพื่อป้องกัน DataFrame พัง
        padded_records = []
        for r in records:
            dt = r[0]
            nums = r[1:]
            if len(nums) < max_cols:
                nums = nums + [None] * (max_cols - len(nums)) # เติมค่าว่างหากแถวสั้นเกินไป
            padded_records.append([dt] + nums[:max_cols])
            
        df = pd.DataFrame(padded_records, columns=col_names)
        df['DateTime'] = pd.to_datetime(df['DateTime'], errors='coerce')
        df = df.dropna(subset=['DateTime'])
    else:
        df = pd.DataFrame()

    # 3. หากมีข้อมูล ให้ผู้ใช้ทำการแมปปิ้งช่องสัญญาณผ่านอินเตอร์เฟสหน้าเว็บ
    if not df.empty:
        st.success(f"🔓 ดึงข้อมูลดิบสำเร็จ! ค้นพบสัญญาณตัวเลข {max_cols} ช่องสัญญาณ (ข้อมูลรวม {len(df)} แถว)")
        
        # กล่องเครื่องมือจับคู่คอลัมน์ด้านข้าง (Sidebar)
        st.sidebar.header("🛠️ เลือกแมปช่องสัญญาณ (Channel Mapping)")
        st.sidebar.write("จับคู่คอลัมน์จากไฟล์ดิบให้ตรงกับหัวข้อที่คุณต้องการดูบนกราฟ:")
        
        channels_options = df.columns.tolist()[1:] # เอาเฉพาะ Channel_1, Channel_2...
        
        # ตัวเลือกจับคู่สำหรับ Dryer Zone #1
        st.sidebar.markdown("---")
        st.sidebar.subheader("🔥 Dryer Zone #1")
        z1_top_col = st.sidebar.selectbox("Z1 Top (เส้นทึบ)", options=channels_options, index=0)
        z1_bottom_col = st.sidebar.selectbox("Z1 Bottom (เส้นประ)", options=channels_options, index=min(1, len(channels_options)-1))
        
        # ตัวเลือกจับคู่สำหรับ Dryer Zone #2
        st.sidebar.markdown("---")
        st.sidebar.subheader("🔥 Dryer Zone #2")
        z2_top_col = st.sidebar.selectbox("Z2 Top (เส้นทึบ)", options=channels_options, index=min(2, len(channels_options)-1))
        z2_bottom_col = st.sidebar.selectbox("Z2 Bottom (เส้นประ)", options=channels_options, index=min(3, len(channels_options)-1))

        # 4. พล็อตกราฟ Subplots ตามค่าที่ผู้ใช้แมปไว้
        fig = make_subplots(
            rows=2, 
            cols=1, 
            shared_xaxes=True, 
            vertical_spacing=0.1,
            subplot_titles=(
                f"📈 Dryer Zone #1 ({z1_top_col} vs {z1_bottom_col})", 
                f"📈 Dryer Zone #2 ({z2_top_col} vs {z2_bottom_col})"
            )
        )

        # แถวที่ 1: Dryer Zone #1
        fig.add_trace(go.Scatter(
            x=df['DateTime'], y=df[z1_top_col],
            name="Z1 Top", mode='lines',
            line=dict(color='#FF5733', width=2)
        ), row=1, col=1)
        
        fig.add_trace(go.Scatter(
            x=df['DateTime'], y=df[z1_bottom_col],
            name="Z1 Bottom", mode='lines',
            line=dict(color='#FFC300', width=2, dash='dash')
        ), row=1, col=1)

        # แถวที่ 2: Dryer Zone #2
        fig.add_trace(go.Scatter(
            x=df['DateTime'], y=df[z2_top_col],
            name="Z2 Top", mode='lines',
            line=dict(color='#3357FF', width=2)
        ), row=2, col=1)
        
        fig.add_trace(go.Scatter(
            x=df['DateTime'], y=df[z2_bottom_col],
            name="Z2 Bottom", mode='lines',
            line=dict(color='#33FFFB', width=2, dash='dash')
        ), row=2, col=1)

        # ตกแต่งโครงสร้างกราฟ
        fig.update_layout(
            template="plotly_dark",
            height=700,
            title_text="Dryer Process Analysis Dashboard (Custom Mapped)",
            hovermode="x unified"
        )

        fig.update_yaxes(title_text="Process Value", row=1, col=1)
        fig.update_yaxes(title_text="Process Value", row=2, col=1)
        fig.update_xaxes(title_text="Date & Time", row=2, col=1)

        # แสดงผลกราฟ
        st.plotly_chart(fig, use_container_width=True)
        
        # มีตารางข้อมูลให้เปิดตรวจทานดูด้านล่าง จะได้เห็นว่า Channel ไหนมีค่าเท่าไหร่บ้าง
        with st.expander("🔍 เปิดตรวจสอบตารางค่าข้อมูลดิบเพื่อช่วยในการจับคู่ (Raw Channels Preview)"):
            st.dataframe(df)

    else:
        st.error("❌ ระบบพยายามดึงข้อมูลอย่างสุดความสามารถแล้ว แต่โครงสร้างตัวเลขแบบเรียงแถวในไฟล์นี้มีการเข้ารหัสพิเศษ (Encrypted Binary) แนะนำให้เปิดไฟล์นี้ในโปรแกรม DxViewerE บนคอมพิวเตอร์ของคุณ แล้วเลือกเมนู File > Export/Save As เพื่อส่งข้อมูลออกเป็นไฟล์นามสกุล .CSV หรือ .TXT แทน จากนั้นจะพล็อตกราฟได้อย่างไม่มีปัญหาแน่นอนครับ")
else:
    st.info("💡 กรุณาอัปโหลดไฟล์ .DAD ของคุณเพื่อเริ่มต้นจัดกลุ่มวิเคราะห์ข้อมูลแยกโซน")
