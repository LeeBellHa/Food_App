import os
import io
import uuid
import base64
import traceback
from typing import List

from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import (
    HTMLResponse,
    RedirectResponse,
    FileResponse,
    Response,
    PlainTextResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.status import HTTP_302_FOUND
from PIL import Image
import openai

# ——— OpenAI API 설정 ———
api_key = "sk-프로젝트-키-여기에-삽입"
client = openai.OpenAI(api_key=api_key)

app = FastAPI()

# 세션 미들웨어 (쿠키 기반)
app.add_middleware(SessionMiddleware, secret_key=os.urandom(24))

# 정적 파일 및 업로드 디렉터리 설정
UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# 템플릿 디렉터리
templates = Jinja2Templates(directory="templates")


# ─────────────────────────────────────────
# 서비스 워커를 루트(/service-worker.js)로 노출
# ─────────────────────────────────────────
@app.get("/service-worker.js", include_in_schema=False)
async def service_worker():
    sw_path = os.path.join("static", "service-worker.js")
    if os.path.exists(sw_path):
        code = open(sw_path, "r", encoding="utf-8").read()
        return PlainTextResponse(code, media_type="application/javascript")
    return Response(status_code=404)


# ─────────────────────────────────────────
# favicon 처리 (없으면 204 No Content)
# ─────────────────────────────────────────
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    ico = os.path.join("static", "favicon.ico")
    if os.path.exists(ico):
        return FileResponse(ico)
    return Response(status_code=204)


# ─────────────────────────────────────────
# 1) 시작 페이지
# ─────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ─────────────────────────────────────────
# 2) 사진 업로드 페이지
# ─────────────────────────────────────────
@app.get("/upload", response_class=HTMLResponse)
def get_upload(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})


@app.post("/upload")
async def post_upload(request: Request, images: List[UploadFile] = File(...)):
    # 세션 초기화: 이전 Base64 데이터 제거
    request.session.clear()

    filenames: List[str] = []
    for up in images:
        ext = os.path.splitext(up.filename)[1] or ".jpg"
        fn = f"{uuid.uuid4().hex}{ext}"
        path = os.path.join(UPLOAD_DIR, fn)
        data = await up.read()
        with open(path, "wb") as f:
            f.write(data)
        filenames.append(fn)

    request.session["filenames"] = filenames
    return RedirectResponse("/results", status_code=HTTP_302_FOUND)


# ─────────────────────────────────────────
# 3) 분석 결과 & 재료 수정 페이지 (오류 핸들링 포함)
# ─────────────────────────────────────────
@app.get("/results", response_class=HTMLResponse)
async def get_results(request: Request):
    try:
        fns = request.session.get("filenames")
        if not fns:
            return RedirectResponse("/upload", status_code=HTTP_302_FOUND)

        # 한 번도 분석하지 않았다면 OpenAI에 요청
        if "ingredients" not in request.session:
            msgs = [
                {"type": "text", "text": "이미지에 포함된 음식 이름을 간단한 단어 목록으로만 알려주세요. 예: 사과, 바나나"}
            ]
            for fn in fns:
                with open(os.path.join(UPLOAD_DIR, fn), "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                msgs.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
                })

            resp = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": msgs}],
                max_tokens=100,
            )
            items = [s.strip() for s in resp.choices[0].message.content.split(",") if s.strip()]
            request.session["ingredients"] = items

        return templates.TemplateResponse("results.html", {
            "request": request,
            "filenames": fns,
            "ingredients": request.session["ingredients"],
        })

    except Exception:
        tb = traceback.format_exc()
        # 화면에 스택 트레이스를 출력하여 디버깅
        return HTMLResponse(
            f"<h1>서버 내부 오류</h1><pre style='white-space: pre-wrap; color: red;'>{tb}</pre>",
            status_code=500
        )


@app.post("/results")
def post_results(request: Request, ingredients: str = Form(...)):
    cleaned = [i.strip() for i in ingredients.split(",") if i.strip()]
    request.session["ingredients"] = cleaned
    return RedirectResponse("/style", status_code=HTTP_302_FOUND)


# ─────────────────────────────────────────
# 4) 요리 스타일 선택 페이지
# ─────────────────────────────────────────
@app.get("/style", response_class=HTMLResponse)
def get_style(request: Request):
    return templates.TemplateResponse("style.html", {"request": request})


@app.post("/style")
def post_style(request: Request, recipe_type: str = Form(...)):
    request.session["recipe_type"] = recipe_type
    return RedirectResponse("/chat", status_code=HTTP_302_FOUND)


# ─────────────────────────────────────────
# 5) 최종 ChatGPT 레시피 페이지
# ─────────────────────────────────────────
@app.get("/chat", response_class=HTMLResponse)
def chat(request: Request):
    ingredients = request.session.get("ingredients", [])
    recipe_type = request.session.get("recipe_type", "식사용")

    prompt = (
        f"나는 {', '.join(ingredients)}을(를) 가지고 있습니다. "
        f"이 재료들로 '{recipe_type}' 스타일 요리를 추천하고, 자세한 레시피를 알려주세요."
    )
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500,
    )

    return templates.TemplateResponse("chat.html", {
        "request": request,
        "recipe": resp.choices[0].message.content.strip(),
    })


# ▶ 개발 모드 실행:
# uvicorn app:app --reload --host 0.0.0.0 --port 8000
