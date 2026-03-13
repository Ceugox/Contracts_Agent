# Assistente Contratual Raiz — Como Usar

## Configuração (1 vez só)

### 1. Obter a API Key gratuita do Google Gemini

1. Acesse: https://aistudio.google.com/app/apikey
2. Faça login com sua conta Google
3. Clique em **"Create API key"**
4. Copie a chave gerada (começa com `AIza...`)

> ✅ **Gratuito:** 1.500 requisições/dia, sem cartão de crédito.

### 2. Configurar a chave (opcional — facilita o uso)

Copie o arquivo `.env.example` para `.env` e cole sua chave:

```
GEMINI_API_KEY=AIza...sua_chave_aqui
```

Ou deixe em branco e insira a chave diretamente na barra lateral do app.

### 3. Instalar as dependências

Abra o terminal na pasta `contrato-raiz-app` e execute:

```bash
pip install -r requirements.txt
```

### 4. Iniciar o app

```bash
streamlit run app.py
```

O app abrirá automaticamente no navegador em `http://localhost:8501`

---

## Como usar o app

### Modo A: Gerar Contrato
1. Selecione **"Gerar Contrato"** na barra lateral
2. O assistente pedirá as informações passo a passo:
   - Marca da CONTRATANTE
   - Dados da CONTRATADA (razão social, CNPJ, endereço)
   - Dados do Representante (nome, CPF, endereço)
   - Atividades
   - Data de início e salário
   - Benefícios / cláusulas opcionais
3. Confirme os dados quando solicitado
4. O arquivo `.docx` ficará disponível para download

### Modo B: Revisar / QA
1. Selecione **"Revisar / QA"** na barra lateral
2. Cole o texto do contrato ou descreva o que quer revisar
3. O assistente listará os apontamentos por prioridade (Crítico / Importante / Estético)

---

## Arquivos do projeto

```
contrato-raiz-app/
├── app.py                  ← App principal (Streamlit)
├── contract_generator.py   ← Geração do .docx
├── requirements.txt        ← Dependências
├── .env                    ← Sua API Key (criar a partir do .env.example)
└── .env.example            ← Modelo do .env
```

Os dados das planilhas e o modelo do contrato são lidos diretamente de:
`C:\Users\marce\Documents\Raíz Educação\Projeto-Contrato PJ\`

---

## Solução de problemas

**"Erro na comunicação com o Gemini"**
- Verifique se a API Key está correta
- Confira se há cota disponível em: https://aistudio.google.com/

**"streamlit não é reconhecido como comando"**
- Use: `python -m streamlit run app.py`

**O contrato gerado tem caracteres estranhos**
- Isso é visual apenas no terminal. O arquivo .docx abre corretamente no Word.
