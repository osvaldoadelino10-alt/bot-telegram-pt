import os
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Novas importações da biblioteca moderna da Google
from google import genai
from google.genai import types

# ==========================================
# 1. CONFIGURAÇÕES E VARIÁVEIS DE AMBIENTE
# ==========================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Inicializa o cliente do novo SDK da Google
client = None
if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY)

# ==========================================
# 2. A BÍBLIA DE ONDJIVA (Base de Conhecimento do TCC)
# ==========================================
CONTEXTO_ONDJIVA = """
Tu és o Ndjili, o assistente virtual oficial e inteligente da província do Cunene, em Angola. 
O teu papel é ser um prestador de serviços de utilidade pública para os cidadãos do Cunene (focado nos municípios de Cuanhama, Namacunde, Ombadja, Cuvelai, Curoca e Cahama, com destaque para a cidade de Ondjiva).

A tua linguagem deve ser sempre no Português de Angola: acolhedora, respeitosa, prestativa e muito educada. Trata os cidadãos com proximidade, mas mantém a formalidade de um serviço público.

=== DIRETRIZES DE ATENDIMENTO ===
1. Sê direto e claro nas respostas, evitando blocos de texto demasiado longos.
2. Foca-te em resolver problemas locais: infraestruturas, saúde, segurança e serviços públicos.
3. Se o utilizador relatar um problema na rua (ex: buraco, falta de luz, falta de água, lixo acumulado), orienta-o a escrever a palavra "Reportagem" seguida do problema, para que o nosso sistema automático possa registar e enviar à Administração Municipal.
4. Para situações de perigo imediato, encaminha sempre para os números de emergência oficiais.

=== BASE DE DADOS E CONTACTOS LOCAIS ===
- Segurança e Polícia Nacional (Comando Provincial do Cunene): Ligar para o 113.
- Bombeiros e Proteção Civil: Ligar para o 115.
- Saúde: Hospital Geral de Ondjiva e principais centros médicos de referência na província.

=== CONTEXTO DO PROJETO ===
Deves saber (e informar se perguntarem) que foste desenvolvido como uma inovação tecnológica (projeto de fim de curso - TCC) para modernizar a província do Cunene. O teu objetivo é dar voz aos munícipes e criar uma ponte direta, rápida e digital entre a população e as autoridades locais para a resolução de problemas e prestação de informações úteis.
"""

# Inicializa o Flask para o Render não dar timeout
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot do Cunene está Online e Ativo!"

# ==========================================
# 3. COMANDOS DO TELEGRAM
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nome = update.effective_user.first_name
    boas_vindas = (
        f"Olá {nome}! 🇦🇴 Bem-vindo ao Ndjili, o assistente do Cunene.\n\n"
        "Estou aqui para te ajudar com informações úteis sobre a nossa província e apoiar a comunidade.\n\n"
        "👉 Para reportar um problema na tua zona (água, luz, estradas), escreve: *Reportagem [teu relato]*\n"
        "👉 Para pedir ajuda urgente, escreve: *Emergência*\n"
        "👉 Ou simplesmente faz-me uma pergunta sobre os nossos serviços locais!"
    )
    await update.message.reply_text(boas_vindas, parse_mode="Markdown")

# ==========================================
# 4. FILTROS E PROCESSAMENTO DA IA
# ==========================================
async def processar_mensagem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_text = update.message.text
    texto_baixo = user_text.lower()
    
    print(f"📥 Mensagem recebida: {user_text}")

    # --- FILTRO 1: EMERGÊNCIA ---
    if any(palavra in texto_baixo for palavra in ["emergencia", "emergência", "perigo", "socorro", "policia", "bombeiros", "acidente", "fogo"]):
        resposta = (
            "🚨 **ALERTA DE EMERGÊNCIA IMEDIATA!** 🚨\n\n"
            "Se estás diante de uma situação de perigo real, acidente ou incêndio no Cunene, liga de imediato para as autoridades:\n\n"
            "🚓 **Polícia Nacional:** 113\n"
            "👨‍🚒 **Bombeiros (Proteção Civil):** 115\n\n"
            "Por favor, procura um local seguro!"
        )
    
    # --- FILTRO 2: REPORTAGEM MUNICIPAL ---
    elif "reportagem" in texto_baixo:
        relato = user_text.replace("Reportagem", "").replace("reportagem", "").strip()
        if not relato:
            resposta = (
                "🚨 **Como registar uma ocorrência:**\n\n"
                "Para avisar a Administração sobre um problema, escreve a palavra *Reportagem* seguida da descrição.\n\n"
                "Exemplo:\n"
                "_Reportagem Falta de iluminação pública no bairro Naipalala, rua principal._"
            )
        else:
            resposta = (
                "✅ **Ocorrência Registada com Sucesso no Sistema!**\n\n"
                f"O teu relato: \"_{relato}_\"\n"
                "Foi guardado de forma segura e será reencaminhado para as equipas técnicas da Administração Municipal.\n\n"
                "Obrigado por exerceres a tua cidadania e ajudares a desenvolver o Cunene!"
            )

    # --- FILTRO 3: INTELIGÊNCIA ARTIFICIAL (GEMINI NOVA API) ---
    else:
        try:
            if not client:
                resposta = "🚨 Erro interno de Servidor: A chave da API do Gemini não foi configurada corretamente no sistema."
            else:
                # O processamento com a nova sintaxe do Google GenAI
                response = client.models.generate_content(
                    model='gemini-1.5-flash',
                    contents=user_text,
                    config=types.GenerateContentConfig(
                        system_instruction=CONTEXTO_ONDJIVA,
                    )
                )
                resposta = response.text
        except Exception as erro_tecnico:
            resposta = f"❌ Ocorreu um erro técnico na IA ao tentar responder: {erro_tecnico}"

    # Envia a resposta final para o chat do utilizador
    await update.message.reply_text(resposta, parse_mode="Markdown")

# ==========================================
# 5. EXECUÇÃO DO SERVIDOR E DO BOT
# ==========================================
if __name__ == '__main__':
    import threading

    # Mantém a porta aberta para o Render não desligar o processo
    port = int(os.environ.get("PORT", 5000))
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=port, use_reloader=False)).start()

    # Arranca o cérebro principal do Bot do Telegram
    if not TELEGRAM_TOKEN:
        print("🚨 ERRO CRÍTICO: A variável TELEGRAM_TOKEN não foi configurada no Render!")
    else:
        print("🚀 A iniciar a ligação segura com o Telegram e a IA...")
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, processar_mensagem))
        
        # Inicia a escuta de mensagens sem bloquear o Render
        application.run_polling()
