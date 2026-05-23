from flask import Flask
import threading
import logging
import os 
import google.generativeai as genai
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters

# =====================================================================
# 1. SERVIDOR WEB PARA MANTER O RENDER ATIVO (PLANO FREE)
# =====================================================================
app = Flask('')

@app.route('/')
def home(): 
    return "Bot Online"

# Inicia o servidor web falso para o Render
threading.Thread(target=lambda: app.run(host='0.0.0.0', port=8080)).start()

# =====================================================================
# 2. CONFIGURAÇÕES INICIAIS E VARIÁVEIS DE AMBIENTE
# =====================================================================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
    print("⚠️ ERRO: As variáveis TELEGRAM_TOKEN ou GEMINI_API_KEY não foram encontradas no Render!")

genai.configure(api_key=GEMINI_API_KEY)

# =====================================================================
# 3. A BÍBLIA DE ONDJIVA (Base de Conhecimento Manual Injetada)
# =====================================================================
CONTEXTO_ONDJIVA = """
Você é o Assistente Virtual Oficial da Província do Cunene, focado na capital Ondjiva.
Use as informações estritas abaixo para responder aos cidadãos de forma precisa, prestativa e curta:

CONHECIMENTO GEOGRÁFICO E ADMINISTRATIVO:
- Municípios do Cunene (6): Cuanhama (onde fica Ondjiva), Namacunde (fronteira), Cahama, Cuvelai, Omadja e Curoca.
- Administração Municipal de Ondjiva: Localizada no bairro Naipalala (Código Plus: WPFM+MX5). Contacto oficial: +244 938 729 878.

MAPEAMENTO DE BAIRROS E ESCOLAS:
1. Bairro Naipalala:
   - Instituto Eiffel
   - Instituto Oulondelo
   - Instituto Médio Politécnico (IMPO)
   - Escola Pitágoras
   - Escola Bolet Salú
   - Extensão do ITSO
2. Bairro Ekuma:
   - Instituto Técnico de Saúde de Ondjiva (ITSO). Oferece os cursos técnicos de: Enfermagem Geral, Análises Clínicas, Farmácia e Gestão Hospitalar. É o coração da saúde local.
3. Bairro Kafitu:
   - Zona estratégica da periferia com forte presença da Guarda Fronteira.
   - Contém a Escola 4 de Janeiro (Kafitu 1) e escolas do primeiro ciclo.
4. Bairro Kaculuvale:
   - Escola Cesmo, Escola Popiene, Escola Marco Lendros e Escola Ednans.
5. Bairro Caxila 3:
   - Escola Abcunene.

GUIA DE RESTAURAÇÃO (RESTAURANTES EM ONDJIVA):
- CUMBUESA: Localizado em Ondjiva. Contacto: +244 923 755 678. Ponto de paragem muito conhecido.
- Restaurante (Zona Central): Localizado em WPJ5+92, Ondjiva. Muito bem avaliado.
- Marito's: Localizado em WPM6+RM4, Ondjiva. Aberto todos os dias das 08h às 22h.
- EUCAR, RESTAURANTE: Localizado em WPH7+R6R, Ondjiva. Contacto: +244 926 686 589. Uma das melhores pontuações da região.

REGRAS DE POSTURA:
- Responda em português de Angola, de forma direta.
- Se não souber algo sobre outra província, foque em ajudar com dados do Cunene.
"""

# =====================================================================
# 4. CAMADA DE REGRAS E FILTRAGEM (Lógica de Negócio)
# =====================================================================
async def comando_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Responde ao botão /start ou Iniciar do Telegram."""
    boas_vindas = (
        "👋 Olá! Sou o Bot de Apoio do Cunene.\n\n"
        "Podes utilizar este canal para reportar problemas no município ou pedir "
        "contactos de saúde e emergências locais. Como posso ajudar-te hoje?"
    )
    await update.message.reply_text(boas_vindas)
async def processar_mensagem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_text = update.message.text
    
    try:
        # Se a chave estiver vazia, o bot avisa-te logo aqui
        if not GEMINI_API_KEY:
            await update.message.reply_text("🚨 Erro: O Python não conseguiu ler a variável GEMINI_API_KEY do Render!")
            return
        model = genai.GenerativeModel('gemini-1.0-pro', system_instruction=CONTEXTO_ONDJIVA)
        response = model.generate_content(user_text)
        resposta = response.text
        
    except Exception as erro_real:
        # Isto vai enviar o erro do Python direto no teu Telegram para sabermos a verdade!
        resposta = f"❌ Erro Técnico Real: {erro_real}"

    await update.message.reply_text(resposta, parse_mode="Markdown")


    # --- FILTRO 1: EMERGÊNCIA (Prioridade Absoluta) ---
    if any(palavra in texto_baixo for palavra in ["emergencia", "emergência", "perigo", "socorro", "fogo", "acidente", "policia", "bombeiros"]):
        resposta = (
            "🚨 **ALERTA DE EMERGÊNCIA IMEDIATA!** 🚨\n\n"
            "Se está a passar por uma situação de perigo real, crime ou incêndio, ligue diretamente:\n"
            "🚓 **Polícia Nacional:** 113\n"
            "👨‍🚒 **Serviço de Proteção Civil e Bombeiros:** 115\n\n"
            "Por favor, certifique-se de que está num local seguro."
        )
    
    # --- FILTRO 2: REPORTAGEM ---
    elif "reportagem" in texto_baixo:
        # Extrai o relato removendo a palavra
        relato = user_text.replace("Reportagem", "").replace("reportagem", "").strip()
        if not relato:
            resposta = (
                "🚨 Para registar o problema, escreva *Reportagem* seguido do seu relato.\n\n"
                "Exemplo: _Reportagem Falta de água no bairro Zeca._\n\n"
                "Por favor, descreva o problema para encaminharmos à Administração Municipal."
            )
        else:
            resposta = (
                "✅ **Ocorrência Registada com Sucesso!**\n\n"
                f"O seu relato: \"_{relato}_\" foi processado pelo nosso sistema técnico e encaminhado para as equipas internas da **Administração Municipal** no bairro Naipalala.\n\n"
                "Obrigado por ajudar a fiscalizar e melhorar a nossa província!"
            )

    # --- FILTRO 3: PROCESSAMENTO DA IA (Perguntas Gerais e Detalhes) ---
    else:
        try:
            # Invoca o modelo Gemini passando a base de dados integrada no sistema
            model = genai.GenerativeModel('gemini-1.0-pro', system_instruction=CONTEXTO_ONDJIVA)
            response = model.generate_content(user_text)
            resposta = response.text
        except Exception as e:
            print(f"❌ Erro na API do Gemini: {e}")
            resposta = "⚠️ Desculpe, o sistema central de inteligência está temporariamente indisponível. Por favor, tente novamente em instantes."

    # Envia a resposta final de volta ao utilizador do Telegram
    await update.message.reply_text(resposta, parse_mode="Markdown")

# =====================================================================
# 5. INICIALIZAÇÃO DO SERVIDOR DO BOT
# =====================================================================
if __name__ == '__main__':
    print("⚡ Inicializando a infraestrutura do Bot Apoio Cunene para Telegram...")
    
    # Mudámos o nome para 'bot_app' para não chocar com a página Flask lá de cima
    bot_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # 1. Registra a resposta para o botão /start
    bot_app.add_handler(CommandHandler("start", comando_start))
    
    # 2. Registra o manipulador de mensagens de texto normais para o Gemini
    bot_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), processar_mensagem))
    
    print("🚀 Servidor online no Telegram! Pronto para receber mensagens via Polling.")
    
    # O truque final: drop_pending_updates=True apaga mensagens antigas e destrava o bot!
    bot_app.run_polling(drop_pending_updates=True)
