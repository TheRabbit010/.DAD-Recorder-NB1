"""
Yokogawa DX2000 .DAD Binary Extractor
Author: Your Name
Description: Extracts raw floating-point data from Yokogawa .DAD binary files 
             and exports them into structured Excel and CSV formats.
"""

import argparse
import os
import struct
import numpy as np
import pandas as pd


def parse_arguments():
    """จัดการ Argument สำหรับการรันผ่าน Command Line"""
    parser = argparse.ArgumentParser(
        description="Extract and convert Yokogawa .DAD binary files to CSV/Excel."
    )
    parser.add_argument(
        "-i",
        "--input",
        required=True,
        help="Path to the input .DAD binary file",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="extracted_output",
        help="Base name for the output files (without extension)",
    )
    parser.add_argument(
        "--endian",
        choices=["little", "big"],
        default="little",
        help="Byte order format: 'little' (<f) or 'big' (>f). Default is little.",
    )
    return parser.parse_args()


def decode_dad_binary(file_path, output_base, endian_setting):
    """ฟังก์ชันหลักในการอ่านและแกะโครงสร้างไฟล์ Binary"""
    if not os.path.exists(file_path):
        print(f"[Error] File not found: {file_path}")
        return

    print(f"[Info] Reading binary file: {file_path}")
    print(f"[Info] Byte Order (Endianness): {endian_setting}")

    # กำหนดรูปแบบโครงสร้าง Format ของ Library Struct
    fmt = "<f" if endian_setting == "little" else ">f"
    chunk_size = 4  # 4 bytes สำหรับ Single-precision float

    try:
        with open(file_path, "rb") as f:
            binary_data = f.read()

        file_size = len(binary_data)
        print(f"[Info] Total File Size: {file_size} bytes")

        records = []

        # วนลูปสแกนหาตำแหน่งและแปลงค่าดิบ
        for offset in range(0, file_size, chunk_size):
            chunk = binary_data[offset : offset + chunk_size]

            if len(chunk) < chunk_size:
                break

            try:
                # แปลง Byte ดิบเป็นเลขทศนิยม
                float_val = struct.unpack(fmt, chunk)[0]
                # กรองค่าที่ผิดปกติออก (เช่น ค่า NaN หรือสัญลักษณ์อินฟินิตี้จากข้อมูลขยะ)
                if np.isnan(float_val) or np.isinf(float_val):
                    float_val = None
            except Exception:
                float_val = None

            records.append(
                {
                    "Byte_Offset": offset,
                    "Raw_Hex": chunk.hex().upper(),
                    "Interpreted_Value": float_val,
                }
            )

        # แปลงข้อมูลเข้า Pandas DataFrame
        df = pd.DataFrame(records)

        # สร้างชื่อไฟล์ผลลัพธ์
        csv_filename = f"{output_base}.csv"
        xlsx_filename = f"{output_base}.xlsx"

        # บันทึกไฟล์
        df.to_csv(csv_filename, index=False, encoding="utf-8-sig")
        df.to_excel(xlsx_filename, index=False)

        print("\n=== Processing Complete ===")
        print(f"[Success] CSV exported to: {csv_filename}")
        print(f"[Success] Excel exported to: {xlsx_filename}")

    except Exception as e:
        print(f"[Error] An unexpected error occurred: {e}")


if __name__ == "__main__":
    args = parse_arguments()
    decode_dad_binary(args.input, args.output, args.endian)
