# 냉장고를 부탁해 (Picook)

“냉장고를 부탁해”는 FastAPI 백엔드와 Jinja2 템플릿, Vanilla JavaScript, 그리고 PWA 기능을 갖춘 웹앱입니다. 사용자가 냉장고 속 재료의 사진을 업로드하면, AI(Vision + ChatGPT)를 통해 재료를 인식하고, 원하는 요리 스타일에 맞춰 레시피를 추천해 줍니다.

---

## 주요 기능

1. **사진 업로드 (멀티 이미지 지원)**

   * 최대 6장까지 업로드 가능
   * 각 사진을 그리드 형태의 슬롯에 표시
   * 개별 삭제 버튼 제공

2. **AI 기반 재료 분석**

   * 각 이미지를 개별적으로 OpenAI Vision API(GPT‑4o)로 분석
   * JSON 배열 형태로 재료 목록 반환
   * ` ```json … ``` ` 코드블록 및 불필요한 따옴표 제거
   * 중복 재료 자동 제거

3. **재료 목록 수정**

   * 인식된 재료 리스트를 화면에 표시
   * 각 항목마다 “삭제” 버튼 제공
   * 사용자가 직접 콤마 구분으로 재료 추가 가능

4. **요리 스타일 선택**

   * 한식, 중식, 일식, 양식, 파티용, 자취요리 등 다중 선택 지원
   * 토글 태그 UI로 직관적인 선택

5. **ChatGPT 레시피 추천**

   * 선택된 재료와 스타일을 합쳐 GPT‑4o에 전달
   * 단계별 레시피를 Markdown 스타일로 화면에 렌더

6. **PWA(Progressive Web App)**

   * `manifest.json` & Service Worker (`service-worker.js`) 완비
   * HTTPS 환경에서 “홈 화면에 추가”/“설치” 지원
   * Android TWA, Capacitor/Cordova 등 네이티브 포장 가능

---

## 디렉터리 구조

```
.
├── app.py                   # FastAPI 서버
├── requirements.txt         # Python 의존성
├── static/
│   ├── uploads/             # 사용자 업로드 이미지 저장
│   ├── icons/               # PWA 아이콘 모음
│   ├── style.css            # 전역 스타일
│   ├── manifest.json        # PWA 매니페스트
│   └── service-worker.js    # PWA Service Worker
└── templates/
    ├── base.html            # 공통 레이아웃
    ├── index.html           # 시작 페이지
    ├── upload.html          # 사진 업로드 페이지
    ├── results.html         # 재료 분석 및 수정 페이지
    ├── style.html           # 요리 스타일 선택 페이지
    └── chat.html            # 최종 레시피 페이지
```

---

## 설치 및 실행

1. **Clone**

   ```bash
   git clone https://github.com/LeeBellHa/Food_App.git
   cd Food_App
   ```

2. **가상환경 & 의존성 설치**

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **환경 변수 설정**

   프로젝트 루트에 `.env` 파일을 생성하고, OpenAI API 키를 추가:

   ```
   OPENAI_API_KEY=sk-*******************************
   ```

4. **서버 실행**

   ```bash
   uvicorn app:app --reload --host 0.0.0.0 --port 8000
   ```

5. **PWA 사용 (로컬 테스트)**

   * `http://localhost:8000` 접속
   * Chrome/Edge 주소창 우측 “설치” 버튼 클릭

6. **(선택) ngrok 로 외부 공개**

   ```bash
   ngrok http 8000
   ```

---

## 주요 기술 스택

* **Python / FastAPI**: 비동기 REST 서버
* **Jinja2**: 템플릿 렌더링
* **Vanilla JavaScript**: 파일 업로드 UI, 재료 리스트 동적 조작
* **OpenAI Vision & ChatCompletion**: GPT‑4o 기반 이미지 → 텍스트 변환 및 레시피 생성
* **PWA**: `manifest.json`, Service Worker, 홈 화면 설치 지원

---

## 배포 가이드

1. **HTTPS 인증서**: Let’s Encrypt 등으로 SSL 설정
2. **Static 파일 서빙**: CDN 또는 Nginx 캐시 적용
3. **TWA(Android)**: PWABuilder 또는 Android Studio에서 Trusted Web Activity로 패키징
4. **iOS**: Capacitor/Cordova로 래핑하여 TestFlight / App Store 제출

---

## 기여

1. 이슈(문제/제안) 등록
2. 브랜치 생성 (`feature/your-feature`)
3. 커밋 & PR 요청

---

## 라이선스

MIT © 2025 Picook 팀
