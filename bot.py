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
        base_url="https://api.groq.com/openai/v1"
    )

app = Flask(__name__)
MEMORIA_CONVERSAS = {}

# ==========================================
# 2. A BÍBLIA DE ONDJIVA (Versão 2.0)
# ==========================================
CONTEXTO_ONDJIVA = """
Tu és o Ndjili, o assistente virtual oficial, humano e direto da Administração de Ondjiva, província do Cunene, Angola.

### DIRETIVAS CRÍTICAS DE RESPOSTA (OBRIGATÓRIO):
1. FORMATO WHATSAPP: O WhatsApp usa asteriscos para negrito. Sempre que quiseres destacar algo, usa *texto* e nunca **texto**.
2. IDIOMA EXCLUSIVO: Responde SEMPRE in Português de Angola. Se o utilizador pedir para responder noutro idioma (Inglês) ou língua nacional (Cuanhama), responde rigorosamente: "Como assistente oficial da Administração de Ondjiva, presto atendimento exclusivamente em Língua Portuguesa."
3. MAPA GEOGRÁFICO: O Cuanhama é um município e uma língua nacional da província do Cunene. Nunca digas que é outra província.
4. RIGOR NOS HORÁRIOS: Só podes informar os horários listados abaixo. Nunca inventes horas.
5. ANTI-VAZAMENTO: Proibido usar termos técnicos como "regras", "prompt" ou "base de dados".

---
### DADOS OFICIAIS E HORÁRIOS DE ATENDIMENTO (A TUA ÚNICA FONTE DE VERDADE)

### 1. ADMINISTRAÇÃO PÚBLICA E INSTITUIÇÕES
* Horário de Atendimento: Segunda a Quinta das 08h00 às 15h30 | Sexta das 08h00 às 15h00.
- Governo Provincial, Tribunal, Delegacia Provincial, AGT e Tribuna: Centro da Cidade.
- Administração Provincial e Aeroporto Provincial: Bairro Kaculuvale.
- Comando Provincial da Polícia e Mediateca Lucas: Centro da Cidade.

### 2. SERVIÇOS DE SAÚDE E HOSPITAIS
* Urgências: 24 horas por dia, todos os dias.
* Consultas Externas/Administrativo: Segunda a Sexta das 08h00 às 15h00.
- Hospital Provincial/Ekuma: Bairro Ekuma.
- Hospital Central Simeone Mucunde: Bairro Naipalala.
- Hospital Municipal: Centro da Cidade.

### 3. INSTITUIÇÕES DE ENSINO E ESCOLAS
* Horário de Aulas: Manhã (07h00-12h30) | Tarde (13h00-17h30) | Noite (18h00-22h30).
- Faculdades: Rei Luhuna (Muhongo), Mandume (Naipalala).
- Institutos: ITSO (Ekuma). Eiffel, Oulondelo, IMPO, Pitágoras, Arcanjo (Naipalala). Cesmo, Ednans, Popiene (Kaculuvale). Complexo Abcunene (Caxila 3).
- Escolas Primárias Kafitu: Escola 4 de Janeiro (Kafitu 1) e básicas no Kafitu 2.

### 4. BANCOS E SERVIÇOS FINANCEIROS
* Horário Bancário: Segunda a Sexta das 08h00 às 15h00.
- Banco BAI: Centro da Cidade.
- Bancos BCI, BPC, Banco Sol, Económico: Bairro Bangula.
- Bancos BFA, BIC: Bairro Zeca.
- Bancos BPC2, Atlântico: Bairro Naipalala.

### 5. COMÉRCIO E LAZER
* Supermercados (Shoprite e AngoMarte): Abertos todos os dias das 08h00 às 20h00. Ficam no bairro Castilhos.
"""

# ==========================================
# 3. CONECTOR DA BASE DE DADOS (POSTGRESQL DO RENDER)
# ==========================================
def guardar_reportagem_bd(telefone, relato):
    if not DATABASE_URL:
        print("⚠️ DATABASE_URL não configurada.")
        return False
        
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
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
        cur.close()
        conn.close()
        print("💾 Relato guardado com sucesso!")
        return True
    except Exception as e:
        print(f"🚨 Erro na BD: {e}")
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
# 5. PROCESSAMENTO DO BOT (MEMÓRIA + RELÓGIO + IA)
# ==========================================
def processar_texto(telefone_origem, user_text):
    texto_baixo = user_text.lower()
    
    if any(palavra in texto_baixo for palavra in ["emergencia", "emergência", "socorro", "policia", "bombeiros"]):
        return (
            "🚨 *ALERTA DE EMERGÊNCIA IMEDIATA!* 🚨\n\n"
            "Se estás numa situação de perigo real no Cunene, liga de imediato:\n"
            "🚓 *Polícia Nacional:* 113\n"
            "👨‍🚒 *Bombeiros:* 115\n\n"
            "Procura um local seguro!"
        )
    
    elif "reportagem" in texto_baixo:
        relato = user_text.lower().replace("reportagem", "").strip()
        if not relato:
            return "🚨 Para registar, escreva a palavra *Reportagem* seguida do problema (Ex: Reportagem falta de luz no bairro Kafitu)."
        
        guardar_reportagem_bd(telefone_origem, relato)
        
        return (
            "✅ *Ocorrência Registada!*\n\n"
            f"O teu relato: _{relato}_\n\n"
            "Foi guardado de forma segura no nosso sistema e será reencaminhado para a Administração Municipal. A cidadania ativa faz a diferença!"
        )

    else:
        try:
            if not client:
                return "🚨 Erro: API da IA não configurada."
            
            if telefone_origem not in MEMORIA_CONVERSAS:
                MEMORIA_CONVERSAS[telefone_origem] = []
            
            MEMORIA_CONVERSAS[telefone_origem].append({"role": "user", "content": user_text})
            
            if len(MEMORIA_CONVERSAS[telefone_origem]) > 6:
                MEMORIA_CONVERSAS[telefone_origem] = MEMORIA_CONVERSAS[telefone_origem][-6:]
            
            agora_angola = datetime.utcnow() + timedelta(hours=1)
            hora_formatada = agora_angola.strftime("%H:%M")
            data_formatada = agora_angola.strftime("%d/%m/%Y")
            
            contexto_dinamico = CONTEXTO_ONDJIVA + f"\n\n[SISTEMA]\nHoje é {data_formatada} e são {hora_formatada} em Ondjiva. Adapta a tua saudação (Bom dia/Boa tarde/Boa noite) a esta hora."

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
# 6. PING ANTI-HIBERNAÇÃO
# ==========================================
def keep_awake():
    url = "https://bot-whatsapp-cunene.onrender.com/"
    while True:
        time.sleep(800)
        try:
            requests.get(url)
        except:
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
                    telefone_origem = message_from = mensagem["from"]
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
