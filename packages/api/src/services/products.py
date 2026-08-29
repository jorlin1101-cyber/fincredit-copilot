# This project was developed with assistance from AI tools.
"""Chinese housing-loan product catalog for the public demo.

Historical enum identifiers are retained for API and seeded-data
compatibility. Public names, amounts and explanations use the China scenario.
Eligibility numbers are explicitly labelled as internal demo review lines.
"""

from ..schemas.products import ProductEligibility, ProductInfo

_LPR_SOURCE = "https://www.chinamoney.com.cn/chinese/rdgz/20260820/3399885.html"
_PROVIDENT_SOURCE = "https://szgjj.hebei.gov.cn/2026-03/23/content_9491962.htm"
_LPR_NOTE = (
    "3.5%为2026年8月20日五年期以上LPR，仅作长期商业贷款测算基准；"
    "实际住房贷款利率由贷款机构按合同和借款人情况确定。"
)
_PROVIDENT_NOTE = (
    "2.6%为首套住房公积金贷款五年以上公开执行利率参考；"
    "须由成都公积金中心或受理银行核验申请当日政策。"
)


def _eligibility(
    *,
    min_credit_score: int = 600,
    max_dti_pct: float = 50.0,
    max_ltv_pct: float = 85.0,
    special_requirements: str | None = None,
) -> ProductEligibility:
    note = "以下为虚构机构内部演示复核线，不是监管部门统一审批标准"
    requirements = f"{note}；{special_requirements}" if special_requirements else note
    return ProductEligibility(
        min_credit_score=min_credit_score,
        max_dti_pct=max_dti_pct,
        max_ltv_pct=max_ltv_pct,
        special_requirements=requirements,
    )


PRODUCTS: list[ProductInfo] = [
    ProductInfo(
        id="conventional_30",
        name="30年期商业性个人住房贷款",
        description="以人民币发放、通常采用LPR加减点定价的长期住房按揭贷款。",
        min_down_payment_pct=15.0,
        typical_rate=3.5,
        eligibility=_eligibility(),
        rate_note=_LPR_NOTE,
        source_name="全国银行间同业拆借中心受权公布LPR公告",
        source_url=_LPR_SOURCE,
        data_as_of="2026-08-20",
    ),
    ProductInfo(
        id="conventional_15",
        name="15年期商业性个人住房贷款",
        description="期限较短、月供通常较高，适合希望缩短还款周期的购房客户。",
        min_down_payment_pct=15.0,
        typical_rate=3.5,
        eligibility=_eligibility(),
        rate_note=_LPR_NOTE,
        source_name="全国银行间同业拆借中心受权公布LPR公告",
        source_url=_LPR_SOURCE,
        data_as_of="2026-08-20",
    ),
    ProductInfo(
        id="fha",
        name="住房公积金个人住房贷款",
        description="面向符合缴存及当地公积金政策条件的购房客户，资格和额度须按成都规则核验。",
        min_down_payment_pct=15.0,
        typical_rate=2.6,
        eligibility=_eligibility(
            min_credit_score=580,
            special_requirements="须满足成都住房公积金缴存、房屋和贷款资格要求",
        ),
        rate_note=_PROVIDENT_NOTE,
        source_name="成都公积金贷款政策公开信息",
        source_url=_PROVIDENT_SOURCE,
        data_as_of="2026-08-28",
    ),
    ProductInfo(
        id="va",
        name="商业贷款与公积金组合贷款",
        description="同时使用住房公积金贷款和商业性个人住房贷款，分别按对应规则计息和审批。",
        min_down_payment_pct=15.0,
        typical_rate=3.5,
        eligibility=_eligibility(
            special_requirements="演示利率只用于商贷部分测算，公积金部分须单独计算"
        ),
        rate_note=_LPR_NOTE,
        source_name="全国银行间同业拆借中心受权公布LPR公告",
        source_url=_LPR_SOURCE,
        data_as_of="2026-08-20",
    ),
    ProductInfo(
        id="jumbo",
        name="大额商业性个人住房贷款",
        description="贷款金额较大的商业住房贷款，贷款机构通常会加强收入、资产和首付款来源核验。",
        min_down_payment_pct=20.0,
        typical_rate=3.5,
        eligibility=_eligibility(min_credit_score=680, max_ltv_pct=80.0),
        rate_note=_LPR_NOTE,
        source_name="全国银行间同业拆借中心受权公布LPR公告",
        source_url=_LPR_SOURCE,
        data_as_of="2026-08-20",
    ),
    ProductInfo(
        id="usda",
        name="县域住房贷款（演示产品）",
        description="用于展示县域住房场景的内部演示产品，不代表政府专项贷款或真实银行产品。",
        min_down_payment_pct=15.0,
        typical_rate=3.5,
        eligibility=_eligibility(special_requirements="须人工核验房屋用途、区位和权属材料"),
        rate_note=_LPR_NOTE,
        source_name="全国银行间同业拆借中心受权公布LPR公告",
        source_url=_LPR_SOURCE,
        data_as_of="2026-08-20",
    ),
    ProductInfo(
        id="arm",
        name="LPR浮动利率个人住房贷款",
        description="合同利率按约定重定价周期随LPR变化，具体加减点和调整方式以借款合同为准。",
        min_down_payment_pct=15.0,
        typical_rate=3.5,
        eligibility=_eligibility(),
        rate_note=_LPR_NOTE,
        source_name="全国银行间同业拆借中心受权公布LPR公告",
        source_url=_LPR_SOURCE,
        data_as_of="2026-08-20",
    ),
]
