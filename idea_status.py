#!/usr/bin/env python3
"""
idea_status.py
需求状态追踪模块
"""

import json
import os
from datetime import datetime
from typing import Dict, Optional

STATUS_FILE = os.path.expanduser("~/.hermes/knowledge-wiki/one-person-company/idea_status.json")

DEFAULT_STATUSES = ["Pending", "In Progress", "Validated", "Abandoned"]

def load_status() -> Dict:
    """加载状态数据"""
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_status(data: Dict):
    """保存状态数据"""
    os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def update_idea_status(idea_id: str, status: str, note: str = ""):
    """更新单个想法的状态"""
    data = load_status()
    data[idea_id] = {
        "status": status,
        "updated_at": datetime.now().isoformat(),
        "note": note
    }
    save_status(data)

def get_idea_status(idea_id: str) -> Optional[Dict]:
    """获取单个想法的状态"""
    data = load_status()
    return data.get(idea_id)

def get_all_statuses() -> Dict:
    """获取所有状态"""
    return load_status()