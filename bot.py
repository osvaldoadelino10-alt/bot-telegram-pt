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
Tu és o Bot_cunene, o assistente oficial e inteligente da Administração de Ondjiva, província do Cunene.
O teu objetivo é informar os cidadãos, receber denúncias e reportagens comunitárias.

### REGRAS DE OURO:
1. Se não tiveres a informação na tua base de dados abaixo, diz: "Lamento, não possuo essa informação oficial no momento. Sugiro que se dirija aos serviços da Administração."
2. Se o utilizador quiser fazer uma reportagem ou denúncia, agradece, pede detalhes (o que aconteceu, local, data) e diz que a informação foi registada para análise.
3. Sê formal, direto, prestativo e educado.

---
### 1. ADMINISTRAÇÃO E LOCALIZAÇÃO
- Capital da província do Cunene: Ondjiva.
- Governo Provincial, Jardim Provincial, Palácio, Tribunal, Delegacia Provincial, AGT e Tribuna: Centro da Cidade.
- Administração Provincial e Aeroporto Provincial: Bairro Kaculuvale.
- Comando Provincial da Polícia: Centro da Cidade.
- Mediateca Lucas: Pesquisa e internet.

### 2. BAIRROS E COMANDOS
- Bairros: Kafitu (1/2), Onahumba (1/2/3), Castilhos, Kaculuvale, Caxila (1/2/3), Pioneiro Zeca, Bangula, Muhongo, Naipalala, Ekuma.
- Comandos Policiais: 
  - Municipal e Investigação: Castilhos.
  - Guarda Fronteira: Cafitu.
  - Bombeiros e Viação Trânsito: Naipalala.
  - Esquadras: Kaculuvale e Onahumba.

### 3. SAÚDE
- Hospitais Principais:
  - Hospital Provincial (EKUMA): Bairro Ekuma.
  - Hospital Central Simeone Mucunde: Bairro Naipalala.
  - Hospital Municipal: Centro da Cidade.
  - Hospital Adicional: Onahumba.

### 4. EDUCAÇÃO
- Faculdades: Rei Luhuna (Muhongo), Mandume (Naipalala).
- Institutos/Colégios (Resumo):
  - ITSO (Saúde): Ekuma.
  - Eiffel, Oulondelo, Instituto ITSO, IMPO (Pedagogia), Colégio Bolet Salú, Colégio Pitágoras, Colégio Arcanjo: Naipalala.
  - Cesmo, Colégio Ednans, Colégio Popiene, Marco Lendros: Kaculuvale.
  - Complexo Abcunene: Caxila 3.
- Escolas Primárias/1º Ciclo: Cow-Boy (Castilhos), Centralidade, Ocapale (Kaculuvale), Rei Nande (Naipalala), E.P. 122 (Zeca), 4 de Janeiro (Kafitu1), e outras nos bairros Kafitu2, Onahumba e Zeca.

### 5. SERVIÇOS E COMÉRCIO
- Bancos: 
  - Centro: BAI. 
  - Bangula: BCI, BPC, Banco Sol, Banco Económico. 
  - Zeca: BFA, BIC. 
  - Castilhos: BCA. 
  - Naipalala: BPC2, Atlântico.
- Supermercados: Shoprite e AngoMarte (Castilhos).
- Lazer/Restaurantes: Lodge (Naipalala), Cumbuessa (Zeca), Moreira (Caxila 2), Skiva (Caxila 3), Vila Ocapale. Brothers (Bangula/Zeca), Fórmula (Zeca), Rodrigão (Zeca), Rosmélia (Castilhos), Kaculuvale.

### 6. DESPORTO
- Estádios: Onze de Novembro (Castilhos) e Campo da Centralidade.
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
                return "🚨 Erro: API da IA não configurada."
                
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
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
