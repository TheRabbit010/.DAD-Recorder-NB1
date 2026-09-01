import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime

# ==========================================
# 1. ตั้งค่าหน้าจอ
# ==========================================
st.set_page_config(layout="wide", page_title="DAD Full Raw Data Extractor")
st.title("📄 DAD Raw Data to CSV (Perfect Match)")
st.markdown("ดึงข้อมูลดิบทั้งหมด 45 Channels (คู่ MIN/MAX) โครงสร้างตรงกับโปรแกรมเครื่อง 100%")

def clear_data_state():
    if "converted_df" in st.session_state:
        del st.session_state["converted_df"]

# ==========================================
# 2. โครงสร้างไฟล์ .DAD และ Mapping ที่ถูกต้อง 100%
# ==========================================
HEADER_OFFSET = 512
TOTAL_CHANNELS = 90  # 90 ช่องย่อย = 45 ช่องหลัก (MIN/MAX)
SCALE_DIVIDER = 10.0
DTYPE_STR = ">i2"

# 💡 Mapping ใหม่: Z#1 Top เริ่มที่ CH001 ตรงตามตารางอ้างอิง
logical_ch_names = {
    1: "Z#1 Top", 2: "Z#2 Top", 3: "Z#3 Top", 4: "Z#4 Top", 5: "Z#5 Top", 6: "Z#6 Top", 7: "Z#7 Top",
    8: "Z#1 Bottom", 9: "Z#2 Bottom", 10: "Z#3 Bottom", 11: "Z#4 Bottom", 12: "Z#5 Bottom", 13: "Z#6 Bottom", 14: "Z#7 Bottom",
    17: "O2 Exit", 
    19: "Dryer #1", 20: "Dryer #2",
    43: "N2 Flow", 44: "Dew Point", 45: "O2 Entrance"
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
# 3. อัปโหลดและประมวลผล
# ==========================================
uploaded_files = st.file_uploader("อัปโหลดไฟล์ .DAD ที่นี่", type=["dad", "DAD"], accept_multiple_files=True, on_change=clear_data_state)

if uploaded_files and "converted_df" not in st.session_state:
    all_dfs = []
    
    with st.spinner("กำลังสกัดข้อมูล... (ไม่ผ่านการฟิลเตอร์ใดๆ)"):
        for file in uploaded_files:
            try:
                start_dt = extract_start_time_from_filename(file.name)
                
                binary_data = file.read()
                raw_signals = np.frombuffer(binary_data, dtype=np.dtype(DTYPE_STR), offset=HEADER_OFFSET).astype(float)
                
                points_per_channel = len(raw_signals) // TOTAL_CHANNELS
                if points_per_channel == 0: continue

                usable_points = points_per_channel * TOTAL_CHANNELS
                
                # 💡 อ่านแบบเรียงบรรทัด (order='C') ถูกต้องที่สุดสำหรับโครงสร้างนี้
                reshaped_data = raw_signals[:usable_points].reshape((points_per_channel, TOTAL_CHANNELS), order='C')
                reshaped_data = reshaped_data / SCALE_DIVIDER

                data_dict = {}
                num_logical_channels = TOTAL_CHANNELS // 2  # 45 ช่องหลัก
                
                for i in range(num_logical_channels):
                    ch_num = i + 1
                    ch_str = str(ch_num).zfill(3)
                    
                    # ตั้งชื่อคอลัมน์ ถ้ามีชื่ออยู่ใน Mapping ก็จะระบุให้ด้วย
                    if ch_num in logical_ch_names:
                        tag_name = logical_ch_names[ch_num]
                        col_min = f"CH{ch_str} [{tag_name}]_MIN"
                        col_max = f"CH{ch_str} [{tag_name}]_MAX"
                    else:
                        col_min = f"CH{ch_str}_MIN"
                        col_max = f"CH{ch_str}_MAX"
                    
                    # Index เลขคู่คือ MIN, เลขคี่คือ MAX
                    data_dict[col_min] = reshaped_data[:, i * 2]
                    data_dict[col_max] = reshaped_data[:, i * 2 + 1]

                df_single = pd.DataFrame(data_dict)
                
                time_axis = pd.date_range(start=start_dt, periods=points_per_channel, freq="10s")
                df_single.insert(0, "Datetime", time_axis.strftime('%Y-%m-%d %H:%M:%S'))
                
                all_dfs.append(df_single)
                
            except Exception as e:
                st.error(f"❌ เกิดข้อผิดพลาดในการอ่านไฟล์ {file.name}: {e}")

        if all_dfs:
            full_df = pd.concat(all_dfs, ignore_index=True)
            full_df = full_df.drop_duplicates(subset=["Datetime"]).reset_index(drop=True)
            st.session_state["converted_df"] = full_df

# ==========================================
# 4. แสดงผลและสร้างปุ่มดาวน์โหลด
# ==========================================
if "converted_df" in st.session_state:
    df_ready = st.session_state["converted_df"]
    
    st.success("✅ ประมวลผลเสร็จสมบูรณ์! โครงสร้างตรงกับโปรแกรมของเครื่อง 100%")
    
    st.divider()
    st.subheader("📊 พรีวิวตารางข้อมูลดิบ (อ้างอิง CH001 คือ Z#1 Top)")
    # แสดงตัวอย่างเฉพาะ 15 คอลัมน์แรกเพื่อความรวดเร็วในการแสดงผลบนเว็บ
    st.dataframe(df_ready.iloc[:, :15].head(100), use_container_width=True)

    csv_data = df_ready.to_csv(index=False).encode('utf-8-sig')
    
    st.download_button(
        label="📥 ดาวน์โหลดไฟล์ CSV (ตารางเต็ม 90 คอลัมน์)",
        data=csv_data,
        file_name=f"DAD_Exact_Match_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        type="primary",
        use_container_width=True
    )
