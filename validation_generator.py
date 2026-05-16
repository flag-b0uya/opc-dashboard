#!/usr/bin/env python3
"""
validation_generator.py
验证实验生成器
为 S-Tier 需求自动生成低成本验证方案
"""

from dataclasses import dataclass
from typing import List, Dict

@dataclass
class ValidationExperiment:
    name: str
    description: str
    estimated_cost: str
    estimated_time: str
    success_criteria: str
    how_to_run: str


def generate_validation_experiments(idea_title: str, idea_description: str = "") -> List[ValidationExperiment]:
    """
    为一个想法生成验证实验
    """
    experiments = []

    # 1. Landing Page 测试
    experiments.append(ValidationExperiment(
        name="Landing Page 测试",
        description="创建一个简单的落地页，描述产品价值，收集邮箱或预购意向。",
        estimated_cost="0-50元（域名+简单建站工具）",
        estimated_time="1-2天",
        success_criteria="转化率 ≥ 15% 或 收集到 50+ 个邮箱",
        how_to_run="使用 Carrd / Framer / Notion + 邮件收集工具（ConvertKit / Substack）"
    ))

    # 2. Fake Door 测试
    experiments.append(ValidationExperiment(
        name="Fake Door 测试",
        description="在现有产品或着陆页上放置“即将上线”按钮，统计点击率。",
        estimated_cost="0元",
        estimated_time="半天",
        success_criteria="点击率 ≥ 8%",
        how_to_run="在现有网站/微信公众号/小红书添加按钮，统计点击数据"
    ))

    # 3. 用户访谈
    experiments.append(ValidationExperiment(
        name="用户访谈",
        description="与 5-8 位潜在用户进行 15-20 分钟深度访谈，验证痛点真实性。",
        estimated_cost="0-200元（可能需要小礼品）",
        estimated_time="2-3天",
        success_criteria="70% 以上用户表示痛点强烈 + 愿意付费",
        how_to_run="通过 Reddit、V2EX、微信群、Twitter 招募用户，使用 Notion 记录访谈"
    ))

    # 4. 可运行 MVP 原型
    experiments.append(ValidationExperiment(
        name="可运行 MVP 原型",
        description="用最简单的方式做出一个能跑通核心流程的原型（非完整产品）。",
        estimated_cost="0-100元",
        estimated_time="3-5天",
        success_criteria="至少 3-5 个真实用户愿意持续使用 1 周以上",
        how_to_run="使用 Python + Streamlit / Gradio / Telegram Bot / 微信小程序快速搭建"
    ))

    return experiments


def format_validation_report(idea_title: str, experiments: List[ValidationExperiment]) -> str:
    """生成格式化的验证报告"""
    lines = [f"# {idea_title} - 验证实验方案\n"]
    
    for i, exp in enumerate(experiments, 1):
        lines.append(f"## {i}. {exp.name}")
        lines.append(f"**描述**：{exp.description}")
        lines.append(f"**预计成本**：{exp.estimated_cost}")
        lines.append(f"**预计时间**：{exp.estimated_time}")
        lines.append(f"**成功标准**：{exp.success_criteria}")
        lines.append(f"**执行方法**：{exp.how_to_run}\n")
    
    return "\n".join(lines)


if __name__ == "__main__":
    # 测试
    title = "本地 AI Agent 长期记忆系统"
    experiments = generate_validation_experiments(title)
    report = format_validation_report(title, experiments)
    print(report)