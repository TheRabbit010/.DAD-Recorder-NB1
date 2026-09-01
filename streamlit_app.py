import struct
import numpy as np
import pandas as pd

# 1. กำหนดชื่อไฟล์ดิบ .DAD และไฟล์ผลลัพธ์
dad_file_path = "data_test.DAD"    # <--- ใส่ชื่อไฟล์ .DAD ของคุณตรงนี้
output_csv = "decoded_binary.csv"
output_xlsx = "decoded_binary.xlsx"

def decode_dad_binary(file_path):
    print(f"กำลังเปิดอ่านโครงสร้างไฟล์ Binary: {file_path}")
    
    try:
        # เปิดไฟล์ดิบในโหมดอ่าน Binary
        with open(file_path, "rb") as f:
            binary_data = f.read()
        
        file_size = len(binary_data)
        print(f"ขนาดไฟล์ดิบทั้งหมด: {file_size} ไบต์")
        
        # ตามหลักสากลของไฟล์ประเภทเครื่องวัด อัตราส่วน 1 แถวข้อมูล (Timestamp + แชนเนลวัด)
        # มักจะจัดเก็บในรูปแบบ 4-byte float หรือ 8-byte double
        # โค้ดนี้จะจำลองการดึงค่าดิบออกมาทีละ 4 ไบต์
        chunk_size = 4 
        records = []
        
        # ทำการวนลูปสแกนข้อมูลตั้งแต่ต้นจนจบไฟล์
        for offset in range(0, file_size, chunk_size):
            chunk = binary_data[offset : offset + chunk_size]
            
            # ตรวจสอบว่าไบต์ครบขนาดล็อกหรือไม่
            if len(chunk) < chunk_size:
                break
                
            try:
                # ลองแปลงไบต์ดิบเป็นเลขทศนิยมความละเอียดเดี่ยว (Single-precision float)
                # ใช้สัญลักษณ์ '<f' สำหรับ Little-endian หรือ '>f' สำหรับ Big-endian ยี่ห้อ Yokogawa
                float_val = struct.unpack('<f', chunk)[0]
            except Exception:
                float_val = np.nan # หากไบต์ส่วนนั้นเป็นตัวอักษรไม่ใช่ตัวเลข
                
            # เก็บบันทึกข้อมูลดิบแยกตามพิกัดตำแหน่งเพื่อตรวจสอบ (Offset Location)
            records.append({
                "Byte_Offset": offset,
                "Raw_Hex": chunk.hex().upper(),
                "Interpreted_Float": float_val
            })
            
        # 2. แปลงผลลัพธ์ข้อมูลดิบเป็น Pandas DataFrame
        df = pd.DataFrame(records)
        
        # 3. เซฟไฟล์ออกเป็น CSV และ Excel 
        df.to_csv(output_csv, index=False, encoding="utf-8-sig")
        df.to_excel(output_xlsx, index=False)
        
        print("\n=== การแปลงโครงสร้างดิบเสร็จสิ้น ===")
        print(f"บันทึกไฟล์ CSV ดิบเรียบร้อยที่: {output_csv}")
        print(f"บันทึกไฟล์ Excel ดิบเรียบร้อยที่: {output_xlsx}")
        print("คำแนะนำ: เปิดไฟล์ Excel เพื่อสังเกตจุดเริ่มต้นของกลุ่มตัวเลขที่สอดคล้องกับค่าอุณหภูมิหน้าจอของคุณ")
        
    except FileNotFoundError:
        print(f"ไม่พบไฟล์ในระบบ โปรดตรวจสอบว่าไฟล์ชื่อ '{file_path}' อยู่ในโฟลเดอร์เดียวกับสคริปต์นี้แล้ว")
    except Exception as e:
        print(f"เกิดข้อผิดพลาดในการแกะ Binary: {e}")

# รันฟังก์ชันแกะไฟล์
decode_dad_binary(dad_file_path)
