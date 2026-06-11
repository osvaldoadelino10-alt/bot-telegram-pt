import os
import time
import threading
import requests
import psycopg2
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from openai import OpenAI

# ==========================================
# 1. VARIÁVEIS DE AMBIENTE (META, GROQ & BD)
# ==========================================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
WHATSAPP_PHONE_ID = os.environ.get("WHATSAPP_PHONE_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "cunene2026")
DATABASE_URL = os.environ.get("DATABASE_URL")

client = None
if GROQ_API_KEY:
    client = OpenAI(
        api_key=GROQ_API_KEY,
        base_url="https://api.api.groq.com/openai/v1" if "api.api.groq.com" in os.environ.get("GROQ_BASE_URL", "") else "https://api.groq.com/openai/v1"
    )

app = Flask(__name__)
MEMORIA_CONVERSAS = {}
ESTADO_REPORTAGEM = {}

# ==========================================
# COORDENADAS DE TODOS OS SERVIÇOS, ESCOLAS E LOCAIS DE ONDJIVA
# (valores aproximados por bairro – devem ser afinados com GPS real)
# ==========================================
COORDENADAS_ONDJIVA = {
    # --- CENTRO DA CIDADE ---
    "hospital municipal": {"lat": -17.0660, "lon": 15.7350, "nome": "Hospital Municipal de Ondjiva", "endereco": "Centro da Cidade, Ondjiva"},
    "governo provincial": {"lat": -17.0665, "lon": 15.7340, "nome": "Governo Provincial do Cunene", "endereco": "Centro da Cidade, Ondjiva"},
    "tribunal": {"lat": -17.0665, "lon": 15.7345, "nome": "Tribunal Provincial", "endereco": "Centro da Cidade, Ondjiva"},
    "delegacia provincial": {"lat": -17.0658, "lon": 15.7355, "nome": "Delegacia Provincial", "endereco": "Centro da Cidade, Ondjiva"},
    "comando provincial da polícia": {"lat": -17.0662, "lon": 15.7352, "nome": "Comando Provincial da Polícia Nacional", "endereco": "Centro da Cidade, Ondjiva"},
    "palácio provincial": {"lat": -17.0668, "lon": 15.7342, "nome": "Palácio Provincial", "endereco": "Centro da Cidade, Ondjiva"},
    "agt": {"lat": -17.0670, "lon": 15.7348, "nome": "AGT – Administração Geral Tributária", "endereco": "Centro da Cidade, Ondjiva"},
    "tribuna": {"lat": -17.0663, "lon": 15.7358, "nome": "Tribuna", "endereco": "Centro da Cidade, Ondjiva"},
    "banco bai": {"lat": -17.0655, "lon": 15.7360, "nome": "Banco BAI", "endereco": "Centro da Cidade, Ondjiva"},
    "banco bfa": {"lat": -17.0658, "lon": 15.7358, "nome": "Banco BFA", "endereco": "Centro da Cidade, Ondjiva"},
    "banco bic": {"lat": -17.0661, "lon": 15.7356, "nome": "Banco BIC", "endereco": "Centro da Cidade, Ondjiva"},
    # --- BAIRRO EKUMA ---
    "hospital ekuma": {"lat": -17.0612, "lon": 15.7425, "nome": "Hospital Provincial da Ekuma", "endereco": "Bairro Ekuma, Ondjiva"},
    "itso": {"lat": -17.0615, "lon": 15.7418, "nome": "ITSO – Instituto Técnico de Saúde de Ondjiva", "endereco": "Bairro Ekuma, Ondjiva"},
    # --- BAIRRO NAIPALALA ---
    "hospital simeone mucunde": {"lat": -17.0721, "lon": 15.7284, "nome": "Hospital Central Simeone Mucunde", "endereco": "Bairro Naipalala, Ondjiva"},
    "mandume": {"lat": -17.0725, "lon": 15.7275, "nome": "Faculdade Mandume", "endereco": "Bairro Naipalala, Ondjiva"},
    "eiffel": {"lat": -17.0728, "lon": 15.7270, "nome": "Instituto Médio Politécnico Eiffel", "endereco": "Bairro Naipalala, Ondjiva"},
    "oulondelo": {"lat": -17.0730, "lon": 15.7265, "nome": "Complexo Escolar Oulondelo", "endereco": "Bairro Naipalala, Ondjiva"},
    "impo": {"lat": -17.0733, "lon": 15.7260, "nome": "IMPO – Instituto Médio de Pedagogia de Ondjiva", "endereco": "Bairro Naipalala, Ondjiva"},
    "pitágoras": {"lat": -17.0735, "lon": 15.7255, "nome": "Colégio Pitágoras", "endereco": "Bairro Naipalala, Ondjiva"},
    "bulet salú": {"lat": -17.0738, "lon": 15.7250, "nome": "Colégio Bulet Salú 1", "endereco": "Bairro Naipalala, Ondjiva"},
    "banco bpc2": {"lat": -17.0720, "lon": 15.7290, "nome": "Banco BPC2", "endereco": "Bairro Naipalala, Ondjiva"},
    "banco atlântico": {"lat": -17.0718, "lon": 15.7295, "nome": "Banco Atlântico", "endereco": "Bairro Naipalala, Ondjiva"},
    "comando viação trânsito": {"lat": -17.0705, "lon": 15.7300, "nome": "Comando Policial de Viação e Trânsito", "endereco": "Bairro Naipalala, Ondjiva"},
    "bombeiros": {"lat": -17.0710, "lon": 15.7305, "nome": "Comando Provincial dos Bombeiros", "endereco": "Bairro Naipalala, Ondjiva"},
    "polícia fiscal": {"lat": -17.0715, "lon": 15.7310, "nome": "Polícia Fiscal", "endereco": "Bairro Naipalala, Ondjiva"},
    "justiça provincial": {"lat": -17.0722, "lon": 15.7288, "nome": "Justiça Provincial", "endereco": "Bairro Naipalala, Ondjiva"},
    "cne": {"lat": -17.0730, "lon": 15.7282, "nome": "CNE – Comissão Nacional Eleitoral", "endereco": "Bairro Naipalala, Ondjiva"},
    "casa da cultura": {"lat": -17.0729, "lon": 15.7278, "nome": "Casa da Cultura", "endereco": "Bairro Naipalala, Ondjiva"},
    "escola primária rei nande": {"lat": -17.0740, "lon": 15.7245, "nome": "E.P Rei Nande", "endereco": "Bairro Naipalala, Ondjiva"},
    # --- BAIRRO KACULUVALE ---
    "mediateca": {"lat": -17.0595, "lon": 15.7450, "nome": "Mediateca Lucas Damba", "endereco": "Bairro Kaculuvale, Ondjiva"},
    "aeroporto": {"lat": -17.0422, "lon": 15.7511, "nome": "Aeroporto Provincial 11 de Novembro", "endereco": "Bairro Kaculuvale, Ondjiva"},
    "administração provincial": {"lat": -17.0598, "lon": 15.7445, "nome": "Administração Provincial", "endereco": "Bairro Kaculuvale, Ondjiva"},
    "cesmo": {"lat": -17.0585, "lon": 15.7460, "nome": "Colégio Cesmo", "endereco": "Bairro Kaculuvale, Ondjiva"},
    "ednas": {"lat": -17.0580, "lon": 15.7465, "nome": "Colégio Ednas", "endereco": "Bairro Kaculuvale, Ondjiva"},
    "popiene": {"lat": -17.0575, "lon": 15.7470, "nome": "Colégio Popiene", "endereco": "Bairro Kaculuvale, Ondjiva"},
    "marc leandres": {"lat": -17.0570, "lon": 15.7475, "nome": "Colégio Marc Leandres", "endereco": "Bairro Kaculuvale, Ondjiva"},
    "escola primária kaculuvale": {"lat": -17.0588, "lon": 15.7455, "nome": "E.P do Kaculuvale", "endereco": "Bairro Kaculuvale, Ondjiva"},
    "escola escolar ocapale": {"lat": -17.0590, "lon": 15.7460, "nome": "E.Escolar Ocapale", "endereco": "Bairro Kaculuvale, Ondjiva"},
    # --- BAIRRO CASTILHOS ---
    "shoprite": {"lat": -17.0688, "lon": 15.7195, "nome": "Supermercado Shoprite Ondjiva", "endereco": "Bairro Castilhos, Ondjiva"},
    "angomarte": {"lat": -17.0675, "lon": 15.7180, "nome": "Supermercado AngoMarte", "endereco": "Bairro Castilhos, Ondjiva"},
    "comando municipal da polícia": {"lat": -17.0690, "lon": 15.7185, "nome": "Comando Municipal da Polícia", "endereco": "Bairro Castilhos, Ondjiva"},
    "polícia investigação criminal": {"lat": -17.0695, "lon": 15.7180, "nome": "Comando da Polícia de Investigação Criminal", "endereco": "Bairro Castilhos, Ondjiva"},
    "campo provincial": {"lat": -17.0699, "lon": 15.7165, "nome": "Campo Provincial 11 de Novembro", "endereco": "Bairro Castilhos, Ondjiva"},
    "escola primária castilhos": {"lat": -17.0705, "lon": 15.7170, "nome": "E.P dos Castilhos", "endereco": "Bairro Castilhos, Ondjiva"},
    "escola cowboy": {"lat": -17.0710, "lon": 15.7160, "nome": "C.Escolar Cowboy", "endereco": "Bairro Castilhos, Ondjiva"},
    # --- BAIRRO KAFITU 1 ---
    "guarda fronteira": {"lat": -17.0900, "lon": 15.7300, "nome": "Comando Policial Guarda Fronteira", "endereco": "Bairro Kafitu 1, Ondjiva"},
    "escola primária 4 de janeiro": {"lat": -17.0905, "lon": 15.7305, "nome": "E.P 4 de Janeiro", "endereco": "Bairro Kafitu 1, Ondjiva"},
    # --- BAIRRO KAFITU 2 ---
    "escola primária okapacupacu": {"lat": -17.0850, "lon": 15.7250, "nome": "E.P Okapacupacu", "endereco": "Bairro Kafitu 2, Ondjiva"},
    # --- BAIRRO ZECA ---
    "escola primária 122": {"lat": -17.0780, "lon": 15.7120, "nome": "E.P 122", "endereco": "Bairro Zeca, Ondjiva"},
    "bulet salú 2": {"lat": -17.0785, "lon": 15.7115, "nome": "Colégio Bulet Salú 2", "endereco": "Bairro Zeca, Ondjiva"},
    # --- BAIRRO MUHONGO ---
    "rei luhuna": {"lat": -17.0900, "lon": 15.7380, "nome": "Faculdade Rei Luhuna", "endereco": "Bairro Muhongo, Ondjiva"},
    # --- BAIRRO CAXILA 1/2/3 ---
    "escola primária caxila1": {"lat": -17.0750, "lon": 15.7050, "nome": "E.P da Caxila 1", "endereco": "Bairro Caxila 1, Ondjiva"},
    "escola primária caxila2": {"lat": -17.0780, "lon": 15.7030, "nome": "E.P da Caxila 2", "endereco": "Bairro Caxila 2, Ondjiva"},
    "abcunene": {"lat": -17.0800, "lon": 15.7000, "nome": "Colégio ABcunene", "endereco": "Bairro Caxila 3, Ondjiva"},
    # --- CENTRALIDADE ---
    "centralidade": {"lat": -17.0850, "lon": 15.7010, "nome": "Centralidade de Ondjiva", "endereco": "Ondjiva, Cunene"},
    "escola primária centralidade": {"lat": -17.0840, "lon": 15.7020, "nome": "E.P da Centralidade", "endereco": "Centralidade, Ondjiva"},
    "escola centralidade 1 ciclo": {"lat": -17.0845, "lon": 15.7015, "nome": "C.E da Centralidade", "endereco": "Centralidade, Ondjiva"},
    "campo centralidade": {"lat": -17.0855, "lon": 15.7005, "nome": "Campo da Centralidade", "endereco": "Centralidade, Ondjiva"},
    # --- ONAHUMBA ---
    "escola primária onahumba": {"lat": -17.0700, "lon": 15.6900, "nome": "E.P do Onahumba", "endereco": "Bairro Onahumba, Ondjiva"},
    # --- BANGULA (bancos) ---
    "banco bci": {"lat": -17.0630, "lon": 15.7370, "nome": "Banco BCI", "endereco": "Bairro Bangula, Ondjiva"},
    "banco bpc": {"lat": -17.0633, "lon": 15.7373, "nome": "Banco BPC", "endereco": "Bairro Bangula, Ondjiva"},
    "banco sol": {"lat": -17.0636, "lon": 15.7376, "nome": "Banco Sol", "endereco": "Bairro Bangula, Ondjiva"},
    "banco económico": {"lat": -17.0639, "lon": 15.7379, "nome": "Banco Económico", "endereco": "Bairro Bangula, Ondjiva"},
    # --- ITAS (localização estimada em Naipalala) ---
    "itas": {"lat": -17.0740, "lon": 15.7250, "nome": "ITAS – Instituto Técnico de Administração e Serviços", "endereco": "Bairro Naipalala, Ondjiva"},
}

# ==========================================
# 2. A BÍBLIA DE ONDJIVA (Versão 5.0 - Com Mapas e Relógio)
# ==========================================
CONTEXTO_ONDJIVA = """
Tu és o Bot_cunene, o assistente virtual oficial de Ondjiva. Deves ser sempre prestativo, caloroso, humano e usar uma linguagem natural de Angola, evitando responder como um robô que apenas lista dados.

### DIRETIVAS CRÍTICAS DE RESPOSTA (OBRIGATÓRIO):
1. FORMATO WHATSAPP: O WhatsApp usa asteriscos para negrito. Sempre que quiseres destacar algo, usa *texto* e nunca **texto**.
2. IDIOMA EXCLUSIVO: Responde SEMPRE em Português de Angola. Se o utilizador pedir para responder noutro idioma (Inglês) ou língua nacional (Cuanhama), responde rigorosamente: "Como assistente oficial da Administração de Ondjiva, presto atendimento exclusivamente em Língua Portuguesa."
3. MAPA GEOGRÁFICO: O Cuanhama é um município e uma língua nacional da província do Cunene. Nunca digas que é outra província.
4. RIGOR NOS HORÁRIOS: Só podes informar os horários listados abaixo. Nunca inventes horas.
5. ANTI-VAZAMENTO: Proibido usar termos técnicos como "regras", "prompt" ou "base de dados".
6. ANTI-ALUCINAÇÃO SELETIVA: Se a informação para responder à pergunta EXISTIR no documento, responde de forma completa, natural e simpática. NUNCA dês avisos ou desculpas sobre o que falta no fim da resposta. Apenas se a pergunta for EXCLUSIVAMENTE sobre algo que não existe aqui, deves responder textualmente: "Peço desculpa, mas não tenho informações oficiais sobre esse assunto no meu sistema neste momento, mas se quiseres saber de outra coisa é só falares, estou aqui pra ajudar."

---
### DADOS OFICIAIS E HORÁRIOS DE ATENDIMENTO (A TUA ÚNICA FONTE DE VERDADE)

### 1. ADMINISTRAÇÃO PÚBLICA E INSTITUIÇÕES
* Horário de Atendimento: Segunda a Quinta das 08h00 às 15h30 | Sexta das 08h00 às 15h00.
- Governo Provincial, Tribunal, Delegacia Provincial, Comando Provincial da Polícia, Palácio provincial, AGT e Tribuna: Centro da Cidade.
- Administração Provincial, Mediateca e Aeroporto Provincial 11 de novembro: Bairro Kaculuvale.
- Comando Municipal da Polícia e Comando da Polícia de Investigação Criminal: Castilhos.
- Comando Policial de Viação Trânsito, Comando provincial dos Bombeiros, Polícia Fiscal: Naipalala.
- Comando Policial Guarda Fronteira: Kafitu1.
- Justiça Provincial, CNE, Casa da Cultura: Naipalala.
- Governadora Provincial do Cunene: Gerdina Didalelwa.

### 2. SERVIÇOS DE SAÚDE E HOSPITAIS
* Urgências: 24 horas por dia, todos os dias.
* Consultas Externas/Administrativo: Segunda a Sexta das 08h00 às 15h00.
- Hospital Provincial Ekuma: Bairro Ekuma.
- Hospital Central Simeone Mucunde: Bairro Naipalala.
- Hospital Municipal: Centro da Cidade.
- NOTA: Não existem outras escolas ou institutos técnicos de saúde registados neste documento.

### 3. INSTITUIÇÕES DE ENSINO E ESCOLAS (com cursos e ciclos)
* Horário de Aulas: Manhã (07h00-12h30) | Tarde (13h00-17h30) | Noite (18h00-22h30).

- **Faculdades:**
   * Rei Luhuna (Muhongo).
   * Mandume (Naipalala).

- **Institutos e escolas públicas do ensino médio:**
   * ITSO (Ekuma) — Escola de Saúde: cursos de Enfermagem Geral, Fisioterapia, Análises Clínicas.
   * Eiffel (Naipalala).
   * Oulondelo (Naipalala) — Ciências Físicas e Biológicas, Ciências Económicas e Jurídicas; também possui ensino primário e 1.º ciclo.
   * IMPO (Naipalala) — Escola de Pedagogia do Cunene: cursos de Mate-Física, Ensino Primário, EMC, Língua Portuguesa.
   * Cesmo (Kaculuvale) — Ciências Físicas e Biológicas, Ciências Económicas e Jurídicas.
   * ITAS (Naipalala) — Instituto Técnico de Administração e Serviços: cursos de Finanças, Secretariado, Contabilidade, Gestão Empresarial, Recursos Humanos.

- **Colégios (todos com ensino primário e 1.º ciclo, excepto indicação em contrário):**
   * Ednas (Kaculuvale) — Ciências Físicas e Biológicas, Ciências Económicas e Jurídicas.
   * Popiene (Kaculuvale).
   * Marc Leandres (Kaculuvale) — apenas ensino primário e 1.º ciclo (não tem ensino médio).
   * Pitágoras (Naipalala) — cursos de Farmácia, Informática, Eletricidade, Ciências Físicas e Biológicas, Enfermagem Geral, Análises Clínicas.
   * Bulet Salú 1 (Naipalala) — Ciências Físicas e Biológicas, Ciências Económicas e Jurídicas, Ciências Humanas, Eletricidade.
   * Abcunene (Caxila 3) — cursos de Enfermagem Geral, Análises Clínicas, Informática.
   * Bulet Salú 2 (Zeca) — Ciências Físicas e Biológicas, Ciências Económicas e Jurídicas, Ciências Humanas, Eletricidade.

- **Escolas Primárias:**
   * E.P 4 de Janeiro (Kafitu 1)
   * E.P Okapacupacu (Kafitu2)
   * E.P 122 (Zeca)
   * E.P Rei Nande (Naipalala)
   * E.P da Centralidade (Centralidade)
   * E.P do Kaculuvale (Kaculuvale)
   * E.P da Caxila1 (Caxila1)
   * E.P da Caxila2 (Caxila2)
   * E.P do Onahumba (Onahumba)
   * E.P dos Castilhos (Castilhos)

- **Escolas do Primeiro ciclo:**
   * C.Escolar Cowboy (Castilhos)
   * E.Escolar Ocapale (Kaculuvale)
   * C.E da Centralidade (Centralidade)
   * E.P Rei Nande (Naipalala) — também funciona como primeiro ciclo.

### 4. BANCOS E SERVIÇOS FINANCEIROS
* Horário Bancário: Segunda a Sexta das 08h00 às 15h00.
- Banco BAI, BFA, BIC: Centro da Cidade.
- Bancos BCI, BPC, Banco Sol, Económico: Bairro Bangula.
- Bancos BPC2, Atlântico: Bairro Naipalala.

### 5. DESPORTO
- Campo provincial: 11 de novembro (Castilhos). 
- Campo: Campo da Centralidade.

### 6. COMÉRCIO E LAZER
* Supermercados (Shoprite e AngoMarte): Abertos todos os dias das 08h00 às 20h00. Ficam no bairro Castilhos.

### 7. DIVISÃO POLÍTICO-ADMINISTRATIVA ACTUALIZADA (MUNICÍPIOS E COMUNAS)
Conforme os dados mais recentes, a província do Cunene está organizada da seguinte forma:

- **Cahama** (Administrador: José Mário Katiti) – Comunas: Cahama, Otchinjau. Sem distritos.
- **Cuanhama** (Administrador: José Felisberto Kalomo) – Comunas: Ondjiva, Môngua. Sem distritos.
- **Curoca** (Administrador: António Dos Santos Luepo) – Comunas: Oncócua, Chitado. Sem distritos.
- **Cuvelai** (Administrador: Germano Baptista Nambalo) – Comunas: Mupa, Mukolongodjo, Calonga, Cubati. Sem distritos.
- **Namacunde** (Administrador: Cristuiana Nameomunu) – Comunas: Namacunde, Chiede. Sem distritos.
- **Ombadja** (Administrador: Hilario Sikalepo) – Comunas: Humpe, Mucope, Naulila, Ombala yo Mungu, Xangongo. Sem distritos.
- **Chiéde** – Sem comunas. Sem administrador.
- **Nehone** – Comunas: Nehone, Evale. Sem administrador.
- **Humbe** – Comunas: Mucope, Humbe. Sem administrador.
- **Mupa** – Sem comunas. Sem administrador.
- **Naulila** – Sem comunas. Sem administrador.
- **Chitado** – Sem comunas. Sem administrador.
- **Cafima** – Sem comunas. Sem administrador.
- **Chissuata** – Sem comunas. Sem administrador.

### 8. INSTRUÇÕES DO SISTEMA DE REPORTAGENS E LOCALIZAÇÃO
- O bot possui um sistema automatizado de triagem de problemas. Instrua o cidadão a digitar *Reportagem* seguida do problema principal.
- Exemplo a mostrar: "Escreve: *Reportagem falta de água no bairro Kafitu*".
- O bot também consegue enviar mapas de localização em tempo real. Se o utilizador quiser saber a rota ou localização de locais (Ex: Shoprite, Mediateca, Ekuma), diga-lhe que basta pedir explicitamente a localização desses sítios (Ex: "Onde fica a Shoprite?").
"""

# ==========================================
# 3. CONECTOR DA BASE DE DADOS OTIMIZADO (ESTÁVEL)
# ==========================================
def guardar_reportagem_bd(telefone, relato):
    if not DATABASE_URL:
        print("⚠️ DATABASE_URL não configurada.")
        return False
        
    try:
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS reportagens (
                        id SERIAL PRIMARY KEY,
                        telefone VARCHAR(50),
                        relato TEXT,
                        data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cur.execute(
                    "INSERT INTO reportagens (telefone, relato) VALUES (%s, %s)",
                    (telefone, relato)
                )
                conn.commit()
        print("💾 Relato guardado com sucesso no PostgreSQL!")
        return True
    except Exception as e:
        print(f"🚨 Erro crítico na BD: {e}")
        return False

# ==========================================
# 4. FUNÇÕES DE ENVIAR MENSAGENS (META API)
# ==========================================
def enviar_mensagem_whatsapp(telefone_destino, texto):
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID:
        print("🚨 Faltam credenciais do WhatsApp.")
        return

    texto_formatado = texto.replace("**", "*")

    url = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": telefone_destino,
        "type": "text",
        "text": {"body": texto_formatado}
    }
    
    resposta = requests.post(url, headers=headers, json=payload)
    print(f"📤 Status de envio: {resposta.status_code}")

def enviar_localizacao_whatsapp(telefone_destino, latitude, longitude, nome_local, endereco):
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID:
        print("🚨 Faltam credenciais para envio de localização.")
        return
        
    url = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": telefone_destino,
        "type": "location",
        "location": {
            "latitude": latitude,
            "longitude": longitude,
            "name": nome_local,
            "address": endereco
        }
    }
    resposta = requests.post(url, headers=headers, json=payload)
    print(f"📍 Status de envio do Pin de Mapa: {resposta.status_code}")

# ==========================================
# 5. PROCESSAMENTO DO BOT (MÁQUINA DE ESTADOS + IA)
# ==========================================
def processar_texto(telefone_origem, user_text):
    texto_baixo = user_text.lower().strip()
    
    # --- MÁQUINA DE ESTADOS (FLUXO MULTI-PASSO DA REPORTAGEM) ---
    if telefone_origem in ESTADO_REPORTAGEM:
        dados = ESTADO_REPORTAGEM[telefone_origem]
        
        # PASSO 1: Receber o Tempo/Duração
        if dados['passo'] == 1:
            dados['tempo'] = user_text.strip()
            dados['passo'] = 2
            return (
                "📝 *Passo 2 de 2 • Detalhes da Ocorrência*\n\n"
                "Obrigado. Agora diz-me: *O que levou a esse acontecimento ou qual achas ser a causa?*\n"
                "_(Se não souberes, podes responder apenas 'Não sei')_"
            )
            
        # PASSO 2: Receber a Causa, Compilar, Gravar e Finalizar
        elif dados['passo'] == 2:
            dados['causa'] = user_text.strip()
            
            relato_final_bd = (
                f"PROBLEMA PRINCIPAL: {dados['problema']} | "
                f"DURAÇÃO DA SITUAÇÃO: {dados['tempo']} | "
                f"CAUSA PROVÁVEL: {dados['causa']}"
            )
            
            guardar_reportagem_bd(telefone_origem, relato_final_bd)
            ESTADO_REPORTAGEM.pop(telefone_origem)
            
            return (
                "✅ *Ocorrência Submetida com Sucesso!* \n\n"
                "O teu relatório detalhado foi estruturado e enviado para o sistema interno da Administração Municipal:\n\n"
                f"• *Ocorrência:* {dados['problema']}\n"
                f"• *Tempo de Existência:* {dados['tempo']}\n"
                f"• *Causa Relatada:* {dados['causa']}\n\n"
                "Obrigado por ajudares a melhorar a nossa comunidade. A cidadania ativa faz a diferença! Como posso ajudar-te em mais alguma coisa?"
            )

    # --- EMERGÊNCIA (Corta logo a IA se for caso sério) ---
    if any(palavra in texto_baixo for palavra in ["emergencia", "emergência", "socorro", "policia", "bombeiros"]):
        return (
            "🚨 *ALERTA DE EMERGÊNCIA IMEDIATA!* 🚨\n\n"
            "Se estás numa situação de perigo real no Cunene, liga de imediato:\n"
            "🚓 *Polícia Nacional:* 113\n"
            "👨‍🚒 *Bombeiros:* 115\n\n"
            "Procura um local seguro!"
        )
    
    # --- ENTRADA NO FLUXO DE REPORTAGEM ---
    if texto_baixo.startswith("reportagem"):
        problema_inicial = user_text.strip()[10:].strip()
        if not problema_inicial:
            return "🚨 Para registar, escreva a palavra *Reportagem* seguida do problema (Ex: Reportagem falta de luz no bairro Kafitu)."
        
        ESTADO_REPORTAGEM[telefone_origem] = {
            'passo': 1,
            'problema': problema_inicial,
            'tempo': '',
            'causa': ''
        }
        
        return (
            "📝 *Sistema de Atendimento de Ocorrências Oficial*\n\n"
            "Registou o seguinte problema: "
            f"_{problema_inicial}_\n\n"
            "Para enviar um relatório completo à Administração Municipal, responde por favor:\n"
            "👉 *Há quanto tempo estão nessa situação?*"
        )

    # --- MENU / GUIA DE UTILIZAÇÃO ---
    if texto_baixo in ["menu", "ajuda", "help", "guia", "opções", "opcoes"]:
        return (
            "📋 *Menu Principal do Bot_cunene*\n\n"
            "Olá! Eu sou o assistente virtual de Ondjiva. Aqui tens as formas de usar os meus serviços sem dependeres só da conversa:\n\n"
            "1️⃣ *Reportar um problema*: escreve *Reportagem* seguido do assunto (ex.: Reportagem falta de água no Kafitu).\n"
            "2️⃣ *Pedir localização*: pergunta 'Onde fica o Shoprite?' ou 'Localização do Hospital Ekuma' e eu envio-te o pin com o mapa.\n"
            "3️⃣ *Informações oficiais*: podes perguntar sobre horários de repartições, cursos das escolas, bancos, hospitais, etc.\n"
            "4️⃣ *Emergências*: escreve 'emergência' para veres os números da Polícia e Bombeiros.\n\n"
            "Estou aqui para te ajudar com tudo sobre Ondjiva! ✨"
        )

    # --- INTERCETOR DE LOCALIZAÇÃO (SISTEMA DE MAPAS NATIVOS) ---
    for chave, dados in COORDENADAS_ONDJIVA.items():
        if chave in texto_baixo and any(p in texto_baixo for p in ["localização", "localizacao", "onde fica", "onde esta", "onde está", "mapa", "rota"]):
            enviar_localizacao_whatsapp(telefone_origem, dados["lat"], dados["lon"], dados["nome"], dados["endereco"])
            return (
                f"📍 *Mapa de Localização Gerado!*\n\n"
                f"Enviei-te mesmo acima o pin oficial do(a) *{dados['nome']}*.\n"
                "Clica no quadrado do mapa para abrires o teu GPS e veres a rota exata a partir do teu local atual!"
            )

    # --- FLUXO NORMAL (INTELIGÊNCIA ARTIFICIAL CONTEXTUAL E BLINDADA) ---
    try:
        if not client:
            return "🚨 Erro: API da IA não configurada."
        
        if telefone_origem not in MEMORIA_CONVERSAS:
            MEMORIA_CONVERSAS[telefone_origem] = []
        
        MEMORIA_CONVERSAS[telefone_origem].append({"role": "user", "content": user_text})
        
        if len(MEMORIA_CONVERSAS[telefone_origem]) > 16:
            MEMORIA_CONVERSAS[telefone_origem] = MEMORIA_CONVERSAS[telefone_origem][-16:]
        
        # --- CÁLCULO INFALÍVEL DA HORA E SAUDAÇÃO PELO PYTHON ---
        agora_angola = datetime.utcnow() + timedelta(hours=1)
        hora_formatada = agora_angola.strftime("%H:%M")
        data_formatada = agora_angola.strftime("%d/%m/%Y")
        
        hora_atual = agora_angola.hour
        if 5 <= hora_atual < 12:
            saudacao_correta = "Bom dia"
            periodo = "da manhã"
        elif 12 <= hora_atual < 18:
            saudacao_correta = "Boa tarde"
            periodo = "da tarde"
        else:
            saudacao_correta = "Boa noite"
            periodo = "da noite"
        
        regra_relogio = (
            f"\n\n[SISTEMA - INFORMAÇÃO TEMPORAL INFALÍVEL]\n"
            f"Hoje é dia {data_formatada}.\n"
            f"Agora são exatamente {hora_formatada} {periodo} em Ondjiva (Formato 24h: {hora_formatada}).\n"
            f"DIRETIVA CRÍTICA DE SAUDAÇÃO: Tu deves saudar o utilizador OBRIGATORIAMENTE com '{saudacao_correta}'. Nunca uses outra saudação.\n"
            f"DIRETIVA DE RESPOSTA HORÁRIA: Se o utilizador perguntar que horas são, responde estritamente que são {hora_formatada}."
        )
        
        contexto_dinamico = CONTEXTO_ONDJIVA + regra_relogio

        mensagens_para_ia = [{"role": "system", "content": contexto_dinamico}] + MEMORIA_CONVERSAS[telefone_origem]

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            temperature=0.0,
            messages=mensagens_para_ia
        )
        
        resposta_ia = response.choices[0].message.content
        MEMORIA_CONVERSAS[telefone_origem].append({"role": "assistant", "content": resposta_ia})
        
        return resposta_ia
        
    except Exception as e:
        return f"❌ Erro na IA: {e}"

# ==========================================
# 6. PING ANTI-HIBERNAÇÃO DA NUVEM
# ==========================================
def keep_awake():
    url = "https://bot-telegram-pt-rzhv.onrender.com/"
    while True:
        time.sleep(800)
        try:
            requests.get(url)
            print("🔄 Ping Anti-Hibernação enviado com sucesso para o Render!")
        except Exception as e:
            print(f"⚠️ Falha no Ping interno: {e}")
            pass

# ==========================================
# 7. ROTAS DO FLASK (WEBHOOK DA META)
# ==========================================
@app.route('/', methods=['GET'])
def home():
    return "Servidor do Bot de WhatsApp do Cunene Ativo com PostgreSQL e Mapas!", 200

@app.route('/webhook', methods=['GET'])
def verificar_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == VERIFY_TOKEN:
            print("✅ Webhook verificado pela Meta com sucesso!")
            return challenge, 200
        else:
            return "Token de verificação inválido", 403
    return "Faltam parâmetros", 400

@app.route('/webhook', methods=['POST'])
def receber_mensagens():
    body = request.get_json()

    if body.get("object"):
        if "entry" in body and "changes" in body["entry"][0]:
            mudancas = body["entry"][0]["changes"][0]["value"]
            
            if "messages" in mudancas:
                mensagem = mudancas["messages"][0]
                
                if mensagem["type"] == "text":
                    telefone_origem = mensagem["from"]
                    texto_recebido = mensagem["text"]["body"]
                    print(f"📥 Recebido de {telefone_origem}: {texto_recebido}")
                    
                    resposta_final = processar_texto(telefone_origem, texto_recebido)
                    enviar_mensagem_whatsapp(telefone_origem, resposta_final)
                    
        return jsonify({"status": "ok"}), 200
    else:
        return jsonify({"status": "erro"}), 404

if __name__ == '__main__':
    threading.Thread(target=keep_awake, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
