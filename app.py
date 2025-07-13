# ─────────────────────────────────────────────────────────
# HTTPConnection.putheader 패치: UnicodeEncodeError 완전 우회
# ─────────────────────────────────────────────────────────
import http.client
_original_putheader = http.client.HTTPConnection.putheader

def _safe_putheader(self, header, *values):
    safe_vals = []
    for v in values:
        if isinstance(v, str):
            try:
                v.encode("latin-1")
            except UnicodeEncodeError:
                v = v.encode("utf-8", "ignore").decode("latin-1", "ignore")
        safe_vals.append(v)
    return _original_putheader(self, header, *safe_vals)

http.client.HTTPConnection.putheader = _safe_putheader


# ─────────────────────────────────────────────────────────
# 환경 변수에서 OpenAI API 키 로드
# ─────────────────────────────────────────────────────────
import os
from dotenv import load_dotenv

load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise RuntimeError("🚨 OPENAI_API_KEY가 설정되지 않았습니다! .env 파일을 확인하세요.")

import openai
openai.api_key = openai_api_key


# ─────────────────────────────────────────────────────────
# FastAPI 애플리케이션 설정
# ─────────────────────────────────────────────────────────
import time
import uuid
import base64
import traceback
import json
import re
from typing import List

from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.status import HTTP_302_FOUND

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=os.urandom(24))

# 업로드 디렉터리 및 정적 파일
UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")


# ─────────────────────────────────────────────────────────
# 서버 시작 시 오래된 업로드 정리 (1시간 지난 파일 삭제)
# ─────────────────────────────────────────────────────────
@app.on_event("startup")
def cleanup_old_uploads():
    now = time.time()
    cutoff = 60 * 60  # 1시간
    for fname in os.listdir(UPLOAD_DIR):
        path = os.path.join(UPLOAD_DIR, fname)
        if os.path.isfile(path) and now - os.path.getmtime(path) > cutoff:
            try:
                os.remove(path)
            except OSError:
                pass


# ─────────────────────────────────────────────────────────
# 서비스 워커 및 favicon
# ─────────────────────────────────────────────────────────
@app.get("/service-worker.js", include_in_schema=False)
async def service_worker():
    path = os.path.join("static", "service-worker.js")
    if os.path.exists(path):
        return FileResponse(path, media_type="application/javascript")
    return Response(status_code=404)

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    path = os.path.join("static", "favicon.ico")
    if os.path.exists(path):
        return FileResponse(path)
    return Response(status_code=204)


# ─────────────────────────────────────────────────────────
# 1) 시작 페이지
# ─────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ─────────────────────────────────────────────────────────
# 2) 사진 업로드 페이지
# ─────────────────────────────────────────────────────────
@app.get("/upload", response_class=HTMLResponse)
def get_upload(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})

@app.post("/upload")
async def post_upload(request: Request, images: List[UploadFile] = File(...)):
    # 이전 업로드 파일 삭제
    old = request.session.get("filenames", [])
    for fn in old:
        p = os.path.join(UPLOAD_DIR, fn)
        if os.path.exists(p):
            try: os.remove(p)
            except: pass

    request.session.clear()

    # 새 파일 저장 (확장자 소문자 통일)
    filenames: List[str] = []
    for up in images:
        ext = os.path.splitext(up.filename)[1].lower() or ".jpg"
        fn = f"{uuid.uuid4().hex}{ext}"
        out = os.path.join(UPLOAD_DIR, fn)
        data = await up.read()
        with open(out, "wb") as f:
            f.write(data)
        filenames.append(fn)

    request.session["filenames"] = filenames
    return RedirectResponse("/results", status_code=HTTP_302_FOUND)


# ─────────────────────────────────────────────────────────
# 3) 분석 결과 & 재료 수정 페이지
# ─────────────────────────────────────────────────────────
@app.get("/results", response_class=HTMLResponse)
async def get_results(request: Request):
    try:
        fns = request.session.get("filenames")
        if not fns:
            return RedirectResponse("/upload", status_code=HTTP_302_FOUND)

        if "ingredients" not in request.session:
            # 시스템 메시지
            system_msg = (
                "당신은 이미지 속 음식 재료를 추출하는 전문가입니다. "
                "반드시 한국어 재료명만 들어간 순수 JSON 배열 형식으로만 응답하세요. "
                "추가 설명이나 주석 없이 배열만 출력합니다."
            )
            # 유저 메시지: Base64 이미지 포함
            msgs = [{"type": "text", "text": "이미지를 분석해 음식 재료를 JSON 배열로 알려주세요."}]
            for fn in fns:
                with open(os.path.join(UPLOAD_DIR, fn), "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                msgs.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
                })

            resp = openai.ChatCompletion.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": msgs}
                ],
                max_tokens=100,
                temperature=0
            )
            raw = resp.choices[0].message.content

            # ── ```json … ``` 제거 ──
            clean = re.sub(r"^```(?:json)?", "", raw.strip(), flags=re.IGNORECASE)
            clean = re.sub(r"```$", "", clean).strip()

            # JSON 파싱 시도
            try:
                items = json.loads(clean)
            except json.JSONDecodeError:
                items = re.split(r"[-,]\s*", clean)
                items = [s.strip().strip('"') for s in items if s.strip()]

            request.session["ingredients"] = items

        return templates.TemplateResponse("results.html", {
            "request": request,
            "filenames": fns,
            "ingredients": request.session["ingredients"]
        })

    except Exception:
        tb = traceback.format_exc()
        return HTMLResponse(
            f"<h1>서버 내부 오류</h1>"
            f"<pre style='white-space: pre-wrap; color: red;'>{tb}</pre>",
            status_code=500
        )

@app.post("/results")
def post_results(request: Request, ingredients: str = Form(...)):
    cleaned = [i.strip() for i in ingredients.split(",") if i.strip()]
    request.session["ingredients"] = cleaned
    return RedirectResponse("/style", status_code=HTTP_302_FOUND)


# ─────────────────────────────────────────────────────────
# 4) 요리 스타일 선택 페이지
# ─────────────────────────────────────────────────────────
@app.get("/style", response_class=HTMLResponse)
def get_style(request: Request):
    return templates.TemplateResponse("style.html", {"request": request})

@app.post("/style")
def post_style(request: Request, recipe_type: List[str] = Form(...)):
    request.session["recipe_type"] = recipe_type
    return RedirectResponse("/chat", status_code=HTTP_302_FOUND)


# ─────────────────────────────────────────────────────────
# 5) 최종 ChatGPT 레시피 페이지
# ─────────────────────────────────────────────────────────
@app.get("/chat", response_class=HTMLResponse)
def chat(request: Request):
    ingredients = request.session.get("ingredients", [])
    recipe_type_list = request.session.get("recipe_type", ["식사용"])
    pt = ", ".join(recipe_type_list)

    prompt = (
        f"나는 {', '.join(ingredients)}을(를) 가지고 있습니다. "
        f"이 재료들로 '{pt}' 스타일의 요리를 추천하고, 자세한 레시피를 알려주세요."
    )
    resp = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500
    )

    return templates.TemplateResponse("chat.html", {
        "request": request,
        "recipe": resp.choices[0].message.content.strip(),
    })


# ▶ 개발 모드 실행:
# uvicorn app:app --reload --host 0.0.0.0 --port 8000
