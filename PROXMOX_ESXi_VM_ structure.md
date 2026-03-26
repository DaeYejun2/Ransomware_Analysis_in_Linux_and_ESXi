<img width="1012" height="616" alt="image" src="https://github.com/user-attachments/assets/973d3a0c-d64c-4554-a8c4-ac3256967c62" />

1. Proxmox Host (제어층)
   * 스냅샷 제어: 실험이 끝나면 ESXi VM을 즉시 초기 상태(사전에 설정해둔 clean_ready)로 되돌린다. 소프트웨어적 롤백
   * 중앙 관리: vCenter VM으로부터 API를 통해 성능 데이터(CPU, Disk I/O 등)를 실시간으로 수집하여 분석 리포트를 생성한다.
   * 자동화 코드 실행: 전체 시나리오를 관리하는 Python 코드가 여기서 실행된다.
  
2. Linux VM (Jump Host)
   * Proxmox Host와 내부 ESXi 사이의 통신이 직접 이루어지지 않을 때, SSH 키 기반으로 명령과 샘플(Malware)을 전달한다.
   * 외부의 위협이 직접 실험 환경에 닿지 않게 하고, 실험 환경의 트래픽이 외부로 나가지 않게 하는 게이트웨이 역할을 수행
  
3. ESXi VM & vCenter VM (샌드박스 & 모니터링)
   * ESXi VM: runner.sh가 실행되는 곳
     * runner.sh: auto_sandbox.py에 의해 ESXi로 전송되어 ESXi 내부에서 실행됨. ESXi 내부에서 샘플 실행, 샘플 실행 시간 측정, 랜섬노트 확인, 암호화된 파일 확인 등의 동작을 하고, ESXi 내부에 그것을 기록한 로그를 만듦. 만들어진 로그는 auto_sandbox.py에 의해 Proxmox host로 전송됨
