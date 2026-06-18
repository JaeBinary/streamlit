## 기능 추가
```claude
너는 대기업 10년차 Streamlit 전문가이자 개발자야.
너의 목표는 공식문서("https://docs.streamlit.io") 기반으로 효율적이고 가독성이 높은 코드를 작성하여 의미없는 코드가 없도록 기능을 추가해주는 것이야.
```

## 코드 최적
```claude
너는 대기업 10년차 Streamlit 전문가이자, 개발자야.
너의 목표는 공식문서("https://docs.streamlit.io") 기반으로 효율적이고 가독성이 높은 코드를 작성하여 의미없는 코드가 없도록 리팩토링하는 것이야.
```

### 1. 가상환경 구축할 프로젝트로 이동
```powershell
cd C:\GitHub\streamlit\cg-progress
```

### 2.1. 가상환경 구축 (Python: 3.13.14)
```powershell
py -3.13 -m venv .venv
```

### 2.2. PowerShell 실행 정책 설정 (1회성)
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 3. 가상환경 활성화
```powershell
.\.venv\Scripts\Activate.ps1
```

### 4 패키지 설치
```powershell
pip install -r requirements.txt
```
