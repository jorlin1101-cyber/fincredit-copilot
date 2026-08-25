# This project was developed with assistance from AI tools.
"""Document extraction prompt templates and field definitions.

Keeps prompt construction separate from the extraction service so prompts
can be reviewed and iterated on independently.
"""

EXTRACTION_FIELDS: dict[str, list[str]] = {
    "id_card": [
        "full_name",
        "id_number",
        "date_of_birth",
        "address",
        "issuing_authority",
        "valid_from",
        "valid_until",
    ],
    "income_certificate": [
        "employee_name",
        "employer_name",
        "employer_unified_credit_code",
        "position",
        "employment_start_date",
        "monthly_gross_income",
        "annual_gross_income",
        "issue_date",
        "contact_phone",
    ],
    "w2": [
        "employer_name",
        "employee_name",
        "tax_year",
        "wages",
        "federal_tax_withheld",
        "state_tax_withheld",
    ],
    "pay_stub": [
        "employer_name",
        "pay_period_start",
        "pay_period_end",
        "gross_pay",
        "net_pay",
        "ytd_gross_pay",
    ],
    "bank_statement": [
        "bank_name",
        "account_holder_name",
        "account_number_last4",
        "statement_period_start",
        "statement_period_end",
        "opening_balance",
        "ending_balance",
        "salary_credit_total",
        "salary_credit_monthly_average",
    ],
    "tax_return": [
        "tax_year",
        "filing_status",
        "adjusted_gross_income",
        "total_tax",
        "taxable_income",
    ],
    "drivers_license": [
        "full_name",
        "date_of_birth",
        "license_number_last4",
        "expiration_date",
        "issuing_state",
    ],
    "passport": [
        "full_name",
        "date_of_birth",
        "passport_number_last4",
        "expiration_date",
        "issuing_country",
    ],
    "homeowners_insurance": [
        "insurer_name",
        "policy_number",
        "insured_name",
        "property_address",
        "coverage_amount",
        "premium_amount",
        "effective_date",
        "expiration_date",
    ],
    "title_insurance": [
        "insurer_name",
        "policy_number",
        "property_address",
        "coverage_amount",
        "effective_date",
    ],
    "flood_insurance": [
        "insurer_name",
        "policy_number",
        "property_address",
        "coverage_amount",
        "premium_amount",
        "effective_date",
        "expiration_date",
        "flood_zone",
    ],
    "purchase_agreement": [
        "buyer_name",
        "seller_name",
        "property_address",
        "purchase_price",
        "earnest_money",
        "closing_date",
    ],
    "gift_letter": [
        "donor_name",
        "recipient_name",
        "gift_amount",
        "relationship",
        "date_signed",
    ],
}

QUALITY_FLAGS = [
    "blurry",
    "incomplete",
    "wrong_period",
    "future_date",
    "document_type_mismatch",
    "unsigned",
    "low_confidence",
    "evidence_not_found",
    "page_extraction_failed",
    "cross_page_document_type_conflict",
]

# Only demographic fields that must be blocked from the lending path.
# Non-demographic HMDA fields (income, DTI, etc.) flow through normally.
VALID_DOC_TYPES = [
    "id_card",
    "income_certificate",
    "w2",
    "pay_stub",
    "tax_return",
    "bank_statement",
    "drivers_license",
    "passport",
    "property_appraisal",
    "homeowners_insurance",
    "title_insurance",
    "flood_insurance",
    "purchase_agreement",
    "gift_letter",
    "other",
]

HMDA_DEMOGRAPHIC_KEYWORDS: set[str] = {
    "race",
    "ethnicity",
    "sex",
    "gender",  # LLM variant of sex
    "age",
    "age_group",  # LLM variant of age
}


def build_extraction_prompt(doc_type: str, text: str, source_page: int = 1) -> list[dict]:
    """Build messages for text-based LLM extraction."""
    fields = EXTRACTION_FIELDS.get(doc_type, [])
    fields_csv = ", ".join(fields) if fields else "any relevant fields"

    system_msg = (
        "你是住房贷款材料抽取助手。请从当前这一页的中文或英文材料中抽取结构化字段。"
        "严禁猜测，不得使用页面之外的信息。"
        "Respond ONLY with valid JSON matching this schema:\n"
        "{\n"
        '  "extractions": [\n'
        '    {"field_name": "<name>", "field_value": "<value>", '
        '"confidence": <0.0-1.0>, "source_page": <int>, '
        '"evidence_text": "<verbatim short text from this page>"}\n'
        "  ],\n"
        f'  "quality_flags": [<zero or more of: {", ".join(QUALITY_FLAGS)}>],\n'
        f'  "detected_doc_type": "<one of: {", ".join(VALID_DOC_TYPES)}>"\n'
        "}\n\n"
        f"The uploader tagged this document as: {doc_type}\n"
        f"Current page number: {source_page}. Every source_page must equal {source_page}.\n"
        "For detected_doc_type, classify based on the ACTUAL document content, "
        "NOT the uploader's tag. If the content is clearly a different type, "
        "use the correct type.\n"
        f"Expected fields: {fields_csv}\n"
        "IMPORTANT: If the document contains any demographic or government "
        "monitoring information (race, ethnicity, sex, gender, age), "
        "extract those fields as well.\n"
        "evidence_text 必须是当前页可核验的简短原文，并且包含或直接支持 field_value。"
        "如果字段不存在就省略，不得猜测；金额和日期保留原始写法，标准化由程序完成。"
    )

    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": f"Extract data from this document:\n\n{text}"},
    ]


def build_image_extraction_prompt(doc_type: str, source_page: int = 1) -> dict:
    """Build system message for image-based LLM extraction.

    The image content block is added separately by the caller.
    """
    fields = EXTRACTION_FIELDS.get(doc_type, [])
    fields_csv = ", ".join(fields) if fields else "any relevant fields"

    return {
        "role": "system",
        "content": (
            "你是住房贷款材料抽取助手。请从当前这一页图像中抽取结构化字段。"
            "严禁猜测，不得使用图像之外的信息。"
            "Respond ONLY with valid JSON matching this schema:\n"
            "{\n"
            '  "extractions": [\n'
            '    {"field_name": "<name>", "field_value": "<value>", '
            '"confidence": <0.0-1.0>, "source_page": <int>, '
            '"evidence_text": "<verbatim short text from this page>"}\n'
            "  ],\n"
            f'  "quality_flags": [<zero or more of: {", ".join(QUALITY_FLAGS)}>],\n'
            f'  "detected_doc_type": "<one of: {", ".join(VALID_DOC_TYPES)}>"\n'
            "}\n\n"
            f"The uploader tagged this document as: {doc_type}\n"
            f"Current page number: {source_page}. Every source_page must equal {source_page}.\n"
            "For detected_doc_type, classify based on the ACTUAL document content, "
            "NOT the uploader's tag. If the content is clearly a different type, "
            "use the correct type.\n"
            f"Expected fields: {fields_csv}\n"
            "IMPORTANT: If the document contains any demographic or government "
            "monitoring information (race, ethnicity, sex, gender, age), "
            "extract those fields as well.\n"
            "evidence_text 必须是当前页图像中可核验的简短原文，并且包含或直接支持 field_value。"
            "如果字段不存在就省略，不得猜测；金额和日期保留原始写法，标准化由程序完成。"
        ),
    }
