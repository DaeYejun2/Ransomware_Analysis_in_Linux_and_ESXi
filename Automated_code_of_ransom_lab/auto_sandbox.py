import os
import sys
import time
import subprocess
import csv
import argparse
from datetime import datetime, timezone
from vcenter_logger import VCenterLogger

# ==========================================
# ⚙️ 1. 인자(Argument) 처리 및 동적 환경 설정
# ==========================================
parser = argparse.ArgumentParser(description="Ransomware Auto Sandbox (Multi-Size Support)")
parser.add_argument('--size', type=str, required=True, help="더미 파일 크기 (예: 1G, 5G, 10G, 30G, 50G)")
args = parser.parse_args()

TARGET_SIZE = args.size
SNAPSHOT_NAME = f"clean_ready_{TARGET_SIZE}"  # 동적 스냅샷 이름
MAX_WAIT_SECONDS = 900  # 🌟 NEW: 랜섬웨어 실행 대기 시간 (50GB 암호화를 위해 15분으로 연장)

# ==========================================
# ⚙️ 2. 고정 환경 설정 및 동적 경로 할당
# ==========================================
VC_IP = "192.168.0.70"
VC_USER = "administrator@vsphere.local"
VC_PASSWORD = "Jinu138602#"  # 👈 비밀번호 수정!

JUMP_HOST = "jinu@192.168.0.62"
ESXI_IP = "root@192.168.0.57"
PROXMOX_VM_ID = "110"

LAB_DIR = "/root/ransom_lab"
SAMPLES_DIR = f"{LAB_DIR}/samples"

# 🌟 NEW: 용량별로 로그 폴더 및 CSV 파일을 분리하여 생성
LOG_DIR = f"{LAB_DIR}/logs_{TARGET_SIZE}"
CSV_REPORT_PATH = f"{LOG_DIR}/dataset_{TARGET_SIZE}.csv"
os.makedirs(LOG_DIR, exist_ok=True)

# CSV 파일 초기 세팅 (헤더 생성)
if not os.path.exists(CSV_REPORT_PATH):
    with open(CSV_REPORT_PATH, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Sample_Name", "Date", "Max_CPU_MHz", "Max_RAM_MB", "Num_Encrypted_Files", "Ransom_Note_Found", "PCAP_Saved"])

# ==========================================
# 🛠️ 3. 유틸리티 함수
# ==========================================
def run_cmd(cmd, timeout_sec=None, quiet=False):
    try:
        result = subprocess.run(cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors='replace', timeout=timeout_sec)
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    except subprocess.CalledProcessError as e:
        if not quiet:
            print(f"    [!] 명령어 실패: {cmd}\n        에러: {e.stderr.strip()}")
        return None

def wait_for_esxi_boot():
    print("    [*] ESXi 부팅 대기 중... (에러 메시지 없이 조용히 기다립니다)")
    while True:
        res = run_cmd(f"ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -J {JUMP_HOST} {ESXI_IP} 'echo ok'", quiet=True)
        if res == "ok":
            print("    [+] ESXi 부팅 완료 및 SSH 연결 성공!")
            break
        time.sleep(10)

# ==========================================
# 🚀 4. 메인 분석 파이프라인
# ==========================================
def analyze_sample(sample_filename, current_idx, total_cnt):
    sample_path = os.path.join(SAMPLES_DIR, sample_filename)
    report_path = f"{LOG_DIR}/report_{sample_filename}.txt"
    pcap_path = f"{LOG_DIR}/pcap_{sample_filename}.pcap"
    target_host_name = ESXI_IP.split('@')[1]

    print(f"\n" + "="*60)
    print(f" 🦠 샌드박스 분석 시작 [{current_idx}/{total_cnt}]: [{sample_filename}] (타겟: {TARGET_SIZE})")
    print("="*60)

    print(f"\n[Step 1] 해당 용량의 클린 상태({SNAPSHOT_NAME})로 스냅샷 롤백 중...")
    run_cmd(f"qm rollback {PROXMOX_VM_ID} {SNAPSHOT_NAME}")
    run_cmd(f"qm start {PROXMOX_VM_ID}")
    wait_for_esxi_boot()

    print("    [*] 시스템 안정화 및 내부 VM 부팅 대기 (180초 쿨다운)...")
    time.sleep(180)

    print("\n[Step 2] 실행 스크립트와 랜섬웨어 샘플을 전송 중...")
    run_cmd(f"scp -o StrictHostKeyChecking=no -J {JUMP_HOST} {LAB_DIR}/runner.sh {ESXI_IP}:/tmp/runner.sh")
    run_cmd(f"scp -o StrictHostKeyChecking=no -J {JUMP_HOST} {sample_path} {ESXI_IP}:/bin/malware.bin")

    print("\n[Step 3] vCenter 모니터링 준비...")
    vc = VCenterLogger(VC_IP, VC_USER, VC_PASSWORD)
    if not vc.connect():
        print("    [!] vCenter 연결 실패. 분석을 건너뜁니다.")
        return

    start_time = datetime.now(timezone.utc)

    print(f"\n[Step 4] 랜섬웨어 실행 (PCAP 캡처 포함) 및 모니터링 시작! (최대 {MAX_WAIT_SECONDS}초 대기)")
    exec_cmd = f"ssh -o StrictHostKeyChecking=no -J {JUMP_HOST} {ESXI_IP} 'sh /tmp/runner.sh'"
    process = subprocess.Popen(exec_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    stats_sequence = []
    elapsed = 0
    poll_interval = 20

    while elapsed < MAX_WAIT_SECONDS:
        if process.poll() is not None:
            print("    -> 랜섬웨어 동작이 조기 종료되었습니다.")
            break

        current_stats = vc.get_host_stats(target_host_name)
        if current_stats and 'error' not in current_stats:
            current_stats['timestamp'] = datetime.now().strftime('%H:%M:%S')
            stats_sequence.append(current_stats)
            cpu = current_stats.get('cpu_usage_mhz', 0)
            ram = current_stats.get('memory_usage_mb', 0)
            print(f"    [{current_stats['timestamp']}] 📈 CPU: {cpu}MHz | RAM: {ram}MB 수집 완료")

        time.sleep(poll_interval)
        elapsed += poll_interval

    if process.poll() is None:
        print("    -> 타임아웃 도달! 강제로 프로세스를 종료합니다.")
        process.kill()

    print("\n[Step 5] 타임라인 이벤트, PCAP 파일 및 내부 로그 수집 중...")
    events_during = vc.get_events_since(target_host_name, start_time)
    vc.disconnect()

    run_cmd(f"scp -o StrictHostKeyChecking=no -J {JUMP_HOST} {ESXI_IP}:/tmp/malware.pcap {pcap_path}", quiet=True)
    pcap_saved = "O" if os.path.exists(pcap_path) else "X"

    local_log = run_cmd(f"ssh -o StrictHostKeyChecking=no -J {JUMP_HOST} {ESXI_IP} 'cat /tmp/execution_result.log'", quiet=True)

    # ==========================================
    # [Step 6] 결과 보고서 및 CSV 데이터 정제
    # ==========================================
    print(f"\n[Step 6] 분석 보고서를 저장합니다 -> {report_path}")

    max_cpu = max([(s.get('cpu_usage_mhz') or 0) for s in stats_sequence]) if stats_sequence else 0
    max_ram = max([(s.get('memory_usage_mb') or 0) for s in stats_sequence]) if stats_sequence else 0
    num_enc_files = 0
    ransom_note_found = "X"

    if local_log:
        if "=== [Modified / Encrypted Files" in local_log:
            lines = local_log.split("\n")
            enc_start = False
            for line in lines:
                if "=== [Ransom Note Content]" in line:
                    break
                if enc_start and line.startswith("/vmfs/"):
                    num_enc_files += 1
                if "=== [Modified / Encrypted Files" in line:
                    enc_start = True
        if "Found Note:" in local_log:
            ransom_note_found = "O"

    with open(report_path, "w", encoding='utf-8') as f:
        f.write(f"=== 🦠 [Ransomware Sandbox Report] ===\n")
        f.write(f"Sample: {sample_filename} (Target: {TARGET_SIZE})\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        f.write("=== 📈 [1. 시스템 자원 변화 시퀀스 (20초 간격)] ===\n")
        if not stats_sequence:
            f.write("  - 수집된 데이터가 없습니다.\n")
        for seq in stats_sequence:
            ds_info = ", ".join([f"{k}:{v['free_space_gb']}GB" for k, v in seq.get('datastores', {}).items()])
            vm_info = ", ".join([f"{k}:{v}" for k, v in seq.get('vms', {}).items()])
            f.write(f"[{seq['timestamp']}] CPU: {seq.get('cpu_usage_mhz')}MHz | RAM: {seq.get('memory_usage_mb')}MB | DS: {ds_info} | VMs: {vm_info}\n")

        f.write("\n=== 🚨 [2. vCenter 타임라인 이벤트 (실행 중 발생)] ===\n")
        if events_during:
            for ev in events_during:
                f.write(f"  {ev}\n")
        else:
            f.write("  - 특이 이벤트 없음\n")

        f.write("\n=== 📂 [3. ESXi 내부 암호화, 랜섬노트 및 명령어 내역] ===\n")
        if local_log:
            f.write(local_log)
        else:
            f.write("  - 내부 로그 수집 실패 (랜섬웨어가 시스템을 파괴했거나 통신 단절)\n")

    with open(CSV_REPORT_PATH, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            sample_filename,
            datetime.now().strftime('%Y-%m-%d %H:%M'),
            max_cpu,
            max_ram,
            num_enc_files,
            ransom_note_found,
            pcap_saved
        ])

    print("[+] 현재 샘플 분석 완료. 다음 샘플로 넘어갑니다.\n")

if __name__ == "__main__":
    if not os.path.exists(SAMPLES_DIR):
        sys.exit(1)
    samples = [f for f in os.listdir(SAMPLES_DIR) if os.path.isfile(os.path.join(SAMPLES_DIR, f))]
    if not samples:
        sys.exit(0)
    total_cnt = len(samples)
    print(f"[*] 총 {total_cnt}개의 샘플을 {TARGET_SIZE} 환경에서 분석합니다.")

    for idx, sample in enumerate(samples, start=1):
        analyze_sample(sample, idx, total_cnt)

    print("\n=== 🧹 [최종 정리] 베이스라인 스냅샷으로 초기화합니다 ===")
    # 🌟 NEW: 마지막엔 어떤 파일도 없는 가장 깨끗한 기둥(base)으로 되돌려 놓습니다.
    run_cmd(f"qm rollback {PROXMOX_VM_ID} clean_ready_base")
    print("    -> 스냅샷 롤백 완료. 디스크 여유 공간이 최대로 확보되었습니다!")
    print("\n🎉 모든 샌드박스 자동화 분석이 성공적으로 종료되었습니다!")
