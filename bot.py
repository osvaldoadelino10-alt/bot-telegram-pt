import os
import time
import threading
import requests
import psycopg2
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from openai import OpenAI

# ==========================================
# 1. VARIÁVEIS DE AMBIENTE
# ==========================================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
WHATSAPP_PHONE_ID = os.environ.get("WHATSAPP_PHONE_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "cunene2026")  # em produção remove o fallback
DATABASE_URL = os.environ.get("DATABASE_URL")

client = None
if GROQ_API_KEY:
    base_url = "https://api.api.groq.com/openai/v1" if "api.api.groq.com" in os.environ.get("GROQ_BASE_URL", "") else "https://api.groq.com/openai/v1"
    client = OpenAI(api_key=GROQ_API_KEY, base_url=base_url)

app = Flask(__name__)

# Estruturas de memória
MEMORIA_CONVERSAS = {}
MEMORIA_TIMESTAMPS = {}
ESTADO_REPORTAGEM = {}
ESTADO_NAVEGACAO = {}
ULTIMA_MENSAGEM_BOT = {}       # guarda a última resposta enviada a cada telefone

# ==========================================
# COORDENADAS DE ONDJIVA
# ==========================================
COORDENADAS_ONDJIVA = {
    # ... (todo o dicionário igual ao anterior)
}

# ==========================================
# 2. BASE DE CONHECIMENTO PARA A IA
# ==========================================
CONTEXTO_ONDJIVA = """
Tu és o Bot_cunene, assistente oficial de Ondjiva. Usa linguagem natural de Angola, calorosa e directa.
... (texto completo igual ao anterior, com 14 municípios)
"""

# ==========================================
# 3. FUNÇÕES DE ENVIO E BASE DE DADOS
# ==========================================
def enviar_mensagem_whatsapp(telefone_destino, texto):
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID:
        return
    texto = texto.replace("**", "*")
    # Guarda a última mensagem enviada (para fallback do sub‑menu)
    ULTIMA_MENSAGEM_BOT[telefone_destino] = texto
    if len(texto) > 3800:
        enviar_mensagens_partidas(telefone_destino, texto)
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
    requests.post(url, headers=headers, json=payload)

def enviar_mensagens_partidas(telefone_destino, texto):
    max_len = 3800
    while len(texto) > max_len:
        corte = texto.rfind(' ', 0, max_len)
        if corte == -1:
            corte = max_len
        bloco = texto[:corte].strip()
        enviar_mensagem_whatsapp(telefone_destino, bloco)
        texto = texto[corte:].strip()
        time.sleep(0.5)
    if texto:
        enviar_mensagem_whatsapp(telefone_destino, texto)

def enviar_localizacao_whatsapp(telefone_destino, latitude, longitude, nome_local, endereco):
    # ... (mantém igual)
    pass

def guardar_reportagem_bd(telefone, relato):
    # ... (mantém igual)
    pass

# ==========================================
# 4. LIMPEZA PERIÓDICA DE MEMÓRIA
# ==========================================
def limpar_memoria_antiga():
    while True:
        time.sleep(600)
        agora = datetime.utcnow()
        chaves = [tel for tel, ts in MEMORIA_TIMESTAMPS.items() if (agora - ts).total_seconds() > 3600]
        for tel in chaves:
            MEMORIA_CONVERSAS.pop(tel, None)
            MEMORIA_TIMESTAMPS.pop(tel, None)
            ESTADO_REPORTAGEM.pop(tel, None)
            ESTADO_NAVEGACAO.pop(tel, None)
            ULTIMA_MENSAGEM_BOT.pop(tel, None)

threading.Thread(target=limpar_memoria_antiga, daemon=True).start()

# ==========================================
# 5. PROCESSAMENTO PRINCIPAL (COM FALLBACK DO SUB‑MENU)
# ==========================================
def processar_texto(telefone_origem, user_text):
    texto_baixo = user_text.lower().strip()
    MEMORIA_TIMESTAMPS[telefone_origem] = datetime.utcnow()

    # Fallback inteligente para sub‑menu: se a última mensagem do bot foi o menu de categorias,
    # e o utilizador envia uma única letra A-F, processamos como escolha do sub‑menu.
    ultima = ULTIMA_MENSAGEM_BOT.get(telefone_origem, "")
    if ("escolhe a categoria" in ultima or "Informações oficiais – escolhe a categoria" in ultima) and texto_baixo.upper() in ["A","B","C","D","E","F"]:
        opcao = texto_baixo.upper()
        # Remove qualquer estado de navegação pendente para evitar conflitos
        ESTADO_NAVEGACAO.pop(telefone_origem, None)
        # Dá a resposta correspondente
        if opcao == "A":
            return "Horário: Seg‑Qui 08h‑15h30, Sex 08h‑15h. Repartições no Centro, Kaculuvale, Castilhos, Naipalala. Precisas de algo específico?"
        elif opcao == "B":
            return "Urgências 24h. Consultas Seg‑Sex 08h‑15h. Hospitais: Ekuma, Simeone Mucunde, Municipal. Mais detalhes?"
        elif opcao == "C":
            return (
                "Escolas públicas: ITSO (saúde), Oulondelo, IMPO (pedagogia), Cesmo, ITAS, Eiffel, várias primárias.\n"
                "Colégios (privados): Pitágoras, Ednas, Popiene, Marc Leandres, Bulet Salú 1/2, Abcunene.\n"
                "Posso detalhar cursos de uma escola específica. Qual te interessa?"
            )
        elif opcao == "D":
            return "Bancos Seg‑Sex 08h‑15h. BAI, BFA, BIC no Centro; BCI, BPC, Sol, Económico em Bangula; BPC2 e Atlântico em Naipalala."
        elif opcao == "E":
            return "Shoprite e AngoMarte (Castilhos) abertos todos os dias 08h‑20h. Campo Provincial e da Centralidade para desporto."
        elif opcao == "F":
            return (
                "A província do Cunene é formada por *14 municípios*:\n"
                "Cahama, Cuanhama, Curoca, Cuvelai, Namacunde, Ombadja, Chiéde, Nehone, Humbe, Mupa, Naulila, Chitado, Cafima, Chissuata.\n\n"
                "Se quiseres a lista completa com comunas e administradores, escreve: *lista completa dos municípios*."
            )

    # --- NAVEGAÇÃO (MENU) ---
    if telefone_origem in ESTADO_NAVEGACAO:
        estado = ESTADO_NAVEGACAO[telefone_origem]
        nivel = estado.get("nivel", "menu")

        if nivel == "menu":
            # ... igual ao anterior
            pass

        elif nivel == "info_submenu":
            # Este bloco agora é um backup, pois o fallback acima já deveria ter tratado a letra.
            opcao = texto_baixo.upper().strip()
            categorias = {"A": "adm", "B": "saude", "C": "ensino", "D": "bancos", "E": "comercio", "F": "divisao"}
            if opcao in categorias:
                ESTADO_NAVEGACAO.pop(telefone_origem)
                if opcao == "A":
                    return "Horário: Seg‑Qui 08h‑15h30, Sex 08h‑15h. Repartições no Centro, Kaculuvale, Castilhos, Naipalala. Precisas de algo específico?"
                elif opcao == "B":
                    return "Urgências 24h. Consultas Seg‑Sex 08h‑15h. Hospitais: Ekuma, Simeone Mucunde, Municipal. Mais detalhes?"
                elif opcao == "C":
                    return "Escolas públicas: ITSO (saúde), Oulondelo, IMPO (pedagogia), Cesmo, ITAS, Eiffel, várias primárias.\nColégios (privados): Pitágoras, Ednas, Popiene, Marc Leandres, Bulet Salú 1/2, Abcunene.\nPosso detalhar cursos de uma escola específica. Qual te interessa?"
                elif opcao == "D":
                    return "Bancos Seg‑Sex 08h‑15h. BAI, BFA, BIC no Centro; BCI, BPC, Sol, Económico em Bangula; BPC2 e Atlântico em Naipalala."
                elif opcao == "E":
                    return "Shoprite e AngoMarte (Castilhos) abertos todos os dias 08h‑20h. Campo Provincial e da Centralidade para desporto."
                elif opcao == "F":
                    return "A província do Cunene é formada por *14 municípios*: Cahama, Cuanhama, Curoca, Cuvelai, Namacunde, Ombadja, Chiéde, Nehone, Humbe, Mupa, Naulila, Chitado, Cafima, Chissuata.\n\nSe quiseres a lista completa com comunas e administradores, escreve: *lista completa dos municípios*."
            else:
                ESTADO_NAVEGACAO.pop(telefone_origem)

        elif nivel == "localizacao_pedido":
            # ... igual ao anterior
            pass

    # --- Restante do código (emergência, menu, reportagem, localização, IA) ---
    # ... (igual ao anterior)
