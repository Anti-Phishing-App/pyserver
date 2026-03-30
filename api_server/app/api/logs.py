from fastapi import APIRouter, HTTPException, WebSocket
from fastapi.responses import HTMLResponse
import os
import asyncio

router = APIRouter(prefix="/admin/logs", tags=["Admin Logs"])

LOG_DIR = "/home/ubuntu/.pm2/logs"
OUT_LOG = os.path.join(LOG_DIR, "fastapi-out.log")

# =========================================================
# 1) 기존 GET 방식: Swagger에서 조회
# =========================================================
@router.get("/fastapi")
def read_fastapi_logs(lines: int = 200):
    """PM2 FastAPI 로그 읽기"""
    try:
        if not os.path.exists(OUT_LOG):
            raise HTTPException(404, "fastapi-out.log 파일이 없습니다.")

        with open(OUT_LOG, "r", encoding="utf-8") as f:
            data = f.readlines()

        return {"log": "".join(data[-lines:])}

    except Exception as e:
        raise HTTPException(500, f"로그 읽기 실패: {str(e)}")


# =========================================================
# 2) WebSocket 실시간 스트리밍
# =========================================================
@router.websocket("/ws")
async def pm2_log_stream(ws: WebSocket):
    await ws.accept()

    if not os.path.exists(OUT_LOG):
        await ws.send_text("fastapi-out.log 파일을 찾을 수 없습니다.")
        await ws.close()
        return

    with open(OUT_LOG, "r") as f:
        f.seek(0, 2)  # tail -f 모드

        while True:
            line = f.readline()

            if line:
                await ws.send_text(line)
            else:
                await asyncio.sleep(0.2)


# =========================================================
# 3) HTML 로그 뷰어 페이지 (자동 스크롤 + 재연결)
# =========================================================
@router.get("/stream-view")
def log_view():
    html = """
    <!doctype html>
    <html lang="ko">
    <head>
        <meta charset="utf-8">
        <title>Real-time PM2 Log Stream</title>
        <style>
            body {
                background: #111;
                color: #eee;
                font-family: Consolas, monospace;
                margin: 0;
                padding: 0;
            }
            #header {
                background: #222;
                padding: 10px;
                font-size: 18px;
                border-bottom: 1px solid #444;
            }
            #log {
                white-space: pre-wrap;
                padding: 12px;
                font-size: 14px;
            }
        </style>
    </head>
    <body>
        <div id="header">🔥 FastAPI PM2 Log Viewer (Real-time)</div>
        <div id="log"></div>

        <script>
            const logBox = document.getElementById("log");

            function connectWS() {
                const ws = new WebSocket("ws://" + location.host + "/admin/logs/ws");

                ws.onopen = () => {
                    logBox.innerHTML += "\\n[Connected] 실시간 로그 시작...\\n";
                };

                ws.onmessage = (event) => {
                    logBox.innerHTML += event.data;
                    window.scrollTo(0, document.body.scrollHeight);
                };

                ws.onerror = () => {
                    logBox.innerHTML += "\\n[WebSocket Error]\\n";
                };

                ws.onclose = () => {
                    logBox.innerHTML += "\\n[Disconnected] 3초 후 재시도...\\n";
                    setTimeout(connectWS, 3000);
                };
            }

            connectWS();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(html)
