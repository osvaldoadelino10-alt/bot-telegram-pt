import os
import requests
from flask import Flask, request, jsonify
from openai import OpenAI

# ==========================================
# 1. VARIÁVEIS DE AMBIENTE (META & OPENAI)
# ==========================================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
WHATSAPP_PHONE_ID = os.environ.get("WHATSAPP_PHONE_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "cunene2026") # Palavra-passe do Webhook

# Inicializa OpenAI
client = None
if GROQ_API_KEY:
    client = OpenAI(
        api_key=GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1"
    )



app = Flask(__name__)

# ==========================================
# 2. A BÍBLIA DE ONDJIVA (Base Embutida do TCC)
# ==========================================
CONTEXTO_ONDJIVA = """
Tu és o Ndjili, o assistente virtual oficial e inteligente da província do Cunene, em Angola. 
O teu papel é ser um prestador de serviços de utilidade pública para os cidadãos do Cunene (focado nos municípios de Cuanhama, Namacunde, Ombadja, Cuvelai, Curoca e Cahama, com destaque para a cidade de Ondjiva).

A tua linguagem deve ser sempre no Português de Angola: acolhedora, respeitosa, prestativa e muito educada. Trata os cidadãos com proximidade, mas mantém a formalidade de um serviço público.

=== DIRETRIZES DE ATENDIMENTO ===
1. Sê direto e claro nas respostas, evitando blocos de texto demasiado longos para o WhatsApp.
2. Foca-te em resolver problemas locais: infraestruturas, saúde, segurança e serviços públicos.
3. Se o utilizador relatar um problema na rua (ex: buraco, falta de luz, falta de água), orienta-o a escrever "Reportagem" seguida do problema.
4. Para situações de perigo imediato, encaminha sempre para os números de emergência.

=== BASE DE DADOS E CONTACTOS LOCAIS ===
- Segurança e Polícia Nacional: 113.
- Bombeiros e Proteção Civil: 115.
- Saúde: Hospital Geral de Ondjiva e principais centros médicos.

=== CONTEXTO DO PROJETO ===
Deves saber que foste desenvolvido como uma inovação tecnológica (TCC) para modernizar a província do Cunene, criando uma ponte digital rápida no WhatsApp entre a população e as autoridades.
"""

# ==========================================
# 3. FUNÇÃO DE ENVIAR MENSAGEM (META API)
# ==========================================
def enviar_mensagem_whatsapp(telefone_destino, texto):
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID:
        print("🚨 Faltam credenciais do WhatsApp no Render!")
        return

    url = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": telefone_destino,
        "type": "text",
        "text": {"body": texto}
    }
    
    resposta = requests.post(url, headers=headers, json=payload)
    print(f"📤 Resposta enviada. Status: {resposta.status_code}")

# ==========================================
# 4. PROCESSAMENTO DO BOT (FILTROS + OPENAI)
# ==========================================
def processar_texto(user_text):
    texto_baixo = user_text.lower()
    
    # --- FILTRO 1: EMERGÊNCIA ---
    if any(palavra in texto_baixo for palavra in ["emergencia", "emergência", "socorro", "policia", "bombeiros"]):
        return (
            "🚨 *ALERTA DE EMERGÊNCIA IMEDIATA!* 🚨\n\n"
            "Se estás numa situação de perigo real no Cunene, liga de imediato:\n"
            "🚓 *Polícia Nacional:* 113\n"
            "👨‍🚒 *Bombeiros:* 115\n\n"
            "Procura um local seguro!"
        )
    
    # --- FILTRO 2: REPORTAGEM ---
    elif "reportagem" in texto_baixo:
        relato = user_text.lower().replace("reportagem", "").strip()
        if not relato:
            return "🚨 Escreve a palavra *Reportagem* seguida da descrição do problema (Ex: Reportagem falta de luz no bairro X)."
        return f"✅ *Ocorrência Registada!*\n\nO teu relato:\n_{relato}_\n\nFoi guardado e será reencaminhado para a Administração Municipal. Obrigado!"

    # --- FILTRO 3: OPENAI ---
    else:
        try:
            if not client:
                return "🚨 Erro: API da OpenAI não configurada."
                
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": CONTEXTO_ONDJIVA},
                    {"role": "user", "content": user_text}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"❌ Erro na IA: {e}"

# ==========================================
# 5. ROTAS DO FLASK (WEBHOOK DA META)
# ==========================================
@app.route('/', methods=['GET'])
def home():
    return "Servidor do Bot de WhatsApp do Cunene Ativo!", 200

# Rota GET: Usada pela Meta apenas uma vez para verificar o URL
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

# Rota POST: Usada pela Meta para enviar as mensagens das pessoas
@app.route('/webhook', methods=['POST'])
def receber_mensagens():
    body = request.get_json()

    if body.get("object"):
        if "entry" in body and "changes" in body["entry"][0]:
            mudancas = body["entry"][0]["changes"][0]["value"]
            
            # Verifica se é uma mensagem de texto nova (e não um aviso de leitura)
            if "messages" in mudancas:
                mensagem = mudancas["messages"][0]
                
                if mensagem["type"] == "text":
                    telefone_origem = mensagem["from"]
                    texto_recebido = mensagem["text"]["body"]
                    print(f"📥 Recebido de {telefone_origem}: {texto_recebido}")
                    
                    # Processa e responde
                    resposta_final = processar_texto(texto_recebido)
                    enviar_mensagem_whatsapp(telefone_origem, resposta_final)
                    
        return jsonify({"status": "ok"}), 200
    else:
        return jsonify({"status": "erro"}), 404

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
