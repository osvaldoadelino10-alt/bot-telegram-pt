import os
import re
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

# ==========================================
# 2. DADOS OFICIAIS (FONTE ÚNICA DE VERDADE)
# ==========================================
# Base de conhecimento estruturada – tudo o que está aqui é respondido deterministicamente
DADOS_OFICIAIS = {
    "saude": {
        "hospitais": {
            "Hospital Provincial Ekuma": {
                "localizacao": "Bairro Ekuma, Ondjiva",
                "consultas": "Segunda a Sexta, 08h00-15h00",
                "urgencias": "24h"
            },
            "Hospital Central Simeone Mucunde": {
                "localizacao": "Bairro Naipalala, Ondjiva",
                "consultas": "Segunda a Sexta, 08h00-15h00",
                "urgencias": "24h"
            },
            "Hospital Municipal": {
                "localizacao": "Centro da Cidade, Ondjiva",
                "consultas": "Segunda a Sexta, 08h00-15h00",
                "urgencias": "24h"
            }
        },
        "campanhas": "Neste momento não há campanhas de vacinação activas. Consulte a unidade sanitária mais próxima."
    },
    "educacao": {
        "horario_aulas": "Manhã: 07h00-12h30 | Tarde: 13h00-17h30 | Noite: 18h00-22h30",
        "faculdades": "Rei Luhuna (Muhongo), Mandume (Naipalala)",
        "institutos_medios": "ITSO (Ekuma), Eiffel, Oulondelo, IMPO (Naipalala), Cesmo (Kaculuvale)",
        "colegios": "Ednas, Popiene, Marc Leandres (Kaculuvale); Pitágoras, Bulet Salú (Naipalala); Abcunene (Caxila 3); Bulet Salú2 (Zeca)",
        "escolas_primarias": "E.P 4 de Janeiro (Kafitu 1), E.P Okapacupacu (Kafitu2), E.P 122 (Zeca), E.P Rei Nande (Naipalala), E.P da Centralidade (Centralidade), E.P do Kaculuvale (Kaculuvale), E.P da Caxila1 (Caxila1), E.P da Caxila2 (Caxila2), E.P do Onahumba (Onahumba), E.P dos Castilhos (Castilhos)",
        "primeiro_ciclo": "C.Escolar Cowboy (Castilhos), E.Escolar Ocapale (Kaculuvale), C.E da Centralidade (Centralidade), E.P Rei Nande (Naipalala)"
    },
    "mercado": {
        "precos_semana": "Milho: 350 Kz/kg | Feijão: 600 Kz/kg | Arroz: 500 Kz/kg | Massango: 400 Kz/kg | Frango: 1500 Kz/unid",
        "mercado_central": "Mercado Ombandja – aberto todos os dias das 07h00 às 18h00",
        "supermercados": "Shoprite e AngoMarte – todos os dias 08h00-20h00 (Bairro Castilhos)"
    },
    "administracao": {
        "horario_atendimento": "Segunda a Quinta 08h00-15h30 | Sexta 08h00-15h00",
        "locais": {
            "Governo Provincial": "Centro da Cidade",
            "Administração Municipal": "Bairro Kaculuvale",
            "Comando da Polícia": "Castilhos (Municipal) / Naipalala (Provincial)",
            "Bombeiros": "Naipalala",
            "Justiça Provincial": "Naipalala",
            "AGT": "Centro da Cidade"
        }
    },
    "cheias": {
        "nivel_atual": "Normal (sem alerta ativo)",
        "subscritos": {},  # telefone -> bairro
        "zonas_risco": ["Kafitu 1", "Kafitu 2", "Caxila", "Onahumba", "Margens do Cunene"]
    },
    "emergencias": {
        "policia": "113",
        "bombeiros": "115",
        "protecao_civil": "222 123 456"
    }
}

# Pontos com coordenadas para envio de localização interativa
LOCAIS_COORDENADAS = {
    "hospital ekuma": {"lat": -17.0612, "lon": 15.7425, "nome": "Hospital Provincial da Ekuma", "endereco": "Bairro Ekuma, Ondjiva"},
    "simeone mucunde": {"lat": -17.0721, "lon": 15.7284, "nome": "Hospital Central Simeone Mucunde", "endereco": "Bairro Naipalala, Ondjiva"},
    "hospital municipal": {"lat": -17.0655, "lon": 15.7321, "nome": "Hospital Municipal de Ondjiva", "endereco": "Centro da Cidade, Ondjiva"},
    "shoprite": {"lat": -17.0688, "lon": 15.7195, "nome": "Supermercado Shoprite Ondjiva", "endereco": "Bairro Castilhos, Ondjiva"},
    "angomarte": {"lat": -17.0675, "lon": 15.7180, "nome": "Supermercado AngoMarte", "endereco": "Bairro Castilhos, Ondjiva"},
    "mediateca": {"lat": -17.0595, "lon": 15.7450, "nome": "Mediateca Lucas Damba", "endereco": "Bairro Kaculuvale, Ondjiva"},
    "aeroporto": {"lat": -17.0422, "lon": 15.7511, "nome": "Aeroporto Provincial 11 de Novembro", "endereco": "Bairro Kaculuvale, Ondjiva"},
    "campo provincial": {"lat": -17.0699, "lon": 15.7165, "nome": "Campo Provincial 11 de Novembro", "endereco": "Bairro Castilhos, Ondjiva"},
    "centralidade": {"lat": -17.0850, "lon": 15.7010, "nome": "Centralidade de Ondjiva", "endereco": "Ondjiva, Cunene"}
}

# Estado das conversas e reportagens
MEMORIA_CONVERSAS = {}      # telefone -> [{"role": "user/assistant", "content": ...}]
ESTADO_REPORTAGEM = {}      # telefone -> {"passo": 1/2, "problema": ..., "tempo": ..., "causa": ...}

# ==========================================
# 3. FUNÇÕES AUXILIARES (DATA/HORA, BD)
# ==========================================
def obter_hora_angola():
    """Retorna datetime actual de Angola (UTC+1)"""
    return datetime.utcnow() + timedelta(hours=1)

def saudacao_por_hora():
    hora = obter_hora_angola().hour
    if 5 <= hora < 12:
        return "Bom dia"
    elif 12 <= hora < 18:
        return "Boa tarde"
    else:
        return "Boa noite"

def horario_funcionamento():
    """Verifica se está dentro do horário de atendimento público (dias úteis)"""
    agora = obter_hora_angola()
    if agora.weekday() >= 5:  # Sábado (5) ou Domingo (6)
        return "FECHADO (fim‑de‑semana)"
    if agora.weekday() == 4:  # Sexta
        if 8 <= agora.hour < 15:
            return "ABERTO (08h00-15h00)"
    else:  # Segunda a Quinta
        if 8 <= agora.hour < 15.5:
            return "ABERTO (08h00-15h30)"
    return "FECHADO (fora do horário de expediente)"

def guardar_reportagem_bd(telefone, relato):
    """Guarda reportagem no PostgreSQL (se disponível)"""
    if not DATABASE_URL:
        print("⚠️ DATABASE_URL não configurada – reportagem apenas em memória.")
        return True
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
                cur.execute("INSERT INTO reportagens (telefone, relato) VALUES (%s, %s)", (telefone, relato))
                conn.commit()
        return True
    except Exception as e:
        print(f"Erro BD: {e}")
        return False

def subscrever_alerta_cheias(telefone, bairro):
    """Regista subscrição de alerta de cheias (em memória)"""
    if bairro.title() not in DADOS_OFICIAIS["cheias"]["zonas_risco"]:
        return False, "Esse bairro não está listado como zona de risco. Pode subscrever na mesma, mas os alertas são apenas preventivos."
    DADOS_OFICIAIS["cheias"]["subscritos"][telefone] = bairro.title()
    return True, f"Subscrição registada para *{bairro.title()}*. Receberá alertas de cheias quando o nível do Rio Cunene subir."

# ==========================================
# 4. ENVIO DE MENSAGENS (TEXTO, BOTÕES, LOCALIZAÇÃO)
# ==========================================
def enviar_mensagem_whatsapp(telefone_destino, texto, interactive=False, buttons=None):
    """Envia mensagem simples ou com botões (reply buttons)"""
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID:
        print("Credenciais WhatsApp em falta")
        return

    texto = texto.replace("**", "*")  # WhatsApp usa * para negrito, não **
    url = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}

    if interactive and buttons:
        # Cria botões interativos (máx 3)
        payload = {
            "messaging_product": "whatsapp",
            "to": telefone_destino,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": texto},
                "action": {"buttons": buttons[:3]}  # Cada button: {"type": "reply", "reply": {"id": "id", "title": "texto"}}
            }
        }
    else:
        payload = {
            "messaging_product": "whatsapp",
            "to": telefone_destino,
            "type": "text",
            "text": {"body": texto}
        }

    resposta = requests.post(url, headers=headers, json=payload)
    print(f"Envio WhatsApp: {resposta.status_code} – {resposta.text[:200]}")

def enviar_localizacao_whatsapp(telefone_destino, latitude, longitude, nome_local, endereco):
    """Envia um pin de localização"""
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID:
        return
    url = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": telefone_destino,
        "type": "location",
        "location": {"latitude": latitude, "longitude": longitude, "name": nome_local, "address": endereco}
    }
    requests.post(url, headers=headers, json=payload)

# ==========================================
# 5. LÓGICA DETERMINÍSTICA (MENUS E SUBMENUS)
# ==========================================
def processar_menu_principal(telefone, opcao):
    """Retorna resposta e possíveis botões para o menu principal"""
    s = saudacao_por_hora()
    menu_texto = (
        f"{s}! 🌿 Sou o *CuneneInfo*, assistente oficial de Ondjiva.\n\n"
        f"*Escolha uma opção:*\n"
        f"1️⃣ *Saúde* – hospitais, campanhas, urgências\n"
        f"2️⃣ *Educação* – escolas, faculdades, horários\n"
        f"3️⃣ *Mercado* – preços, supermercados, feira\n"
        f"4️⃣ *Administração* – horário, locais, contactos\n"
        f"5️⃣ *Cheias & Emergências* – alertas, subscrever\n"
        f"6️⃣ *Reportar problema* (água, luz, estrada)\n"
        f"0️⃣ *Falar com atendente humano*\n\n"
        f"*Responda com o número da opção* ou escreva a sua pergunta."
    )
    # Botões interativos (apenas 3 – opções mais usadas)
    botoes = [
        {"type": "reply", "reply": {"id": "opt1", "title": "🏥 Saúde"}},
        {"type": "reply", "reply": {"id": "opt2", "title": "📚 Educação"}},
        {"type": "reply", "reply": {"id": "opt5", "title": "⚠️ Cheias"}}
    ]
    return menu_texto, botoes

def processar_submenu_saude():
    return (
        "*🏥 SERVIÇOS DE SAÚDE EM ONDJIVA*\n\n"
        "*Hospitais:*\n"
        "• Hospital Provincial Ekuma (Bairro Ekuma) – Consultas: Seg‑Sex 08h-15h, Urgências 24h\n"
        "• Hospital Central Simeone Mucunde (Naipalala) – mesmo horário\n"
        "• Hospital Municipal (Centro) – mesmo horário\n\n"
        "*Campanhas:* " + DADOS_OFICIAIS["saude"]["campanhas"] + "\n\n"
        "*Emergência:* ligue 113 (Polícia) ou 115 (Bombeiros)\n\n"
        "Responda com o nome do hospital para receber a localização ou digite *Menu* para voltar."
    ), None

def processar_submenu_educacao():
    texto = (
        "*📚 EDUCAÇÃO EM ONDJIVA*\n\n"
        f"*Horário de aulas:* {DADOS_OFICIAIS['educacao']['horario_aulas']}\n\n"
        f"*Faculdades:* {DADOS_OFICIAIS['educacao']['faculdades']}\n"
        f"*Institutos médios:* {DADOS_OFICIAIS['educacao']['institutos_medios']}\n"
        f"*Colégios:* {DADOS_OFICIAIS['educacao']['colegios']}\n\n"
        f"*Escolas primárias:* {DADOS_OFICIAIS['educacao']['escolas_primarias']}\n\n"
        "Digite *Menu* para voltar."
    )
    return texto, None

def processar_submenu_mercado():
    texto = (
        "*💰 MERCADO EM ONDJIVA*\n\n"
        f"*Preços médios (esta semana):* {DADOS_OFICIAIS['mercado']['precos_semana']}\n\n"
        f"*Mercado Central (Ombandja):* {DADOS_OFICIAIS['mercado']['mercado_central']}\n"
        f"*Supermercados:* {DADOS_OFICIAIS['mercado']['supermercados']}\n\n"
        "Digite o nome de um supermercado (Shoprite, AngoMarte) para saber a localização.\n"
        "*Menu* para voltar."
    )
    return texto, None

def processar_submenu_administracao():
    horario_atual = horario_funcionamento()
    texto = (
        "*🏛 ADMINISTRAÇÃO PÚBLICA*\n\n"
        f"*Horário de atendimento:* {DADOS_OFICIAIS['administracao']['horario_atendimento']}\n"
        f"*Neste momento:* {horario_atual}\n\n"
        "*Principais locais:*\n"
        "• Governo Provincial – Centro\n"
        "• Administração Municipal – Bairro Kaculuvale\n"
        "• Comando Polícia – Castilhos (Municipal) / Naipalala (Provincial)\n"
        "• Bombeiros – Naipalala\n"
        "• Justiça Provincial – Naipalala\n\n"
        "Digite o nome do serviço para mais detalhes ou *Menu*."
    )
    return texto, None

def processar_submenu_cheias(telefone):
    nivel = DADOS_OFICIAIS["cheias"]["nivel_atual"]
    texto = (
        f"*🌊 SISTEMA DE ALERTA DE CHEIAS*\n\n"
        f"*Nível do Rio Cunene:* {nivel}\n"
        f"*Zonas de risco:* {', '.join(DADOS_OFICIAIS['cheias']['zonas_risco'])}\n\n"
        f"*Opções:*\n"
        f"• Digite *Consultar nível* para atualização\n"
        f"• Digite *Subscrever alertas* + bairro (ex: *Subscrever alertas Kafitu 1*)\n"
        f"• Digite *Emergência* para números de socorro\n\n"
        f"*Já subscreveu?* {'Sim' if telefone in DADOS_OFICIAIS['cheias']['subscritos'] else 'Não'}"
    )
    return texto, None

def processar_reportagem_inicio(telefone, problema_texto):
    """Inicia fluxo de reportagem (dois passos)"""
    if not problema_texto:
        return "Escreva *Reportagem* seguido do problema, ex: *Reportagem falta de água no Kafitu*", None
    ESTADO_REPORTAGEM[telefone] = {"passo": 1, "problema": problema_texto, "tempo": "", "causa": ""}
    return (
        "📝 *Sistema de Atendimento de Ocorrências*\n\n"
        f"Problema registado: _{problema_texto}_\n\n"
        "👉 *Há quanto tempo estão nessa situação?* (ex: 3 dias, 2 semanas)"
    ), None

def processar_resposta_reportagem(telefone, user_text):
    """Segundo passo do report – guarda tempo, pede causa"""
    dados = ESTADO_REPORTAGEM.get(telefone)
    if not dados or dados["passo"] != 1:
        return None, None
    dados["tempo"] = user_text.strip()
    dados["passo"] = 2
    return (
        "📝 *Passo 2 de 2 – Causa*\n\n"
        "Obrigado. Agora diga: *O que levou a esse acontecimento ou qual acha que é a causa?*\n"
        "(Se não souber, responda 'Não sei')"
    ), None

def processar_causa_reportagem(telefone, user_text):
    dados = ESTADO_REPORTAGEM.get(telefone)
    if not dados or dados["passo"] != 2:
        return None, None
    dados["causa"] = user_text.strip()
    relato_final = f"PROBLEMA: {dados['problema']} | DURAÇÃO: {dados['tempo']} | CAUSA: {dados['causa']}"
    guardar_reportagem_bd(telefone, relato_final)
    del ESTADO_REPORTAGEM[telefone]
    return (
        "✅ *Ocorrência submetida com sucesso!*\n\n"
        "O seu relatório foi enviado para a Administração Municipal de Ondjiva.\n"
        "Obrigado por ajudar a melhorar a nossa comunidade!\n\n"
        "Digite *Menu* para voltar."
    ), None

# ==========================================
# 6. IA GENERATIVA (APENAS PARA PERGUNTAS ABERTAS)
# ==========================================
CONTEXTO_IA = """
Tu és o Bot_cunene, assistente oficial de Ondjiva (Cunene, Angola).
REGRAS OBRIGATÓRIAS:
1. Responde APENAS em Português de Angola. Se pedirem inglês ou kwanyama, diga: "Atendemos exclusivamente em Língua Portuguesa."
2. NUNCA inventes informações. Se não souberes, responde: "Peço desculpa, não tenho informação oficial sobre isso. Tente uma das opções do menu (Saúde, Educação, Mercado, Administração, Cheias, Reportagem)."
3. Usa *asteriscos* para negrito (formato WhatsApp).
4. Não uses termos técnicos como "prompt", "base de dados", "modelo".
5. Respostas curtas, úteis e calorosas.
6. Saudações: deves usar a saudação correcta de acordo com a hora real de Angola (fornecida no sistema).
7. Sobre localizações: se alguém perguntar onde fica um local conhecido (Shoprite, hospital, etc.), responda com o endereço e diga que pode pedir "Enviar localização" para receber o mapa.
"""

def gerar_resposta_ia(telefone, pergunta):
    """Usa Groq/LLaMA para perguntas não cobertas pelos menus"""
    if not client:
        return "⚠️ Serviço de IA temporariamente indisponível. Use o menu digitando *Menu*."

    agora = obter_hora_angola()
    hora_str = agora.strftime("%H:%M")
    data_str = agora.strftime("%d/%m/%Y")
    saudacao = saudacao_por_hora()

    system_msg = (
        CONTEXTO_IA +
        f"\n[SISTEMA] Hoje é {data_str}, {hora_str} em Angola (UTC+1). A saudação correta agora é '{saudacao}'."
    )

    if telefone not in MEMORIA_CONVERSAS:
        MEMORIA_CONVERSAS[telefone] = []
    MEMORIA_CONVERSAS[telefone].append({"role": "user", "content": pergunta})
    if len(MEMORIA_CONVERSAS[telefone]) > 10:
        MEMORIA_CONVERSAS[telefone] = MEMORIA_CONVERSAS[telefone][-10:]

    messages = [{"role": "system", "content": system_msg}] + MEMORIA_CONVERSAS[telefone]
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            temperature=0.2,
            messages=messages
        )
        resposta = response.choices[0].message.content
        MEMORIA_CONVERSAS[telefone].append({"role": "assistant", "content": resposta})
        return resposta
    except Exception as e:
        print(f"Erro IA: {e}")
        return "Ocorreu um erro ao processar a sua pergunta. Por favor, tente novamente ou use o menu digitando *Menu*."

# ==========================================
# 7. ROTEADOR PRINCIPAL (MÁQUINA DE ESTADOS)
# ==========================================
def processar_texto(telefone, user_text):
    texto = user_text.strip()
    texto_lower = texto.lower()

    # --- 1. Fluxo de reportagem em andamento ---
    if telefone in ESTADO_REPORTAGEM:
        estado = ESTADO_REPORTAGEM[telefone]
        if estado["passo"] == 1:
            resp, _ = processar_resposta_reportagem(telefone, texto)
            return resp if resp else "Resposta inválida. Digite o tempo aproximado (ex: 2 semanas)."
        elif estado["passo"] == 2:
            resp, _ = processar_causa_reportagem(telefone, texto)
            return resp if resp else "Digite a causa ou 'Não sei'."
        else:
            del ESTADO_REPORTAGEM[telefone]

    # --- 2. Emergência (sobrescreve tudo) ---
    if any(p in texto_lower for p in ["emergencia", "emergência", "socorro", "perigo"]):
        return (
            "🚨 *EMERGÊNCIA – NÚMEROS ÚTEIS*\n\n"
            f"• Polícia Nacional: {DADOS_OFICIAIS['emergencias']['policia']}\n"
            f"• Bombeiros: {DADOS_OFICIAIS['emergencias']['bombeiros']}\n"
            f"• Protecção Civil: {DADOS_OFICIAIS['emergencias']['protecao_civil']}\n\n"
            "Mantenha a calma e procure um local seguro."
        )

    # --- 3. Comandos especiais ---
    if texto_lower == "menu" or texto_lower == "inicio" or texto_lower == "voltar":
        resp, botoes = processar_menu_principal(telefone, None)
        # Envia botões (se a API suportar) – simplificado: enviamos texto e depois tentamos botões
        enviar_mensagem_whatsapp(telefone, resp, interactive=True, buttons=botoes)
        return None  # Já enviámos a mensagem com botões

    if texto_lower.startswith("subscrever alertas"):
        bairro = texto[18:].strip()
        if not bairro:
            return "Digite *Subscrever alertas* seguido do nome do bairro (ex: *Subscrever alertas Kafitu 1*)."
        ok, msg = subscrever_alerta_cheias(telefone, bairro)
        return msg

    if texto_lower == "consultar nível":
        return f"🌊 *Nível do Rio Cunene:* {DADOS_OFICIAIS['cheias']['nivel_atual']} (dados do INAMET)."

    if texto_lower.startswith("reportagem"):
        problema = texto[10:].strip()
        resp, _ = processar_reportagem_inicio(telefone, problema)
        return resp

    # --- 4. Localização (pedido explícito) ---
    for chave, dados in LOCAIS_COORDENADAS.items():
        if chave in texto_lower and any(p in texto_lower for p in ["localização", "localizacao", "onde fica", "mapa"]):
            enviar_localizacao_whatsapp(telefone, dados["lat"], dados["lon"], dados["nome"], dados["endereco"])
            return f"📍 Enviei o mapa de *{dados['nome']}*. Clique no pin para abrir o GPS."

    # --- 5. Submenus numéricos ---
    if texto in ["1", "1️⃣"]:
        resp, _ = processar_submenu_saude()
        return resp
    if texto in ["2", "2️⃣"]:
        resp, _ = processar_submenu_educacao()
        return resp
    if texto in ["3", "3️⃣"]:
        resp, _ = processar_submenu_mercado()
        return resp
    if texto in ["4", "4️⃣"]:
        resp, _ = processar_submenu_administracao()
        return resp
    if texto in ["5", "5️⃣"]:
        resp, _ = processar_submenu_cheias(telefone)
        return resp
    if texto in ["6", "6️⃣"]:
        return "Para reportar um problema, escreva: *Reportagem* + descrição (ex: *Reportagem falta de água no bairro Kafitu*)."
    if texto in ["0", "0️⃣"]:
        return "📞 *Atendente humano*\n\nNeste momento não há atendente disponível. Deixe mensagem que retornaremos em breve. Número alternativo: 222 123 456 (Provedoria)."

    # --- 6. Perguntas directas sobre dados oficiais (para evitar IA) ---
    if "hospital" in texto_lower and ("horario" in texto_lower or "consulta" in texto_lower):
        return "Horário de consultas externas: Segunda a Sexta, 08h00-15h00. Urgências: 24h."
    if "preço" in texto_lower and ("milho" in texto_lower or "feijão" in texto_lower or "mercado" in texto_lower):
        return DADOS_OFICIAIS["mercado"]["precos_semana"]
    if "horário" in texto_lower and "administração" in texto_lower:
        return f"Horário de atendimento: {DADOS_OFICIAIS['administracao']['horario_atendimento']} – Agora: {horario_funcionamento()}"

    # --- 7. Fallback: IA generativa ---
    return gerar_resposta_ia(telefone, texto)

# ==========================================
# 8. WEBHOOK FLASK (META)
# ==========================================
@app.route('/', methods=['GET'])
def home():
    return "Bot CuneneInfo activo – atende via WhatsApp.", 200

@app.route('/webhook', methods=['GET'])
def verificar_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode and token and mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Token inválido", 403

@app.route('/webhook', methods=['POST'])
def receber_mensagens():
    body = request.get_json()
    if not body or "entry" not in body:
        return jsonify({"status": "erro"}), 404

    try:
        changes = body["entry"][0]["changes"][0]["value"]
        if "messages" in changes:
            msg = changes["messages"][0]
            if msg["type"] == "text":
                telefone = msg["from"]
                texto = msg["text"]["body"]
                print(f"📩 {telefone}: {texto}")
                resposta = processar_texto(telefone, texto)
                if resposta:
                    enviar_mensagem_whatsapp(telefone, resposta)
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print(f"Erro no webhook: {e}")
        return jsonify({"status": "erro", "detalhe": str(e)}), 500

# ==========================================
# 9. KEEP‑ALIVE (EVITA HIBERNAÇÃO NO RENDER)
# ==========================================
def keep_awake():
    url = "https://" + os.environ.get("RENDER_EXTERNAL_URL", "localhost")
    while True:
        time.sleep(780)  # a cada 13 minutos
        try:
            requests.get(url, timeout=10)
            print("Ping keep‑alive enviado.")
        except:
            pass

if __name__ == '__main__':
    threading.Thread(target=keep_awake, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
