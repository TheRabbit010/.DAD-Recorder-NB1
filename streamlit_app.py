import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime

# ==========================================
# 1. ตั้งค่าหน้าจอและการจัดการ State
# ==========================================
st.set_page_config(layout="centered", page_title="DAD to CSV Converter")
st.title("📄 DAD to CSV Converter")
st.markdown("อัปโหลดไฟล์ `.DAD` ระบบจะแปลงและเก็บข้อมูลไว้ในหน่วยความจำ พร้อมให้ดาวน์โหลดหรือใช้งานต่อ")

# ฟังก์ชันเคลียร์หน่วยความจำ หากมีการเปลี่ยน/ลบไฟล์ที่อัปโหลด
def clear_data_state():
    if "converted_df" in st.session_state:
        del st.session_state["converted_df"]

# ==========================================
# 2. ตั้งค่าโครงสร้างไฟล์ไบนารี .DAD
# ==========================================
HEADER_OFFSET = 512
TOTAL_CHANNELS = 90  
SCALE_DIVIDER = 10.0
DTYPE_STR = ">i2"

# ดึงเฉพาะคอลัมน์สำคัญ (MAX values)
col_mapping = {
    "Z#1 Top": 5, "Z#2 Top": 7, "Z#3 Top": 9, "Z#4 Top": 11, "Z#5 Top": 13, "Z#6 Top": 15, "Z#7 Top": 17,
    "Z#1 Bottom": 19, "Z#2 Bottom": 21, "Z#3 Bottom": 23, "Z#4 Bottom": 25, "Z#5 Bottom": 27, "Z#6 Bottom": 29, "Z#7 Bottom": 31,
    "O2 Exit": 33, "Dryer #1": 37, "Dryer #2": 39, 
    "N2 Flow": 85, "O2 Entrance": 89, "Dew Point": 87
}

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
# 3. ส่วนอัปโหลดและประมวลผลไฟล์
# ==========================================
# เมื่อไฟล์เปลี่ยน จะเรียก clear_data_state เพื่อเคลียร์ของเก่า
uploaded_files = st.file_uploader("อัปโหลดไฟล์ .DAD ที่นี่", type=["dad", "DAD"], accept_multiple_files=True, on_change=clear_data_state)

# ถ้ามีการอัปโหลดไฟล์ และยังไม่มีข้อมูลใน session_state ให้ทำการประมวลผล
if uploaded_files and "converted_df" not in st.session_state:
    all_dfs = []
    
    with st.spinner("กำลังประมวลผลไฟล์ กรุณารอสักครู่..."):
        for file in uploaded_files:
            try:
                start_dt = extract_start_time_from_filename(file.name)
                
                binary_data = file.read()
                raw_signals = np.frombuffer(binary_data, dtype=np.dtype(DTYPE_STR), offset=HEADER_OFFSET).astype(float)
                
                points_per_channel = len(raw_signals) // TOTAL_CHANNELS
                if points_per_channel == 0: continue

                usable_points = points_per_channel * TOTAL_CHANNELS
                reshaped_data = raw_signals[:usable_points].reshape((points_per_channel, TOTAL_CHANNELS), order='C')
                reshaped_data = reshaped_data / SCALE_DIVIDER

                data_dict = {}
                for ch_name, col_idx in col_mapping.items():
                    if col_idx < TOTAL_CHANNELS:
                        val_array = reshaped_data[:, col_idx]
                        
                        # ตัดค่า Error หรือเซนเซอร์หลุด
                        if "Top" in ch_name or "Bottom" in ch_name or "Dryer" in ch_name:
                            val_array = np.where((val_array < 0.0) | (val_array > 1500.0), np.nan, val_array)
                        else:
                            val_array = np.where((val_array < -100.0) | (val_array > 3500.0), np.nan, val_array)
                            
                        data_dict[ch_name] = val_array

                df_single = pd.DataFrame(data_dict)
                
                time_axis = pd.date_range(start=start_dt, periods=points_per_channel, freq="10s")
                df_single.insert(0, "Datetime", time_axis)
                
                all_dfs.append(df_single)
                
            except Exception as e:
                st.error(f"❌ เกิดข้อผิดพลาดในการอ่านไฟล์ {file.name}: {e}")

        # รวมไฟล์ทั้งหมดและบันทึกใส่หน่วยความจำ (Session State)
        if all_dfs:
            full_df = pd.concat(all_dfs, ignore_index=True)
            full_df = full_df.sort_values(by="Datetime").drop_duplicates(subset=["Datetime"]).reset_index(drop=True)
            
            # 🔥 เก็บ DataFrame ไว้ในหน่วยความจำที่ชื่อว่า converted_df
            st.session_state["converted_df"] = full_df

# ==========================================
# 4. แสดงผลและสร้างปุ่มดาวน์โหลด (ดึงค่าจากหน่วยความจำ)
# ==========================================
if "converted_df" in st.session_state:
    df_ready = st.session_state["converted_df"]
    
    st.success("✅ ประมวลผลและเก็บข้อมูลเข้าหน่วยความจำสำเร็จ!")
    st.info("💡 ขณะนี้ข้อมูลตารางถูกเก็บไว้ในตัวแปร `st.session_state['converted_df']` เรียบร้อยแล้ว (รอคำสั่งถัดไป)")
    
    st.divider()
    st.subheader("📊 พรีวิวข้อมูล")
    st.dataframe(df_ready.head(50), use_container_width=True)

    # แปลงเป็น CSV สำหรับเตรียมดาวน์โหลด
    csv_data = df_ready.to_csv(index=False).encode('utf-8-sig')
    
    # ปุ่มดาวน์โหลด
    st.download_button(
        label="📥 ดาวน์โหลดไฟล์ CSV",
        data=csv_data,
        file_name=f"DAD_Converted_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        type="primary",
        use_container_width=True
    )
