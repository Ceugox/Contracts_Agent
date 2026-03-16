"""
Assistente Contratual Raiz
Gera e revisa contratos PJ do Grupo Raiz Educação — powered by OpenAI
"""

import os
import csv
import json
import re
import base64
from io import BytesIO
from datetime import datetime
from pathlib import Path

import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv
from PyPDF2 import PdfReader
from docx import Document

from contract_generator import generate_contract

load_dotenv()

# ─── Login ─────────────────────────────────────────────────────────────────────

def _get_users() -> dict:
    """
    Lê usuários da env var APP_USERS no formato:  nome:senha,nome2:senha2
    Fallback: APP_PASSWORD cria um usuário genérico 'admin'.
    """
    raw = os.getenv("APP_USERS", "").strip()
    if raw:
        users = {}
        for pair in raw.split(","):
            pair = pair.strip()
            if ":" in pair:
                u, p = pair.split(":", 1)
                users[u.strip()] = p.strip()
        if users:
            return users

    password = os.getenv("APP_PASSWORD", "").strip()
    if password:
        return {"admin": password}

    return {}


def show_login() -> bool:
    """
    Exibe a tela de login. Retorna True se autenticado, False caso contrário.
    Gerencia estado em st.session_state['authenticated'].
    """
    if st.session_state.get("authenticated"):
        return True

    # ── layout centralizado ──
    _, col, _ = st.columns([1, 1.4, 1])
    with col:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown(
            "<h2 style='text-align:center;'>📋 Assistente Contratual</h2>"
            "<p style='text-align:center; color:gray;'>Grupo Raiz Educação</p>",
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)

        with st.form("login_form"):
            username = st.text_input("Usuário", placeholder="seu usuário")
            password = st.text_input("Senha", type="password", placeholder="••••••••")
            submitted = st.form_submit_button("Entrar", use_container_width=True)

        if submitted:
            users = _get_users()
            if not users:
                st.error(
                    "Nenhum usuário configurado. "
                    "Defina APP_USERS ou APP_PASSWORD nas variáveis de ambiente."
                )
            elif username in users and users[username] == password:
                st.session_state["authenticated"] = True
                st.session_state["logged_user"] = username
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")

    return False


# ─── Paths ─────────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent / "data"
TEMPLATE_PATH = DATA_DIR / "contrato_template.docx"
MARCAS_CSV = DATA_DIR / "marcas.csv"
BENEFICIOS_CSV = DATA_DIR / "beneficios.csv"

OPENAI_MODEL = "gpt-4o"

# ─── Data loaders ──────────────────────────────────────────────────────────────

@st.cache_data
def load_marcas() -> dict:
    """Returns {marca: [{razao_social, cnpj, endereco, unidade, diretor_marca}]}"""
    brands: dict = {}
    with open(MARCAS_CSV, encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            if len(row) <= 27:
                continue
            marca = row[2].strip()
            razao = row[3].strip()
            cnpj = row[5].strip()
            if not marca or not razao or cnpj in ("", "**"):
                continue
            endereco = row[9].strip() if row[9].strip() not in ("**", "") else ""
            diretor = row[27].strip()
            if diretor in ("**", "N/A", ""):
                diretor = "André Gusman de Oliveira"
            entry = {
                "razao_social": razao,
                "unidade": row[4].strip(),
                "cnpj": cnpj,
                "endereco": endereco,
                "diretor_marca": diretor,
            }
            brands.setdefault(marca, []).append(entry)
    return brands


@st.cache_data
def load_beneficios() -> dict:
    """Returns {brand_name: {clause_key: value_text}}"""
    pj = {}
    with open(BENEFICIOS_CSV, encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        brand_cols = [b.strip() for b in header[1:] if b.strip()]
        for row in reader:
            if not row or not row[0].strip():
                continue
            beneficio = row[0].strip().upper()
            if "PLANO DE SA" in beneficio:
                key = "saude_odonto"
            elif "DENTAL" in beneficio:
                key = "plano_dental"
            elif "PLUXEE" in beneficio:
                key = "cartao_alimentacao"
            else:
                continue
            for i, brand in enumerate(brand_cols):
                val = row[i + 1].strip() if i + 1 < len(row) else ""
                if val and val != "-":
                    pj.setdefault(brand, {})[key] = val
    return pj


def format_brands_table(brands: dict) -> str:
    lines = ["MARCA | RAZÃO SOCIAL | CNPJ | ENDEREÇO | DIRETOR"]
    for marca, entries in brands.items():
        for e in entries:
            addr = e["endereco"] or "(consultar)"
            lines.append(
                f"{marca} | {e['razao_social']} | {e['cnpj']} | {addr} | {e['diretor_marca']}"
            )
    return "\n".join(lines)


def format_benefits_table(benefits: dict) -> str:
    lines = ["MARCA | PLANO_SAUDE | PLANO_DENTAL | CARTAO_ALIMENTACAO"]
    for brand, bens in benefits.items():
        saude = "SIM" if "saude_odonto" in bens else "NÃO"
        dental = "SIM" if "plano_dental" in bens else "NÃO"
        pluxee = "SIM" if "cartao_alimentacao" in bens else "NÃO"
        lines.append(f"{brand} | {saude} | {dental} | {pluxee}")
    return "\n".join(lines)


# ─── System prompt ─────────────────────────────────────────────────────────────

def build_system_prompt(brands: dict, benefits: dict) -> str:
    today = datetime.now()
    dia = today.strftime("%d")
    mes_map = {
        1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril",
        5: "maio", 6: "junho", 7: "julho", 8: "agosto",
        9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro",
    }
    mes = mes_map[today.month]
    ano = today.strftime("%Y")

    brands_table = format_brands_table(brands)
    benefits_table = format_benefits_table(benefits)

    return f"""Você é o **Assistente Contratual Raiz** — agente especializado em gerar e revisar contratos PJ para o Grupo Raiz Educação S.A.

Data de hoje: {dia} de {mes} de {ano}

## POSTURA
- Profissional, objetiva e assertiva.
- Nunca inventa dados. Nunca altera textos em negrito do modelo original.
- Assume que o usuário pode não conhecer o padrão Raiz: explica desvios, orienta e propõe correções.
- Trabalha sempre com confirmação por etapa antes de avançar.

## LEITURA DE IMAGENS
- O usuário pode enviar imagens (fotos de contratos, documentos, cartões CNPJ, comprovantes etc.).
- Ao receber uma imagem, extraia TODOS os dados relevantes visíveis (razão social, CNPJ, CPF, endereço, nome, valores, datas, atividades, etc.).
- Use os dados extraídos para preencher automaticamente as etapas do fluxo de geração.
- Apresente os dados extraídos de forma organizada e peça confirmação antes de avançar.
- Se algum dado estiver ilegível ou ausente na imagem, informe claramente e peça ao usuário para complementar.

## MODOS DE ATUAÇÃO
**A) GERAÇÃO** — gera o contrato do zero seguindo as etapas abaixo.
**B) REVISÃO/QA** — revisa contrato existente (texto colado ou .docx), lista apontamentos por prioridade: Crítico / Importante / Estético. Não reabre decisões já aprovadas, salvo risco jurídico evidente.

## GUARDAS DE COERÊNCIA
Para qualquer desvio do padrão Raiz:
1. Aponte o desvio objetivamente ("Padrão Raiz vs. Solicitado")
2. Explique o impacto prático
3. Oriente o caminho correto e proponha a correção
4. Peça confirmação antes de aplicar

## FLUXO DE GERAÇÃO (seguir em ordem)

**Etapa 1 — Cabeçalho CONTRATANTE**
Pergunte a marca. Consulte a tabela de marcas abaixo. Se a marca tiver múltiplas unidades/CNPJs, liste as opções e peça para o usuário escolher.
Exiba o cabeçalho completo (razão social, CNPJ, endereço, diretor) e aguarde confirmação.

**Etapa 2 — Dados da CONTRATADA**
Colete: razão social, CNPJ (14 dígitos, formato XX.XXX.XXX/XXXX-XX), endereço completo.
Valide: CNPJ não pode ser igual ao da CONTRATANTE.

**Etapa 3 — Dados do REPRESENTANTE**
Colete: nome completo, CPF (11 dígitos, formato XXX.XXX.XXX-XX), endereço completo.

**Etapa 4 — Atividades ({{[ATIVIDADES]}})**
Aceite texto livre. Formate em lista numerada. Confirme com o usuário.

**Etapa 5 — Datas e Valores**
- Data de início (DD/MM/AAAA)
- Salário mensal: valor em R$ X.XXX,XX E por extenso
- Valide coerência entre o número e o extenso.

**Etapa 6 — Benefícios / Cláusulas Opcionais**
Consulte o mapa de benefícios abaixo para a marca escolhida.
Apresente checklist SIM/NÃO para cada cláusula:
- [ ] Afastamento remunerado (30 dias/ano) — Cláusula 1.3
- [ ] Plano de saúde + odontológico — Cláusulas 4.1.3 e 4.1.4
- [ ] Cartão Pluxee R$400/mês — Cláusula 4.1.5
- [ ] Valor Adicional Anual (1 salário em dezembro) — Cláusula 4.2.1
- [ ] Valor Adicional Variável (bônus por metas) — Cláusula 4.2.2
- [ ] Valor Adicional ao Afastamento (1/3 salário; só se afastamento=SIM) — Cláusula 4.2.3

Se os benefícios informados diferirem do mapa padrão, aponte a divergência, pergunte o motivo e peça confirmação.

**Etapa 7 — Confirmação Final**
Apresente resumo completo de todos os dados e cláusulas ativas.
Aguarde o usuário confirmar com "confirmar", "ok", "sim" ou equivalente.

**Etapa 8 — Emissão**
Após confirmação, emita o bloco JSON de geração (ver formato abaixo).

## CLÁUSULAS OPCIONAIS — IDENTIFICADORES
- `afastamento_remunerado` → Cláusula 1.3
- `saude_odonto` → Cláusulas 4.1.3 + 4.1.4 (saúde e odontológico juntos)
- `cartao_alimentacao` → Cláusula 4.1.5 (Pluxee R$400/mês)
- `valor_adicional_anual` → Cláusula 4.2.1 (1 salário em dezembro)
- `valor_adicional_variavel` → Cláusula 4.2.2 (bônus por metas)
- `valor_adicional_afastamento` → Cláusula 4.2.3 (só ativa se afastamento_remunerado=true)

## TABELA DE MARCAS
```
{brands_table}
```

## MAPA DE BENEFÍCIOS PJ POR MARCA
```
{benefits_table}
```

## FORMATO DE SAÍDA PARA GERAÇÃO DE CONTRATO
Quando todos os dados estiverem coletados e confirmados pelo usuário, emita EXATAMENTE o bloco abaixo ao FINAL da sua mensagem.
Não omita nenhum campo. Preencha todos os valores corretamente.

[CONTRATO_PRONTO]
{{
  "contratante": {{
    "razao_social": "",
    "cnpj": "",
    "endereco": "",
    "diretor": ""
  }},
  "contratada": {{
    "razao_social": "",
    "cnpj": "",
    "endereco": ""
  }},
  "representante": {{
    "nome": "",
    "cpf": "",
    "endereco": ""
  }},
  "atividades": [""],
  "data_inicio": "DD/MM/AAAA",
  "salario": "X.XXX,XX",
  "salario_extenso": "... reais",
  "dia_atual": "{dia}",
  "mes_atual": "{mes}",
  "ano": "{ano}",
  "clausulas_ativas": {{
    "afastamento_remunerado": false,
    "saude_odonto": false,
    "cartao_alimentacao": false,
    "valor_adicional_anual": false,
    "valor_adicional_variavel": false,
    "valor_adicional_afastamento": false
  }}
}}
[/CONTRATO_PRONTO]
"""


# ─── Streamlit UI ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Assistente Contratual Raiz",
    page_icon="📋",
    layout="centered",
)

# ── Autenticação ── deve vir antes de qualquer conteúdo ──
if not show_login():
    st.stop()

st.title("📋 Assistente Contratual Raiz")
st.caption("Geração e revisão de contratos PJ · Grupo Raiz Educação")

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuração")

    # Logout
    user = st.session_state.get("logged_user", "")
    st.markdown(f"👤 **{user}**")
    if st.button("Sair", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
    st.divider()

    st.header("📌 Modo")
    mode = st.radio(
        "Selecione o modo de operação:",
        ["🆕 Gerar Contrato", "🔍 Revisar / QA"],
        label_visibility="collapsed",
    )

    st.divider()
    if st.button("🔄 Nova Conversa", use_container_width=True):
        for key in ["messages", "openai_messages", "generated_contract"]:
            st.session_state.pop(key, None)
        st.rerun()

    st.divider()
    st.caption(
        f"**Modelo:** {OPENAI_MODEL}\n\n"
        "**Suporta:** texto e imagens"
    )

# Load data
brands = load_marcas()
benefits = load_beneficios()
system_prompt = build_system_prompt(brands, benefits)

# Session state initialization
if "messages" not in st.session_state:
    st.session_state.messages = []
if "openai_messages" not in st.session_state:
    st.session_state.openai_messages = []
if "generated_contract" not in st.session_state:
    st.session_state.generated_contract = None

# Download button (shown when contract is ready)
if st.session_state.generated_contract:
    filename = f"Contrato_PJ_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
    st.download_button(
        label="⬇️ Baixar Contrato (.docx)",
        data=st.session_state.generated_contract,
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        use_container_width=True,
        type="primary",
    )
    st.divider()

# Display conversation history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg.get("images"):
            for img_data in msg["images"]:
                st.image(base64.b64decode(img_data["b64"]), caption=img_data["name"], width=300)
        if msg.get("docs"):
            for doc_name in msg["docs"]:
                st.caption(f"📄 {doc_name}")
        st.markdown(msg["content"])

# Show welcome message if empty
if not st.session_state.messages:
    with st.chat_message("assistant"):
        if "Gerar" in mode:
            welcome = (
                "Olá! Sou o **Assistente Contratual Raiz** 👋\n\n"
                "Vou guiá-lo(a) passo a passo na geração de um contrato PJ padrão Raiz.\n\n"
                "Para começar: **qual é a marca da CONTRATANTE?**\n\n"
                "*(Ex.: HOLDING, QI, PRO RAIZ, CUBO GLOBAL, APOGEU...)*\n\n"
                "💡 *Você pode anexar imagens, PDFs ou DOCX junto com sua mensagem.*"
            )
        else:
            welcome = (
                "Olá! Sou o **Assistente Contratual Raiz** 👋\n\n"
                "Modo **Revisão / QA** ativo.\n\n"
                "Cole aqui o texto do contrato que deseja revisar, ou descreva o que precisa verificar.\n\n"
                "💡 *Você pode anexar imagens, PDFs ou DOCX de contratos para análise.*"
            )
        st.markdown(welcome)

# ─── API key (loaded from environment, no user input needed) ──────────────────
api_key = os.getenv("OPENAI_API_KEY", "")

# ─── File uploader + Chat input ──────────────────────────────────────────────
uploaded_files = st.file_uploader(
    "📎 Anexar arquivos",
    type=["png", "jpg", "jpeg", "gif", "webp", "pdf", "docx"],
    accept_multiple_files=True,
    key="file_uploader",
    label_visibility="collapsed",
)

if uploaded_files:
    img_files = [f for f in uploaded_files if f.name.rsplit(".", 1)[-1].lower() in ("png", "jpg", "jpeg", "gif", "webp")]
    doc_files = [f for f in uploaded_files if f.name.rsplit(".", 1)[-1].lower() in ("pdf", "docx")]
    if img_files:
        cols = st.columns(min(len(img_files), 4))
        for i, img_file in enumerate(img_files):
            with cols[i % 4]:
                st.image(img_file, caption=img_file.name, width=120)
    if doc_files:
        for doc in doc_files:
            st.caption(f"📄 {doc.name}")

if prompt := st.chat_input("Digite sua mensagem (pode anexar arquivos acima)..."):
    if not api_key:
        st.error("⚠️ API Key da OpenAI não configurada. Defina OPENAI_API_KEY nas variáveis de ambiente.")
        st.stop()

    # Process uploaded files
    image_contents = []
    doc_texts = []
    if uploaded_files:
        for ufile in uploaded_files:
            ext = ufile.name.rsplit(".", 1)[-1].lower()
            if ext in ("png", "jpg", "jpeg", "gif", "webp"):
                img_bytes = ufile.getvalue()
                b64 = base64.b64encode(img_bytes).decode("utf-8")
                mime = f"image/{'jpeg' if ext in ('jpg', 'jpeg') else ext}"
                image_contents.append({"b64": b64, "mime": mime, "name": ufile.name})
            elif ext == "pdf":
                try:
                    reader = PdfReader(BytesIO(ufile.getvalue()))
                    text = "\n".join(page.extract_text() or "" for page in reader.pages)
                    doc_texts.append({"name": ufile.name, "text": text.strip()})
                except Exception as e:
                    doc_texts.append({"name": ufile.name, "text": f"[Erro ao ler PDF: {e}]"})
            elif ext == "docx":
                try:
                    doc = Document(BytesIO(ufile.getvalue()))
                    text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
                    doc_texts.append({"name": ufile.name, "text": text.strip()})
                except Exception as e:
                    doc_texts.append({"name": ufile.name, "text": f"[Erro ao ler DOCX: {e}]"})

    # Build display content
    file_labels = []
    if image_contents:
        file_labels += [f"📎 *{img['name']}*" for img in image_contents]
    if doc_texts:
        file_labels += [f"📄 *{doc['name']}*" for doc in doc_texts]

    # Append to UI messages
    st.session_state.messages.append({
        "role": "user",
        "content": prompt,
        "images": [{"b64": img["b64"], "name": img["name"]} for img in image_contents] if image_contents else None,
        "docs": [doc["name"] for doc in doc_texts] if doc_texts else None,
    })
    with st.chat_message("user"):
        if image_contents:
            for img in image_contents:
                st.image(base64.b64decode(img["b64"]), caption=img["name"], width=300)
        if doc_texts:
            for doc in doc_texts:
                st.caption(f"📄 {doc['name']}")
        st.markdown(prompt)

    # Build OpenAI message content (text + images + doc text)
    extra_text = ""
    if doc_texts:
        for doc in doc_texts:
            extra_text += f"\n\n--- Conteúdo do arquivo {doc['name']} ---\n{doc['text']}\n--- Fim do arquivo ---"

    full_text = prompt + extra_text

    if image_contents:
        user_content = []
        for img in image_contents:
            user_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:{img['mime']};base64,{img['b64']}"},
            })
        user_content.append({"type": "text", "text": full_text})
    else:
        user_content = full_text

    st.session_state.openai_messages.append({"role": "user", "content": user_content})

    # Get AI response
    client = OpenAI(api_key=api_key)

    with st.chat_message("assistant"):
        with st.spinner("Processando..."):
            try:
                messages_for_api = [
                    {"role": "system", "content": system_prompt},
                ] + st.session_state.openai_messages

                response = client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=messages_for_api,
                )
                response_text = response.choices[0].message.content

                # Append assistant message to OpenAI history
                st.session_state.openai_messages.append(
                    {"role": "assistant", "content": response_text}
                )

                # Check for contract generation trigger
                match = re.search(
                    r"\[CONTRATO_PRONTO\](.*?)\[/CONTRATO_PRONTO\]",
                    response_text,
                    re.DOTALL,
                )

                if match:
                    try:
                        contract_data = json.loads(match.group(1).strip())
                        contract_bytes = generate_contract(
                            contract_data, str(TEMPLATE_PATH)
                        )
                        st.session_state.generated_contract = contract_bytes

                        display_text = response_text[: match.start()].strip()
                        display_text += (
                            "\n\n✅ **Contrato gerado com sucesso!** "
                            "Clique no botão de download no topo da página para baixar o arquivo .docx."
                        )
                        st.markdown(display_text)
                        st.session_state.messages.append(
                            {"role": "assistant", "content": display_text}
                        )
                        st.rerun()

                    except json.JSONDecodeError as e:
                        st.markdown(response_text)
                        st.error(f"Erro ao interpretar os dados do contrato: {e}")
                        st.session_state.messages.append(
                            {"role": "assistant", "content": response_text}
                        )
                    except Exception as e:
                        st.markdown(response_text)
                        st.error(f"Erro ao gerar o documento: {e}")
                        st.session_state.messages.append(
                            {"role": "assistant", "content": response_text}
                        )
                else:
                    st.markdown(response_text)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": response_text}
                    )

            except Exception as e:
                error_msg = f"❌ Erro na comunicação com a OpenAI: {str(e)}"
                st.error(error_msg)
                st.info(
                    "Verifique se a API Key está correta e se você tem cota disponível."
                )
