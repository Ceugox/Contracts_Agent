# 📋 Assistente Contratual Raiz

Agente de IA para geração e revisão de contratos PJ do **Grupo Raiz Educação S.A.**

Powered by **Google Gemini 2.5 Flash** · Interface web via **Streamlit** · 100% gratuito.

---

## Funcionalidades

### Modo A — Geração de Contrato
Coleta os dados passo a passo via chat:
- Consulta automática de marcas (razão social, CNPJ, endereço)
- Validação de CPF, CNPJ, datas e coerência salário × extenso
- Ativação/desativação das cláusulas opcionais conforme mapa de benefícios
- Exporta o contrato preenchido em `.docx` preservando toda a formatação original

### Modo B — Revisão / QA
- Analisa contratos existentes (texto colado)
- Lista apontamentos por prioridade: **Crítico / Importante / Estético**
- Identifica desvios do padrão Raiz sem reabrir decisões já aprovadas

---

## Cláusulas opcionais suportadas

| Cláusula | Descrição |
|----------|-----------|
| 1.3 | Afastamento remunerado (30 dias/ano) |
| 4.1.3 + 4.1.4 | Plano de saúde e odontológico |
| 4.1.5 | Cartão Pluxee R$ 400/mês |
| 4.2.1 | Valor Adicional Anual (1 salário em dezembro) |
| 4.2.2 | Valor Adicional Variável (bônus por metas) |
| 4.2.3 | Valor Adicional ao Afastamento (1/3 salário) |

---

## Deploy (Railway)

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app)

1. Faça fork/clone deste repositório
2. No Railway: **New Project → Deploy from GitHub repo**
3. Adicione a variável de ambiente:
   ```
   GEMINI_API_KEY=sua_chave_aqui
   ```
4. Railway → **Settings → Networking → Generate Domain**

> API Key gratuita: [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
> Limite gratuito: 1.500 requisições/dia, sem cartão de crédito.

---

## Rodar localmente

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Configurar API Key
cp .env.example .env
# edite o .env e cole sua GEMINI_API_KEY

# 3. Iniciar
streamlit run app.py
```

Acesse: `http://localhost:8501`

---

## Estrutura do projeto

```
├── app.py                  # App principal (Streamlit + Gemini)
├── contract_generator.py   # Geração do .docx com python-docx
├── data/
│   ├── contrato_template.docx   # Modelo oficial do contrato PJ
│   ├── marcas.csv               # Dados das marcas (razão social, CNPJ, endereço)
│   └── beneficios.csv           # Mapa de benefícios por marca
├── Procfile                # Configuração para Railway
├── requirements.txt
└── runtime.txt
```

---

## Tecnologias

- [Streamlit](https://streamlit.io) — interface web
- [Google Gemini](https://ai.google.dev) — modelo de linguagem (free tier)
- [python-docx](https://python-docx.readthedocs.io) — geração do `.docx`
