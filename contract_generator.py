"""
Contract generator for Raiz Educação PJ contracts.
Fills the template .docx with variable data and handles optional clauses.
"""

from docx import Document
from io import BytesIO
import re

# Maps the clause identifier (prefix inside {{ }}) to the data key
OPTIONAL_CLAUSE_MAP = {
    "1.3.": "afastamento_remunerado",
    "4.1.3.": "saude_odonto",
    "4.1.5.": "cartao_alimentacao",
    "4.2.1.": "valor_adicional_anual",
    "4.2.2.": "valor_adicional_variavel",
    "4.2.3.": "valor_adicional_afastamento",
}

# Hardcoded HOLDING values in the template that must be replaced for other brands
HOLDING_ADDRESS = "Freeway Center - Av. das Américas, 2000 - Loja 5 - Barra da Tijuca, Rio de Janeiro - RJ, 22640-100"
HOLDING_CNPJ = "21.219.576/0001-14"
HOLDING_DIRECTOR = "André Gusman de Oliveira"


def get_paragraph_text(paragraph) -> str:
    return "".join(r.text for r in paragraph.runs)


def detect_optional_clause(paragraph) -> str | None:
    """
    Returns the clause_id if the paragraph is an optional clause, else None.
    Optional clauses have the full text wrapped in {{ }}.
    """
    text = get_paragraph_text(paragraph).strip()
    if not (text.startswith("{{") and text.rstrip("\n").endswith("}}")):
        return None
    inner = text[2:].lstrip()
    for prefix, clause_id in OPTIONAL_CLAUSE_MAP.items():
        if inner.startswith(prefix):
            return clause_id
    return None


def strip_optional_wrappers(paragraph):
    """Remove the {{ and }} wrapper runs from an activated optional clause."""
    runs = paragraph.runs
    if not runs:
        return
    # Remove leading {{
    if runs[0].text == "{{":
        runs[0].text = ""
    # Remove trailing }}
    for run in reversed(runs):
        stripped = run.text.rstrip("\n")
        if stripped == "}}":
            run.text = run.text.replace("}}", "", 1)
            break
        elif stripped.endswith("}}"):
            run.text = run.text.replace("}}", "", 1)
            break


def replace_in_runs(runs, replacements: dict):
    """
    Replace template variables in a list of runs.
    Handles the 3-run pattern: run('{{') + run('VARNAME') + run('}}')
    Falls back to single-run replacement for plain text substitutions.
    """
    n = len(runs)
    i = 0
    while i < n:
        run = runs[i]

        # 3-run pattern: '{{' + 'VARNAME' + '}}'
        if run.text == "{{" and i + 2 < n:
            closing_text = runs[i + 2].text.rstrip("\n")
            if closing_text == "}}":
                var_key = "{{" + runs[i + 1].text + "}}"
                if var_key in replacements:
                    after = runs[i + 2].text[len(closing_text):]  # preserve trailing \n
                    run.text = replacements[var_key]
                    runs[i + 1].text = ""
                    runs[i + 2].text = after
                    i += 3
                    continue

        # Single-run fallback: plain text replacement
        for key, val in replacements.items():
            if key in run.text:
                run.text = run.text.replace(key, val)

        i += 1


def generate_contract(data: dict, template_path: str) -> bytes:
    """
    Generate a filled .docx contract from the template.

    Expected data structure:
    {
        "contratante": {"razao_social", "cnpj", "endereco", "diretor"},
        "contratada":  {"razao_social", "cnpj", "endereco"},
        "representante": {"nome", "cpf", "endereco"},
        "atividades": [str, ...],
        "data_inicio": "DD/MM/AAAA",
        "salario": "X.XXX,XX",
        "salario_extenso": "... reais",
        "dia_atual": "DD",
        "mes_atual": "Mês por extenso",
        "ano": "AAAA",
        "clausulas_ativas": {
            "afastamento_remunerado": bool,
            "saude_odonto": bool,
            "cartao_alimentacao": bool,
            "valor_adicional_anual": bool,
            "valor_adicional_variavel": bool,
            "valor_adicional_afastamento": bool
        }
    }
    """
    doc = Document(template_path)

    atividades = data.get("atividades", [])
    atividades_text = "\n".join(f"{i + 1}. {a}" for i, a in enumerate(atividades))

    contratante = data["contratante"]
    contratada = data["contratada"]
    representante = data["representante"]

    replacements = {
        # CONTRATANTE variables (preâmbulo and signature)
        "{{RAIZ EDUCAÇÃO S.A.}}": contratante["razao_social"],
        # Hardcoded HOLDING values — replaced for any brand
        HOLDING_ADDRESS: contratante["endereco"],
        HOLDING_CNPJ: contratante["cnpj"],
        HOLDING_DIRECTOR: contratante.get("diretor", HOLDING_DIRECTOR),
        # CONTRATADA variables
        "{{NOME DA RAZÃO SOCIAL}}": contratada["razao_social"],
        "{{ENDEREÇO DA RAZÃO SOCIAL}}": contratada["endereco"],
        "{{CNPJ}}": contratada["cnpj"],
        # REPRESENTANTE variables
        "{{NOME DO FAVORECIDO}}": representante["nome"],
        "{{CPF}}": representante["cpf"],
        "{{ENDEREÇO DO FAVORECIDO}}": representante["endereco"],
        # Contract body
        "{{[ATIVIDADES]}}": atividades_text,
        "{{DATA DE INÍCIO}}": data["data_inicio"],
        "{{SALÁRIO}}": data["salario"],
        "{{SALÁRIO POR EXTENSO}}": data["salario_extenso"],
        # Signature block date
        "{{DIA ATUAL}}": data["dia_atual"],
        "{{MÊS ATUAL}}": data["mes_atual"],
        "2025": data.get("ano", "2025"),
        # Signature block CONTRATADA
        "{{RAZÃO SOCIAL}}": contratada["razao_social"],
    }

    clausulas = data.get("clausulas_ativas", {})
    paragraphs_to_delete = []

    for para in doc.paragraphs:
        clause_id = detect_optional_clause(para)

        if clause_id is not None:
            if clausulas.get(clause_id, False):
                # Activated: strip {{ }} and apply replacements
                strip_optional_wrappers(para)
                replace_in_runs(para.runs, replacements)
            else:
                # Deactivated: mark for deletion
                paragraphs_to_delete.append(para._element)
        else:
            replace_in_runs(para.runs, replacements)

    # Delete deactivated paragraphs (safe to remove after iteration)
    for p_elem in paragraphs_to_delete:
        parent = p_elem.getparent()
        if parent is not None:
            parent.remove(p_elem)

    output = BytesIO()
    doc.save(output)
    output.seek(0)
    return output.getvalue()
