import os
import re
import csv

def parse_report(file_path):
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    # 데이터 추출을 위한 정규표현식 패턴들
    sample_match = re.search(r"Sample: ([\w.]+)", content)
    target_match = re.search(r"\(Target: (\d+G)\)", content)
    duration_match = re.search(r"Total duration: (\d+) seconds", content)

    # 암호화된 파일 개수 세기 (Modified / Encrypted Files 섹션 아래 줄 수)
    enc_section = re.search(r"=== \[Modified / Encrypted Files \(Top 50\) ===\n(.*?)\n\n", content, re.S)
    enc_count = len(enc_section.group(1).strip().split('\n')) if enc_section and enc_section.group(1).strip() else 0

    # C2 통신(onion 주소 등) 시도 여부 확인
    c2_attempt = "O" if ".onion" in content or "dial tcp" in content else "X"

    # 랜섬노트 발견 여부
    note_found = "X" if "No ransom note found" in content else "O"

    return {
        "Sample": sample_match.group(1) if sample_match else "Unknown",
        "Target_Size": target_match.group(1) if target_match else "Unknown",
        "Duration_Sec": duration_match.group(1) if duration_match else "0",
        "Enc_Files": enc_count,
        "C2_Attempt": c2_attempt,
        "Ransom_Note": note_found
    }

def main():
    base_dir = "."  # ransom_lab 위치에서 실행
    log_dirs = [d for d in os.listdir(base_dir) if d.startswith("logs_") and os.path.isdir(d)]

    results = []
    for log_dir in log_dirs:
        dir_path = os.path.join(base_dir, log_dir)
        for file in os.listdir(dir_path):
            if file.startswith("report_") and file.endswith(".txt"):
                file_path = os.path.join(dir_path, file)
                try:
                    results.append(parse_report(file_path))
                except Exception as e:
                    print(f"Error parsing {file}: {e}")

    # CSV 결과 저장
    output_file = "total_analysis_result.csv"
    keys = ["Sample", "Target_Size", "Duration_Sec", "Enc_Files", "C2_Attempt", "Ransom_Note"]

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        dict_writer = csv.DictWriter(f, fieldnames=keys)
        dict_writer.writeheader()
        dict_writer.writerows(results)

    print(f"✅ 분석 완료! 결과가 '{output_file}'에 저장되었습니다.")

if __name__ == "__main__":
    main()
