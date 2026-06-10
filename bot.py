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

# DICIONÁRIO GLOBAL PARA CONTROLAR OS PASSOS DA REPORTAGEM (MÁQUINA DE ESTADOS)
ESTADO_REPORTAGEM = {}

# ==========================================
# 2. A BÍBLIA DE ONDJIVA (Versão 4.0 - Com Reportagem)
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
- Comando Picial de Viação Trânsito, Comando provincial dos Bombeiros, Polícia Fiscal: Naipalala.
- Comando Policial Guarda Fronteita: Kafitu1.
- Justiça Provincial, CNE, Casa da Cultura: Naipalala.
- Governadora Provincial do Cunene: Gerdina Didalelwa.

### 2. SERVIÇOS DE SAÚDE E HOSPITAIS
* Urgências: 24 horas por dia, todos os dias.
* Consultas Externas/Administrativo: Segunda a Sexta das 08h00 às 15h00.
- Hospital Provincial Ekuma: Bairro Ekuma.
- Hospital Central Simeone Mucunde: Bairro Naipalala.
- Hospital Municipal: Centro da Cidade.
- NOTA: Não existem outras escolas ou institutos técnicos de saúde registados neste documento.

### 3. INSTITUIÇÕES DE ENSINO E ESCOLAS
* Horário de Aulas: Manhã (07h00-12h30) | Tarde (13h00-17h30) | Noite (18h00-22h30).
- Faculdades: Rei Luhuna (Muhongo), Mandume (Naipalala).
- Institutos e escolas públicas do ensino médio: ITSO (Ekuma). Eiffel, Oulondelo, IMPO (Naipalala). Cesmo (Kaculuvale).
- Colégios: Ednas, Popiene, Marc Leandres (Kaculuvale). Pitágoras, Bulet Salú (Naipalala). Abcunene (Caxila 3). Bulet Salú2 (Zeca).
- Escolas Primárias: E.P 4 de Janeiro (Kafitu 1), E.P Okapacupacu (Kafitu2), E.P 122 (Zeca), E.P Rei Nande (Naipalala), E.P da Centralidade (Centralidade), E.P do Kaculuvale (Kaculuvale), E.P da Caxila1 (Caxila1), E.P da Caxila2 (Caxila2), E.P do Onahumba (Onahumba), E.P dos Castilhos (Castilhos).
- Escolas do Primeiro ciclo: C.Escolar Cowboy (Castilhos), E.Escolar Ocapale (Kaculuvale), C.E da Centralidade (Centralidade), E.P Rei Nande (Naipalala).

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

### 7. DIVISÃO POLÍTICO-ADMINISTRATIVA (MUNICÍPIOS E COMUNAS)
A província do Cunene é constituída por 6 Municípios e as respetivas Comunas:
* 1. Município do Cuanhama (Sede: Ondjiva) - Comunas: Ondjiva, Môngua, Evale, Nehone, Cafima.
* 2. Município de Ombadja (Sede: Xangongo) - Comunas: Xangongo, Humbe, Mucope, Naulila, Ombala yo Mungu.
* 3. Município da Cahama (Sede: Cahama) - Comunas: Cahama, Otchinjau.
* 4. Município do Cuvelai (Sede: Cuvelai) - Comunas: Cuvelai, Mupa, Calonga, Cubati.
* 5. Município do Curoca (Sede: Oncocua) - Comunas: Oncocua, Chitado.
* 6. Município de Namacunde (Sede: Namacunde) - Comunas: Namacunde, Chiedi.

### 8. INSTRUÇÕES DO SISTEMA DE REPORTAGENS DE CIDADANIA
- O bot possui um sistema automatizado de triagem de problemas.
- Se o cidadão perguntar como fazer uma reportagem ou reclamação, deves instruí-lo explicitamente a enviar uma mensagem que comece com a palavra *Reportagem* seguida do problema principal.
- Exemplo a mostrar: "Escreve: *Reportagem falta de água no bairro Kafitu*".
- Explica-lhe que, logo de seguida, o sistema fará perguntas automáticas para detalhar o relatório antes de o submeter à Administração.
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
# 4. FUNÇÃO DE ENVIAR MENSAGEM (META API)
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
            
            # Formatação estruturada que será gravada na Base de Dados
            relato_final_bd = (
                f"PROBLEMA PRINCIPAL: {dados['problema']} | "
                f"DURAÇÃO DA SITUAÇÃO: {dados['tempo']} | "
                f"CAUSA PROVÁVEL: {dados['causa']}"
            )
            
            # Gravação física no PostgreSQL do Render
            guardar_reportagem_bd(telefone_origem, relato_final_bd)
            
            # Remover o utilizador do fluxo de denúncias
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
    elif texto_baixo.startswith("reportagem"):
        # Extrai o problema preservando maiúsculas originais
        problema_inicial = user_text.strip()[10:].strip()
        if not problema_inicial:
            return "🚨 Para registar, escreva a palavra *Reportagem* seguida do problema (Ex: Reportagem falta de luz no bairro Kafitu)."
        
        # Cria o estado inicial para este número de telefone
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

    # --- FLUXO NORMAL (INTELIGÊNCIA ARTIFICIAL) ---
    else:
        try:
            if not client:
                return "🚨 Erro: API da IA não configurada."
            
            if telefone_origem not in MEMORIA_CONVERSAS:
                MEMORIA_CONVERSAS[telefone_origem] = []
            
            MEMORIA_CONVERSAS[telefone_origem].append({"role": "user", "content": user_text})
            
            # Janela estendida para 16 mensagens para lembrar histórico
            if len(MEMORIA_CONVERSAS[telefone_origem]) > 16:
                MEMORIA_CONVERSAS[telefone_origem] = MEMORIA_CONVERSAS[telefone_origem][-16:]
            
            agora_angola = datetime.utcnow() + timedelta(hours=1)
            hora_formatada = agora_angola.strftime("%H:%M")
            data_formatada = agora_angola.strftime("%d/%m/%Y")
            
            # Regra de relógio
            regra_relogio = (
                f"\n\n[SISTEMA]\nHoje é {data_formatada} e são {hora_formatada} em Ondjiva. "
                "REGRA MANDATÓRIA DE SAUDAÇÃO: Se a hora estiver entre 05:00 e 11:59, deves saudar APENAS com 'Bom dia'. "
                "Entre 12:00 e 17:59, saúda APENAS com 'Boa tarde'. Entre 18:00 e 04:59, saúda APENAS com 'Boa noite'. "
                "Se o utilizador repetir saudações seguidas, mantém rigidamente a mesma saudação baseada na hora real."
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
# 6. PING ANTI-HIBERNAÇÃO DA NUVEM (CORRIGIDO)
# ==========================================
def keep_awake():
    url = "https://bot-telegram-pt-rzhv.onrender.com/"
    while True:
        time.sleep(800) # Ping a cada ~13 minutos
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
    return "Servidor do Bot de WhatsApp do Cunene Ativo com PostgreSQL!", 200

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

