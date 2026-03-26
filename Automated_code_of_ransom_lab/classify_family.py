import os
import re
import csv

def get_family_info(report_path):
    if not os.path.exists(report_path):
        return "No_Report", "No_Ext"

    with open(report_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    # 1. 랜섬노트 파일명 추출
    note_match = re.search(r"([^/\s!]+![^!\s]+\.txt|README[^/\s]*\.html|HELP[^/\s]*\.txt)", content, re.IGNORECASE)
    note_name = note_match.group(1) if note_match else "Unknown_Note"

    # 2. 암호화 확장자 추출
    ext_match = re.search(r"\.([a-zA-Z0-9]{3,10})-\w{8}", content)
    extension = "." + ext_match.group(1) if ext_match else "Unknown_Ext"

    return note_name, extension

def main():
    input_file = 'total_analysis_result.csv'
    output_file = 'total_analysis_with_family.csv'

    results = []
    with open(input_file, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames + ['Ransom_Note_Name', 'Extension', 'Family']

        for row in reader:
            report_file = f"logs_{row['Target_Size']}/report_{row['Sample']}.txt"
            note, ext = get_family_info(report_file)

            row['Ransom_Note_Name'] = note
            row['Extension'] = ext
            row['Family'] = f"{note}_{ext}"
            results.append(row)

    with open(output_file, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print("✅ 패밀리 분류 데이터 생성 완료 (No Pandas 버전): total_analysis_with_family.csv")

if __name__ == "__main__":
    main()
