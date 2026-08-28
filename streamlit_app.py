import streamlit as st
import pandas as pd
import plotly.express as px

# ตั้งค่าหน้าเว็บเป็นแบบกว้างขยายเต็มหน้าจอ
st.set_page_config(layout="wide")

st.title("📊 โปรแกรมแยกกราฟแสดงสัญญาณแบบระบุโซนละเอียด (7 โซน)")
st.write("ระบบจะแยกกราฟกลุ่ม Top, Bottom, Dryer, N2, ppm O2, Debinder และ Dew Point ออกจากกันโดยอัตโนมัติ")

# ช่องสำหรับอัปโหลดไฟล์ข้อมูล (.csv หรือ .txt)
uploaded_file = st.file_uploader("กรุณาเลือกไฟล์ข้อมูลของคุณ", type=["csv", "txt"])

if uploaded_file is not None:
    try:
        # อ่านข้อมูลจากไฟล์เข้ามาในระบบ
        df = pd.read_csv(uploaded_file)
        
        # แสดงตารางข้อมูลให้ผู้ใช้ตรวจสอบความถูกต้อง
        st.subheader("📋 ตรวจสอบข้อมูลดิบในไฟล์")
        st.dataframe(df.head(3))
        
        all_columns = df.columns.tolist()
        
        # ค้นหาคอลัมน์แกน X (แกนเวลา) อัตโนมัติ
        default_x = [col for col in all_columns if 'time' in col.lower() or 'date' in col.lower()]
        x_axis = st.selectbox(
            "เลือกคอลัมน์สำหรับแกน X (แกนเวลา):", 
            all_columns, 
            index=all_columns.index(default_x) if default_x else 0
        )
        
        # ฟังก์ชันช่วยสร้างกราฟเพื่อลดความซ้ำซ้อนของโค้ด และบังคับใช้ Auto-scale แยกกัน
        def plot_zone_graph(title, columns_to_plot):
            if columns_to_plot:
                fig = px.line(df, x=x_axis, y=columns_to_plot, title=f"{title} Waveform (Auto-Scale)", template="plotly_white")
                fig.update_yaxes(autorange=True)
                fig.update_layout(legend_title_text='Signals', margin=dict(l=20, r=20, t=40, b=20))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info(f"💡 ไม่พบข้อมูลคอลัมน์สำหรับกลุ่ม {title} (คุณสามารถเลือกคอลัมน์เองได้ผ่านหน้าเว็บ)")

        # ==========================================
        # 1. โซน: Top Zones
        # ==========================================
        st.divider()
        st.subheader("📐 1. Top Zones")
        top_cols = [col for col in all_columns if 'top' in col.lower() or any(f'z{i}' in col.lower() for i in range(1, 8))]
        if not top_cols:
            top_cols = st.multiselect("เลือกสัญญาณสำหรับ Top Zones:", all_columns, default=None)
        plot_zone_graph("Top Zones", top_cols)

        # ==========================================
        # 2. โซน: Bottom Zones
        # ==========================================
        st.divider()
        st.subheader("📐 2. Bottom Zones")
        bot_cols = [col for col in all_columns if 'bot' in col.lower() or any(f'z{i}' in col.lower() for i in range(8, 15))]
        if not bot_cols:
            bot_cols = st.multiselect("เลือกสัญญาณสำหรับ Bottom Zones:", all_columns, default=None)
        plot_zone_graph("Bottom Zones", bot_cols)

        # ==========================================
        # 3. โซน: Dryer
        # ==========================================
        st.divider()
        st.subheader("🔥 3. Dryer")
        dryer_cols = [col for col in all_columns if 'dryer' in col.lower()]
        if not dryer_cols:
            dryer_cols = st.multiselect("เลือกสัญญาณสำหรับ Dryer:", all_columns, default=None)
        plot_zone_graph("Dryer", dryer_cols)

        # ==========================================
        # 4. โซน: N2 (Nitrogen)
        # ==========================================
        st.divider()
        st.subheader("💨 4. N2")
        n2_cols = [col for col in all_columns if 'n2' in col.lower() or 'nitrogen' in col.lower()]
        if not n2_cols:
            n2_cols = st.multiselect("เลือกสัญญาณสำหรับ N2:", all_columns, default=None)
        plot_zone_graph("N2", n2_cols)

        # ==========================================
        # 5. โซน: ppm O2 (Oxygen)
        # ==========================================
        st.divider()
        st.subheader("🧪 5. ppm O2")
        o2_cols = [col for col in all_columns if 'o2' in col.lower() or 'oxygen' in col.lower()]
        if not o2_cols:
            o2_cols = st.multiselect("เลือกสัญญาณสำหรับ ppm O2:", all_columns, default=None)
        plot_zone_graph("ppm O2", o2_cols)

        # ==========================================
        # 6. โซน: Debinder
        # ==========================================
        st.divider()
        st.subheader("⚙️ 6. Debinder")
        debinder_cols = [col for col in all_columns if 'debinder' in col.lower() or 'de-binder' in col.lower()]
        if not debinder_cols:
            debinder_cols = st.multiselect("เลือกสัญญาณสำหรับ Debinder:", all_columns, default=None)
        plot_zone_graph("Debinder", debinder_cols)

        # ==========================================
        # 7. โซน: Dew Point (เพิ่มใหม่)
        # ==========================================
        st.divider()
        st.subheader("💧 7. Dew Point")
        dew_cols = [col for col in all_columns if 'dew' in col.lower() or 'point' in col.lower()]
        if not dew_cols:
            dew_cols = st.multiselect("เลือกสัญญาณสำหรับ Dew Point:", all_columns, default=None)
        plot_zone_graph("Dew Point", dew_cols)

    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการประมวลผลไฟล์: {e}")
