import os
from flask import FLask, request
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = "8322294828:AAEtputFF8a9KAOJmrqlgYLxlMPAvHHot8Y"

# --- START ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Bem-vindo ao Complexo Escolar Pitágoras!\n"
        "Digite 'menu' para ver as opções."
    )

# --- MENSAGENS ---
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.lower()

    # Saudações
    if texto in ["oi", "olá", "ola"]:
        await update.message.reply_text("Olá 👋 Bem-vindo ao Pitágoras!")

    elif "bom dia" in texto:
        await update.message.reply_text("🌞 Bom dia! Como posso ajudar?")

    elif "boa tarde" in texto:
        await update.message.reply_text("🌤 Boa tarde! Em que posso ajudar?")

    elif "como estás" in texto or "como estas" in texto:
        await update.message.reply_text("Estou bem 😊 e pronto para ajudar!")

    elif "estás bem" in texto or "estas bem" in texto:
        await update.message.reply_text("Sim 👍 sempre pronto para ajudar!")

    # Nomes específicos
    elif "augusto" in texto:
        await update.message.reply_text(
            "É uma pessoa muito fixe 😊"
        )

    elif "osvaldo" in texto or "quem é o osvaldo" in texto or "quem é o teu criador" in texto:
        await update.message.reply_text("Osvaldo, mais conhecido como Osvaldo Adelino ou Neymar Jr,é o criador deste sistema 👨‍💻")

    elif "pedro" in texto:
        await update.message.reply_text("CR7 ⚽🔥")

    # Menu / Info da escola
    elif "menu" in texto:
        await update.message.reply_text(
            "📚 Complexo Escolar Pitágoras\n\n"
            "📞 Secretária: 976 369 133\n\n"
            "🎓 Cursos:\n"
             "- Informática\n"
            "- Enfermagem Geral\n"
            "- Electricidade\n"
            "- Análises Clínicas\n"
            "- Farmácia\n"
         "⏰ Abertura da secretrária:\n"
            "Manhã: 07:30 - 15:00"
           
        )

    else:
        await update.message.reply_text("Escreve 'menu' para ver informações do Pitágoras 📚")

# --- APP ---
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT, responder))

flask_app = Flask(__name__)

@flask_app.route('/webhook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), app.bot)
    app.process_update(update)
    return 'ok'
@flask_app.route('/') 
def index():
    return 'Bot do Pitágoras online!'

if __name__=="__main__":
    app.run_webhook(
        listen="0.0.0",
        port=int(os.environ.get('PORT', 5000)),
        webhook_url=f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/webhook"
    )
else:
    app.run_webhook(
        listen="0.0.0",
        port=int(os.environ.get('PORT', 5000)),
        webhook_url=f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/webhook"





    
















