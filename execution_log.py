#!/usr/bin/env python3
"""
execution_log.py
执行反馈闭环模块
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

LOG_FILE = os.path.expanduser("~/.hermes/knowledge-wiki/one-person-company/execution_log.json")

@dataclass
class ExecutionRecord:
    idea_id: str
    idea_title: str
    executed_date: str
    time_spent_days: float
    result: str              # Success / Failed / Paused / Abandoned
    revenue_or_feedback: str = ""
    key_learnings: str = ""
    next_action: str = ""


def load_logs() -> List[Dict]:
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_logs(logs: List[Dict]):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)


def add_execution_record(record: ExecutionRecord):
    """添加一条执行记录"""
    logs = load_logs()
    logs.append(asdict(record))
    save_logs(logs)
    print(f"✅ 已记录执行：{record.idea_title}")


def get_execution_summary() -> Dict:
    """生成执行统计摘要"""
    logs = load_logs()
    if not logs:
        return {"total": 0, "success_rate": 0}
    
    success_count = sum(1 for log in logs if log["result"].lower() == "success")
    total_time = sum(log["time_spent_days"] for log in logs)
    
    return {
        "total_executed": len(logs),
        "success_count": success_count,
        "success_rate": round(success_count / len(logs) * 100, 1),
        "total_time_spent_days": total_time,
        "average_time_per_idea": round(total_time / len(logs), 1)
    }


def print_summary():
    """打印执行摘要"""
    summary = get_execution_summary()
    print("\n=== 执行反馈摘要 ===")
    print(f"已执行想法数量: {summary['total_executed']}")
    print(f"成功率: {summary['success_rate']}%")
    print(f"总耗时: {summary['total_time_spent_days']} 天")
    print(f"平均每个想法耗时: {summary['average_time_per_idea']} 天")
    print("====================\n")


if __name__ == "__main__":
    # 示例
    record = ExecutionRecord(
        idea_id="r2",
        idea_title="本地 AI Agent 长期记忆",
        executed_date=datetime.now().strftime("%Y-%m-%d"),
        time_spent_days=4.5,
        result="Success",
        revenue_or_feedback="获得 3 位付费用户",
        key_learnings="用户更在意隐私和本地化",
        next_action="继续优化记忆检索功能"
    )
    add_execution_record(record)
    print_summary()