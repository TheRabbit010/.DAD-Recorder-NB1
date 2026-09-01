import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime

# ==========================================
# 1. ตั้งค่าหน้าจอ
# ==========================================
st.set_page_config(layout="wide", page_title="Yokogawa .DAD Binary Tuner")
st.title("🛠️ เครื่องมือปรับจูนและสกัดข้อมูลไฟล์ .DAD")
st.markdown("""
**วิธีใช้งาน:**
1. อัปโหลดไฟล์ .DAD
2. สังเกตตารางด้านล่าง หากข้อมูล **"ไหลเฉียงข้ามคอลัมน์"** ให้ลองปรับค่า **ความกว้างบรรทัด** ด้านซ้ายมือ (ลอง 44, 46, 48 หรือ 90, 92)
3. ปรับจนกว่าค่าอุณหภูมิ (เช่น 580-600°C) จะเรียงตรงดิ่งอยู่ในคอลัมน์เดียวกัน
4. หากตัวเลขเรียงตรงแล้ว แต่ค่าดูแปลกๆ ให้ลองขยับ **Header Offset** (ทีละ 2)
5. เมื่อข้อมูลตรงเป๊ะแล้ว กดปุ่มดาวน์โหลด CSV ได้เลย!
""")

def clear_data_state():
    if "converted_df" in st.session_state:
        del st.session_state["converted_df"]

# ==========================================
# 2. แถบตั้งค่าด้านข้าง (Tuner Tools)
# ==========================================
st.sidebar.header("⚙️ ปรับจูนโครงสร้างไฟล์")
st.sidebar.markdown("ปรับค่าด้านล่าง ตารางจะอัปเดตให้ดูทันที!")

header_offset = st.sidebar.number_input("1. Header Offset (เริ่มอ่านที่ไบต์)", min_value=0, max_value=8192, value=512, step=2)
total_channels = st.sidebar.number_input("2. ความกว้างบรรทัด (Total Channels)", min_value=10, max_value=200, value=46, step=1)
skip_channels = st.sidebar.number_input("3. ตัดข้อมูลส่วนหัวบรรทัดทิ้ง (Skip Ch.)", min_value=0, max_value=20, value=0, step=1)
scale_divider = st.sidebar.number_input("4. ตัวหารทศนิยม (Scale)", min_value=1.0, max_value=100.0, value=10.0, step=1.0)

# ==========================================
# 3. ฟังก์ชันดึงเวลา
# ==========================================
def extract_start_time_from_filename(filename):
    matches = re.findall(r'\d{6}', filename)
    if len(matches) >= 2:
        d_str, t_str = matches[-2], matches[-1]
        p1, p2, p3 = int(d_str[:2]), int(d_str[2:4]), int(d_str[4:6])
        hh, mm, ss = int(t_str[:2]), int(t_str[2:4]), int(t_str[4:6])
        if 20 <= p1 <= 35: year, month, day = 2000 + p1, p2, p3
        elif 20 <= p3 <= 35: day, month, year = p1, p2, 2000 + p3
        else: year, month, day = 2000 + p1, p2, p3
        try: return datetime(year, month, day, hh, mm, ss)
        except ValueError: pass
    return pd.to_datetime("today").replace(microsecond=0)

# ==========================================
# 4. อัปโหลดและประมวลผล
# ==========================================
uploaded_files = st.file_uploader("อัปโหลดไฟล์ .DAD ที่นี่", type=["dad", "DAD"], accept_multiple_files=True)

if uploaded_files:
    all_dfs = []
    
    with st.spinner("กำลังประมวลผลและสร้างตาราง..."):
        for file in uploaded_files:
            try:
                start_dt = extract_start_time_from_filename(file.name)
                
                binary_data = file.read()
                
                # ตรวจสอบขนาดไฟล์ก่อนอ่าน
                if len(binary_data) <= header_offset:
                    st.warning(f"ไฟล์ {file.name} มีขนาดเล็กกว่า Header Offset ที่ตั้งไว้")
                    continue
                    
                raw_signals = np.frombuffer(binary_data, dtype=np.dtype(">i2"), offset=header_offset).astype(float)
                
                points_per_channel = len(raw_signals) // total_channels
                if points_per_channel == 0: continue

                usable_points = points_per_channel * total_channels
                
                # อ่านแบบเรียงบรรทัด (order='C')
                reshaped_data = raw_signals[:usable_points].reshape((points_per_channel, total_channels), order='C')
                reshaped_data = reshaped_data / scale_divider

                # สร้างชื่อคอลัมน์
                col_names = [f"CH_{str(i+1).zfill(3)}" for i in range(total_channels - skip_channels)]
                
                # ตัดคอลัมน์ที่ไม่ต้องการออกจากด้านหน้า (ถ้ามีการตั้งค่า Skip)
                data_to_df = reshaped_data[:, skip_channels:]
                
                df_single = pd.DataFrame(data_to_df, columns=col_names)
                
                # สร้างคอลัมน์ วัน เวลา และ sec 
                time_axis = pd.date_range(start=start_dt, periods=points_per_channel, freq="10s")
                df_single.insert(0, "sec", 0.0)
                df_single.insert(0, "Time", time_axis.strftime('%H:%M:%S'))
                df_single.insert(0, "Date", time_axis.strftime('%Y/%m/%d'))
                df_single.insert(0, "Datetime", time_axis.strftime('%Y-%m-%d %H:%M:%S'))
                
                all_dfs.append(df_single)
                
            except Exception as e:
                st.error(f"❌ เกิดข้อผิดพลาดในการอ่านไฟล์ {file.name}: {e}")

        if all_dfs:
            full_df = pd.concat(all_dfs, ignore_index=True)
            full_df = full_df.drop_duplicates(subset=["Datetime"]).reset_index(drop=True)
            
            st.success("✅ แปลงไฟล์สำเร็จ! ลองเลื่อนดูตารางด้านล่างว่าคอลัมน์ตรงหรือยังครับ")
            
            st.divider()
            st.subheader("📊 พรีวิวตารางข้อมูลดิบ (Tuner Preview)")
            # แสดงข้อมูลเพื่อเช็คความตรงของคอลัมน์
            st.dataframe(full_df.head(100), use_container_width=True)

            csv_data = full_df.to_csv(index=False).encode('utf-8-sig')
            
            st.download_button(
                label="📥 ดาวน์โหลดไฟล์ CSV ที่ปรับจูนแล้ว",
                data=csv_data,
                file_name=f"DAD_Tuned_Data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                type="primary",
                use_container_width=True
            )
