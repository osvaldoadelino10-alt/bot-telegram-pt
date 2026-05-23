import os
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai

# ==========================================
# 1. CONFIGURAÇÕES E VARIÁVEIS DE AMBIENTE
# ==========================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Configura a API do Gemini com a chave do Render
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Contexto para o teu TCC (Bíblia de Ondjiva / Cunene)
CONTEXTO_ONDJIVA = (
    "Tu és o Ndjili, um assistente virtual inteligente e amigável criado para apoiar a "
    "população da província do Cunene, em Angola. O teu objetivo é ajudar os cidadãos com "
    "informações sobre serviços públicos, saúde, contactos de emergência locais e apoiar na "
    "reportagem de problemas municipais (como falta de água, luz, buracos nas vias ou saneamento). "
    "Responde sempre em português de Angola, usa uma linguagem acolhedora, respeitosa e foca-te "
    "em soluções para a região do Cunene (Ondjiva, Namacunde, Cuanhama, etc.)."
)

# Inicializa o Flask para o Render não dar timeout
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot do Cunene está Online e Ativo!"

# ==========================================
# 2. COMANDOS DO TELEGRAM
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nome = update.effective_user.first_name
    boas_vindas = (
        f"Olá {nome}! 🇦🇴 Bem-vindo ao assistente do Cunene.\n\n"
        "Estou aqui para ajudar com informações sobre a nossa província e apoiar a comunidade.\n\n"
        "👉 Para reportar um problema na tua rua, escreva: *Reportagem [teu relato]*\n"
        "👉 Para emergências, escreva: *Emergência*"
    )
    await update.message.reply_text(boas_vindas, parse_mode="Markdown")

# ==========================================
# 3. FILTROS E PROCESSAMENTO DA IA
# ==========================================
async def processar_mensagem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_text = update.message.text
    texto_baixo = user_text.lower()
    
    print(f"📥 Mensagem recebida: {user_text}")

    # --- FILTRO 1: EMERGÊNCIA ---
    if any(palavra in texto_baixo for palavra in ["emergencia", "emergência", "perigo", "socorro", "policia", "bombeiros"]):
        resposta = (
            "🚨 **ALERTA DE EMERGÊNCIA IMEDIATA!** 🚨\n\n"
            "Se estás diante de uma situação de perigo real ou acidente no Cunene, liga diretamente:\n"
            "🚓 **Polícia Nacional:** 113\n"
            "👨‍🚒 **Bombeiros (Proteção Civil):** 115\n\n"
            "Por favor, mantém-te em segurança!"
        )
    
    # --- FILTRO 2: REPORTAGEM MUNICIPAL ---
    elif "reportagem" in texto_baixo:
        relato = user_text.replace("Reportagem", "").replace("reportagem", "").strip()
        if not relato:
            resposta = (
                "🚨 **Como fazer uma reportagem:**\n"
                "Escreve a palavra *Reportagem* seguida do problema técnico.\n\n"
                "Exemplo:\n"
                "_Reportagem Falta de iluminação pública na rua principal de Naipalala._"
            )
        else:
            resposta = (
                "✅ **Ocorrência Registada no Sistema!**\n\n"
                f"O teu relato: \"_{relato}_\" foi guardado com sucesso e será encaminhado para as "
                "equipas de análise da Administração Municipal.\n\n"
                "Obrigado por ajudares a melhorar o Cunene!"
            )

    # --- FILTRO 3: INTELIGÊNCIA ARTIFICIAL (GEMINI) ---
    else:
        try:
            if not GEMINI_API_KEY:
                resposta = "🚨 Erro interno: A chave da API do Gemini não foi configurada no Render."
            else:
                # Modelo correto, atualizado e estável para a API pública da Google
                model = genai.GenerativeModel('gemini-1.5-flash', system_instruction=CONTEXTO_ONDJIVA)
                response = model.generate_content(user_text)
                resposta = response.text
        except Exception as erro_tecnico:
            resposta = f"❌ Erro Técnico do Gemini: {erro_tecnico}"

    await update.message.reply_text(resposta, parse_mode="Markdown")

# ==========================================
# 4. EXECUÇÃO DO BOT
# ==========================================
if __name__ == '__main__':
    import threading

    # 1. Inicia o Flask numa thread secundária para o URL do Render responder "Online"
    port = int(os.environ.get("PORT", 5000))
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=port, use_reloader=False)).start()

    # 2. Inicia o Bot do Telegram na thread principal
    if not TELEGRAM_TOKEN:
        print("🚨 ERRO CRÍTICO: TELEGRAM_TOKEN não configurado!")
    else:
        print("🚀 A iniciar ligação com o Telegram...")
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        
        # Adiciona os detetores de mensagens
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, processar_mensagem))
        
        # Corre o bot continuamente
        application.run_polling()
