#!/usr/bin/env python3
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pathlib import Path

router = APIRouter(prefix="/api/system", tags=["system"])

def read_html_file(filename):
    filepath = Path(__file__).parent.parent / "templates" / filename
    if filepath.exists():
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    return "<h1>页面加载失败</h1>"

SYSTEM_HTML = read_html_file("system.html")

@router.get("/page", response_class=HTMLResponse)
async def system_page():
    """系统信息页面"""
    return HTMLResponse(content=SYSTEM_HTML)
