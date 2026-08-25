# This project was developed with assistance from AI tools.
"""Generate the 30 watermarked synthetic PDFs used by the P0 interview demo."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas


WATERMARK = "合成数据｜仅供演示"
PAGE_WIDTH, PAGE_HEIGHT = A4
FONT = "STSong-Light"
ACCENT = colors.HexColor("#173B57")
MUTED = colors.HexColor("#637083")


@dataclass(frozen=True)
class DemoCase:
    index: int
    scenario: str
    quality: str
    id_name: str
    income_name: str
    bank_name: str
    id_number: str | None
    employer: str | None
    certified_income: int | None
    bank_income: int | None
    pages: int = 1


CASES = [
    DemoCase(1, "正常一致", "清晰", "李安然", "李安然", "李安然", "51010019900101001X", "成都融科信息服务有限公司", 15000, 14880),
    DemoCase(2, "正常一致-多页", "多页", "陈蓉", "陈蓉", "陈蓉", "510100199202020028", "成都益居科技有限公司", 18000, 17920, 2),
    DemoCase(3, "低清晰度", "模糊", "王晴", "王晴", "王晴", "510100198803030036", "成都青禾数据有限公司", 13500, 13320),
    DemoCase(4, "关键字段缺失", "字段缺失", "赵宁", "赵宁", "赵宁", None, None, None, None),
    DemoCase(5, "姓名不一致", "清晰", "张安宁", "李安宁", "张安宁", "510100199404040044", "成都万象咨询有限公司", 16000, 15850),
    DemoCase(6, "收入不一致", "清晰", "周平", "周平", "周平", "510100199105050052", "成都星云软件有限公司", 20000, 10800),
    DemoCase(7, "证件或证明过期", "历史日期", "孙悦", "孙悦", "孙悦", "510100198706060060", "成都锦程商贸有限公司", 12000, 11950),
    DemoCase(8, "部分字段遮罩", "遮罩", "何川", "何川", "何川", "510100199307070079", "成都西岭智能科技有限公司", 17500, 17250),
    DemoCase(9, "低对比度", "低对比度", "罗欣", "罗欣", "罗欣", "510100199508080087", "成都新川创意有限公司", 14500, 14300),
    DemoCase(10, "正常一致-边界金额", "清晰", "唐晓", "唐晓", "唐晓", "510100199609090095", "成都天府企服有限公司", 10000, 9900),
]


def setup_fonts() -> None:
    pdfmetrics.registerFont(UnicodeCIDFont(FONT))


def add_watermark(pdf: canvas.Canvas) -> None:
    pdf.saveState()
    pdf.setFillColor(colors.HexColor("#B91C1C"))
    pdf.setFillAlpha(0.12)
    pdf.setFont(FONT, 34)
    pdf.translate(PAGE_WIDTH / 2, PAGE_HEIGHT / 2)
    pdf.rotate(32)
    pdf.drawCentredString(0, 0, WATERMARK)
    pdf.restoreState()
    pdf.saveState()
    pdf.setFillColor(colors.HexColor("#B91C1C"))
    pdf.setFont(FONT, 8)
    pdf.drawCentredString(PAGE_WIDTH / 2, 16, f"{WATERMARK} · 融安住房金融虚构演示机构")
    pdf.restoreState()


def header(pdf: canvas.Canvas, title: str, subtitle: str, page_no: int = 1) -> float:
    pdf.setFillColor(ACCENT)
    pdf.rect(0, PAGE_HEIGHT - 105, PAGE_WIDTH, 105, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont(FONT, 23)
    pdf.drawString(42, PAGE_HEIGHT - 55, title)
    pdf.setFont(FONT, 9)
    pdf.drawString(42, PAGE_HEIGHT - 78, subtitle)
    pdf.drawRightString(PAGE_WIDTH - 42, PAGE_HEIGHT - 78, f"第 {page_no} 页")
    return PAGE_HEIGHT - 145


def field(pdf: canvas.Canvas, label: str, value: object, y: float, *, muted: bool = False) -> float:
    pdf.setFillColor(MUTED)
    pdf.setFont(FONT, 10)
    pdf.drawString(52, y, label)
    pdf.setFillColor(colors.HexColor("#A0A8B0") if muted else "#111827")
    pdf.setFont(FONT, 13)
    pdf.drawString(165, y, "—" if value in (None, "") else str(value))
    pdf.setStrokeColor(colors.HexColor("#D8DEE7"))
    pdf.line(52, y - 10, PAGE_WIDTH - 52, y - 10)
    return y - 43


def note(pdf: canvas.Canvas, case: DemoCase, y: float) -> None:
    pdf.setFillColor(colors.HexColor("#EFF6FF"))
    pdf.roundRect(45, y - 52, PAGE_WIDTH - 90, 62, 8, fill=1, stroke=0)
    pdf.setFillColor(ACCENT)
    pdf.setFont(FONT, 10)
    pdf.drawString(60, y - 12, f"样本场景：{case.scenario} · 质量：{case.quality}")
    pdf.setFont(FONT, 8)
    pdf.drawString(60, y - 32, "所有姓名、证件号、单位、账户与交易均为程序生成，不对应任何真实个人或机构。")


def create_id_pdf(path: Path, case: DemoCase) -> None:
    if case.quality == "模糊":
        create_blurred_pdf(path, "居民身份证信息页", case, "id")
        return
    pdf = canvas.Canvas(str(path), pagesize=A4)
    for page_no in range(1, case.pages + 1):
        y = header(pdf, "居民身份证信息页", "FinCredit Copilot 材料提取演示", page_no)
        y = field(pdf, "姓名", case.id_name, y, muted=case.quality == "低对比度")
        y = field(pdf, "公民身份号码", case.id_number, y, muted=case.quality == "低对比度")
        y = field(pdf, "性别", "女" if case.index % 2 else "男", y)
        y = field(pdf, "出生日期", "1990-01-01", y)
        y = field(pdf, "住址", "四川省成都市高新区合成路 100 号", y)
        y = field(pdf, "签发机关", "成都市公安局演示分局", y)
        expiry = "2017-01-01 至 2027-01-01" if case.index == 7 else "2023-01-01 至 2043-01-01"
        y = field(pdf, "有效期限", expiry, y)
        if page_no == 2:
            y = field(pdf, "页面说明", "身份证背面与签发信息补充页", y)
        note(pdf, case, y - 5)
        add_watermark(pdf)
        pdf.showPage()
    pdf.save()


def create_income_pdf(path: Path, case: DemoCase) -> None:
    if case.quality == "模糊":
        create_blurred_pdf(path, "收入证明", case, "income")
        return
    pdf = canvas.Canvas(str(path), pagesize=A4)
    for page_no in range(1, case.pages + 1):
        y = header(pdf, "收入证明", "供住房贷款授信材料核验使用", page_no)
        y = field(pdf, "员工姓名", case.income_name, y, muted=case.quality == "低对比度")
        y = field(pdf, "任职单位", case.employer, y, muted=case.quality == "低对比度")
        y = field(pdf, "部门 / 职务", "产品技术部 / 业务分析师", y)
        y = field(pdf, "入职日期", "2021-06-01", y)
        income = f"人民币 {case.certified_income:,.2f} 元/月" if case.certified_income is not None else None
        y = field(pdf, "税前月收入", income, y)
        y = field(pdf, "近 12 个月奖金", "人民币 24,000.00 元", y)
        issue_date = "2023-01-10" if case.index == 7 else "2026-08-18"
        y = field(pdf, "开具日期", issue_date, y)
        y = field(pdf, "单位经办信息", "合成经办人 / 028-0000-0000", y)
        if page_no == 2:
            y = field(pdf, "补充说明", "本页为薪酬结构与奖金说明附件", y)
        note(pdf, case, y - 5)
        add_watermark(pdf)
        pdf.showPage()
    pdf.save()


def transactions(case: DemoCase, page_no: int) -> list[tuple[str, str, int, int]]:
    income = case.bank_income or 0
    base = (page_no - 1) * 5
    return [
        (f"2026-{month:02d}-05", "工资代发-合成单位", income, 58000 + income * (month - 4))
        for month in range(4 + base, min(9 + base, 13))
    ]


def create_bank_pdf(path: Path, case: DemoCase) -> None:
    if case.quality == "模糊":
        create_blurred_pdf(path, "个人银行账户流水", case, "bank")
        return
    pdf = canvas.Canvas(str(path), pagesize=A4)
    for page_no in range(1, case.pages + 1):
        y = header(pdf, "个人银行账户流水", "演示银行 · 账户交易明细", page_no)
        y = field(pdf, "账户户名", case.bank_name if case.index != 4 else None, y, muted=case.quality == "低对比度")
        account = "6222 **** **** 8888" if case.index == 8 else "6222 0000 0000 8888"
        y = field(pdf, "账户号码", account, y)
        y = field(pdf, "查询期间", "2026-04-01 至 2026-08-20", y)
        y -= 5
        pdf.setFillColor(ACCENT)
        pdf.rect(45, y - 24, PAGE_WIDTH - 90, 24, fill=1, stroke=0)
        pdf.setFillColor(colors.white)
        pdf.setFont(FONT, 9)
        for x, text in [(55, "交易日期"), (145, "摘要"), (330, "收入（元）"), (430, "余额（元）")]:
            pdf.drawString(x, y - 16, text)
        y -= 45
        for tx_date, summary, income, balance in transactions(case, page_no):
            pdf.setFillColor(colors.HexColor("#111827"))
            pdf.setFont(FONT, 9)
            pdf.drawString(55, y, tx_date)
            pdf.drawString(145, y, summary)
            pdf.drawRightString(405, y, f"{income:,.2f}" if income else "—")
            pdf.drawRightString(520, y, f"{balance:,.2f}")
            pdf.setStrokeColor(colors.HexColor("#E5E7EB"))
            pdf.line(50, y - 9, PAGE_WIDTH - 50, y - 9)
            y -= 31
        y -= 18
        y = field(pdf, "月均工资性入账", f"人民币 {case.bank_income:,.2f} 元" if case.bank_income is not None else None, y)
        note(pdf, case, y - 5)
        add_watermark(pdf)
        pdf.showPage()
    pdf.save()


def create_blurred_pdf(path: Path, title: str, case: DemoCase, kind: str) -> None:
    image = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(image)
    font_path = "C:/Windows/Fonts/msyh.ttc"
    bold_path = "C:/Windows/Fonts/msyhbd.ttc"
    title_font = ImageFont.truetype(bold_path, 48)
    body_font = ImageFont.truetype(font_path, 29)
    small_font = ImageFont.truetype(font_path, 20)
    draw.rectangle((0, 0, 1240, 220), fill="#173B57")
    draw.text((90, 75), title, fill="white", font=title_font)
    values = {
        "id": [("姓名", case.id_name), ("身份号码", case.id_number), ("住址", "四川省成都市高新区合成路 100 号")],
        "income": [("员工姓名", case.income_name), ("任职单位", case.employer), ("税前月收入", f"{case.certified_income} 元")],
        "bank": [("账户户名", case.bank_name), ("账户号码", "6222 0000 0000 8888"), ("月均工资性入账", f"{case.bank_income} 元")],
    }[kind]
    y = 330
    for label, value in values:
        draw.text((110, y), label, fill="#5B6573", font=body_font)
        draw.text((400, y), str(value or "—"), fill="#111827", font=body_font)
        draw.line((110, y + 58, 1130, y + 58), fill="#CBD2DB", width=2)
        y += 125
    draw.text((110, 1280), f"样本场景：{case.scenario} · 原件成像模糊", fill="#173B57", font=small_font)
    image = image.filter(ImageFilter.GaussianBlur(radius=3.2))
    tmp_png = path.with_suffix(".blur.png")
    image.save(tmp_png, quality=92)
    pdf = canvas.Canvas(str(path), pagesize=A4)
    pdf.drawImage(str(tmp_png), 0, 0, width=PAGE_WIDTH, height=PAGE_HEIGHT)
    add_watermark(pdf)
    pdf.showPage()
    pdf.save()
    tmp_png.unlink()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("data/demo-documents"))
    args = parser.parse_args()
    output_dir: Path = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    setup_fonts()

    manifest: list[dict[str, object]] = []
    generators = {
        "id-cards": ("身份证", create_id_pdf),
        "income-certificates": ("收入证明", create_income_pdf),
        "bank-statements": ("银行流水", create_bank_pdf),
    }
    for folder, (document_type, generator) in generators.items():
        target = output_dir / folder
        target.mkdir(parents=True, exist_ok=True)
        for case in CASES:
            filename = f"{case.index:02d}_{case.scenario}.pdf"
            path = target / filename
            generator(path, case)
            manifest.append(
                {
                    "file": path.relative_to(output_dir).as_posix(),
                    "document_type": document_type,
                    "case_id": f"CASE-{case.index:02d}",
                    "scenario": case.scenario,
                    "quality": case.quality,
                    "expected_pages": case.pages,
                    "synthetic": True,
                    "watermark": WATERMARK,
                }
            )

    payload = {
        "generated_on": date.today().isoformat(),
        "institution": "融安住房金融（虚构演示机构）",
        "notice": "全部内容均为合成数据，仅供功能与面试演示。",
        "documents": manifest,
    }
    (output_dir / "manifest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Generated {len(manifest)} PDFs in {output_dir}")


if __name__ == "__main__":
    main()
