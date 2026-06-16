import os
import time
import threading
import signal
import sys
import requests
import psycopg2
from datetime import datetime, timedelta
from collections import defaultdict, deque
from flask import Flask, request, jsonify
from openai import OpenAI

# ══════════════════════════════════════════════════════════════════════
# 1. VARIÁVEIS DE AMBIENTE
# ══════════════════════════════════════════════════════════════════════
GROQ_API_KEY       = os.environ.get("GROQ_API_KEY")
WHATSAPP_TOKEN     = os.environ.get("WHATSAPP_TOKEN")
WHATSAPP_PHONE_ID  = os.environ.get("WHATSAPP_PHONE_ID")
VERIFY_TOKEN       = os.environ.get("VERIFY_TOKEN", "cunene2026")
DATABASE_URL       = os.environ.get("DATABASE_URL")
TIMEOUT_REPORTAGEM = int(os.environ.get("TIMEOUT_REPORTAGEM", "900"))   # segundos
MAX_MSG_POR_MINUTO = int(os.environ.get("MAX_MSG_POR_MINUTO", "30"))

# Cliente Groq / OpenAI-compatible
client = None
if GROQ_API_KEY:
    client = OpenAI(
        api_key=GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1"
    )

app = Flask(__name__)

# ══════════════════════════════════════════════════════════════════════
# 2. ESTRUTURAS DE MEMÓRIA (em RAM — limpas ao reiniciar)
# ══════════════════════════════════════════════════════════════════════
MEMORIA_CONVERSAS   = {}   # {tel: [{"role":…, "content":…}, …]}
MEMORIA_TIMESTAMPS  = {}   # {tel: datetime}  — para expirar sessões
ESTADO_REPORTAGEM   = {}   # {tel: {passo, problema, tempo, causa, inicio}}
ESTADO_NAVEGACAO    = {}   # {tel: {nivel}}
ESTADO_ROTA         = {}   # {tel: {lat, lon, nome, endereco}}
ULTIMA_MSG_BOT      = {}   # {tel: texto}  — para fallback de sub-menus

# Rate-limit: deque de timestamps por utilizador
RATE_LIMIT_STORE: dict[str, deque] = defaultdict(deque)

# ══════════════════════════════════════════════════════════════════════
# 3. COORDENADAS DE ONDJIVA (ampliadas)
# ══════════════════════════════════════════════════════════════════════
COORDENADAS_ONDJIVA = {
    "shoprite":                  {"lat": -17.06568, "lon": 15.72992, "nome": "Shoprite Ondjiva",                       "endereco": "Bairro Castilhos, Ondjiva"},
    "angomarte":                 {"lat": -17.0675,  "lon": 15.7180,  "nome": "AngoMarte",                              "endereco": "Bairro Castilhos, Ondjiva"},
    "governo provincial":        {"lat": -17.0665,  "lon": 15.7340,  "nome": "Governo Provincial do Cunene",           "endereco": "Centro da Cidade, Ondjiva"},
    "tribunal":                  {"lat": -17.0665,  "lon": 15.7345,  "nome": "Tribunal Provincial",                    "endereco": "Centro da Cidade, Ondjiva"},
    "agt":                       {"lat": -17.0670,  "lon": 15.7348,  "nome": "AGT — Autoridade Geral Tributária",      "endereco": "Centro da Cidade, Ondjiva"},
    "aeroporto":                 {"lat": -17.0422,  "lon": 15.7511,  "nome": "Aeroporto Provincial 11 de Novembro",    "endereco": "Bairro Kaculuvale, Ondjiva"},
    "mediateca":                 {"lat": -17.0595,  "lon": 15.7450,  "nome": "Mediateca Lucas Damba",                  "endereco": "Bairro Kaculuvale, Ondjiva"},
    "administração provincial":  {"lat": -17.0598,  "lon": 15.7445,  "nome": "Administração Provincial",               "endereco": "Bairro Kaculuvale, Ondjiva"},
    "tribuna":                   {"lat": -17.0663,  "lon": 15.7358,  "nome": "Tribuna",                                "endereco": "Centro da Cidade, Ondjiva"},
    "hospital ekuma":            {"lat": -17.0612,  "lon": 15.7425,  "nome": "Hospital Provincial da Ekuma",           "endereco": "Bairro Ekuma, Ondjiva"},
    "hospital simeone mucunde":  {"lat": -17.0721,  "lon": 15.7284,  "nome": "Hospital Central Simeone Mucunde",       "endereco": "Bairro Naipalala, Ondjiva"},
    "hospital municipal":        {"lat": -17.0660,  "lon": 15.7350,  "nome": "Hospital Municipal de Ondjiva",          "endereco": "Centro da Cidade, Ondjiva"},
    "comando provincial da polícia": {"lat": -17.0662, "lon": 15.7352, "nome": "Comando Provincial da Polícia Nacional", "endereco": "Centro da Cidade, Ondjiva"},
    "justiça provincial":        {"lat": -17.0722,  "lon": 15.7288,  "nome": "Justiça Provincial",                    "endereco": "Bairro Naipalala, Ondjiva"},
    "pitágoras":                 {"lat": -17.0735,  "lon": 15.7255,  "nome": "Colégio Pitágoras",                     "endereco": "Bairro Naipalala, Ondjiva"},
    # NOVO — mercado central
    "mercado ombandja":          {"lat": -17.0668,  "lon": 15.7330,  "nome": "Mercado Central Ombandja",              "endereco": "Centro da Cidade, Ondjiva"},
    # NOVO — campo de futebol
    "campo provincial":          {"lat": -17.0650,  "lon": 15.7310,  "nome": "Campo Provincial 11 de Novembro",       "endereco": "Centro da Cidade, Ondjiva"},
}

# ══════════════════════════════════════════════════════════════════════
# 4. PALAVRAS-CHAVE EM KWANYAMA → mapeadas para tópicos portugueses
#    (H2 do TFC: adaptar às especificidades linguísticas e culturais)
# ══════════════════════════════════════════════════════════════════════
KWANYAMA_MAP = {
    "oshikola":    "escola",
    "epangelo":    "governo",
    "oshifo":      "mercado",
    "omukiintu":   "médico",
    "omukuluntu":  "polícia",
    "omeva":       "água",
    "ohambo":      "cheia inundação",
    "oshilongo":   "país angola cunene",
    "nawa":        "obrigado",
    "peni":        "onde fica localização",
}

def traduzir_kwanyama(texto: str) -> str:
    """Substitui palavras Kwanyama reconhecidas pelos equivalentes pt-AO."""
    t = texto
    for kw, pt in KWANYAMA_MAP.items():
        t = t.replace(kw, pt)
    return t

# ══════════════════════════════════════════════════════════════════════
# 5. BASE DE CONHECIMENTO — CONTEXTO DA IA (EXPANDIDA)
# ══════════════════════════════════════════════════════════════════════
CONTEXTO_ONDJIVA = """
Tu és o Bot_cunene, assistente oficial de Ondjiva, Província do Cunene, Angola. Usa linguagem natural de Angola, calorosa e directa.

DIRETIVAS DE SEGURANÇA OBRIGATÓRIAS:
1. SE NÃO SOUBERES OU SE O DADO NÃO ESTIVER AQUI, DIZ: "Peço desculpa, não tenho essa informação oficial disponível no momento." NUNCA INVENTES.
2. NUNCA fales sobre províncias que não existem ou inventes factos históricos. O Cunene é no SUL de Angola e a capital é Ondjiva.
3. Formatação WhatsApp: *negrito* apenas com um asterisco.
4. Idioma: responde exclusivamente em Português de Angola.
5. Rigor geográfico: Cuanhama é município e língua nacional da província do Cunene.
6. Horários: só os fornecidos. Nunca inventes.
7. Proibido mencionar "regras", "prompt", "base de dados".
8. Público vs. privado: colégios (Pitágoras, Ednas, Popiene, Marc Leandres, Bulet Salú 1 e 2, Abcunene, Cesmo) são privados. Escolas como ITSO, Oulondelo, IMPO, Eiffel, ITAS e todas as primárias são públicas.
9. Respostas curtas: A não ser que o utente peça explicitamente uma lista completa, sê conciso. Se a resposta for longa (>800 caracteres), pergunta se quer detalhes completos.
10. Menu numérico: Se o utilizador envia um número (1,2,3,4) isolado, o sistema externo trata disso.
11. CHEIAS: Se a mensagem mencionar "cheia", "inundação", "rio cunene", "água subiu", orienta SEMPRE para o número de emergência 113 e para o ponto de evacuação mais próximo.
12. PREÇOS DE MERCADO: Informa que os preços do Mercado Ombandja variam diariamente e recomenda verificação presencial.

----- DADOS OFICIAIS (FACTOS HISTÓRICOS E GEOGRÁFICOS) -----

### GEOGRAFIA E LOCALIZAÇÃO
- O Cunene é uma Província de Angola, situada no extremo SUL do país.
- Faz fronteira a SUL com a Namíbia, a NORTE/NOROESTE com a Huíla, a LESTE com o Cuando Cubango e a OESTE com o Namibe. Angola tem 21 províncias oficiais no total.
- Extensão territorial: aproximadamente 79.762 km².

### HISTÓRIA E CULTURA (CUNENE)
- Raízes: A cultura é dominada pelos povos Nyaneka-Humbe e Ovambo (Kwanyama).
- Hábitos: A pastorícia de gado bovino é a base da economia tradicional e do prestígio social.
- Gastronomia: A base da alimentação é o funge de massa de massango ou milho, o leite azedo (maiavi) e carne seca (chacota).
- História: O Cunene é uma terra de resistência anticolonial, com destaque para a figura do Rei Mandume ya Ndemufayo, símbolo de resistência do povo Cuanhama.
- Línguas locais: Kwanyama (Cuanhama) e Nyaneka são as línguas maternas mais faladas.

### CLIMA E CHEIAS (NOVO)
- Clima árido a semi-árido. Estação seca: Março–Outubro. Estação chuvosa: Novembro–Fevereiro.
- As cheias do Rio Cunene são recorrentes. Em episódios graves, contacta: Protecção Civil 118 | Polícia 113 | Bombeiros 115.
- Ponto de evacuação temporária: Campo da Centralidade (Ondjiva).
- Alerta meteorológico: Segue as comunicações do INAMET (Instituto Nacional de Meteorologia e Geofísica de Angola).

### MERCADO AGRÍCOLA (NOVO)
- Mercado Central Ombandja (Centro, Ondjiva): um dos maiores mercados do sul de Angola.
- Produtos típicos: milho, massango, feijão, gado bovino, caprinos, artesanato Kwanyama.
- Preços variam diariamente. Para preços actualizados, visita o mercado ou liga à Administração Municipal: consulta o portal da Administração de Ondjiva.

----- DADOS DOS SERVIÇOS DE ONDJIVA -----

### ADMINISTRAÇÃO PÚBLICA
Horário: Seg‑Qui 08h-15h30, Sex 08h-15h.
Governo Provincial, Tribunal, AGT, Palácio, Polícia (comando) – Centro da Cidade.
Administração Provincial, Mediateca Lucas Damba, Aeroporto – Bairro Kaculuvale.
Comando Municipal, PIC – Castilhos.
Viação, Bombeiros, Polícia Fiscal – Naipalala.
Guarda Fronteira – Kafitu1.
Governadora: Gerdina Didalelwa.

### SAÚDE
Urgências 24h. Consultas externas: Seg‑Sex 08h-15h.
Hospital Ekuma (Ekuma), Hospital Simeone Mucunde (Naipalala), Hospital Municipal (Centro da cidade).
Linha de saúde: MINSA — 080 0200 200 (gratuita).

### ENSINO – ESCOLAS PÚBLICAS (manhã 7:00‑12:30, tarde 13:00‑17:30, noite 18:00‑22:30)
* Faculdades: Rei Luhuna (Muhongo), Mandume (Naipalala).
* Escolas médias públicas:
   - ITSO (Ekuma) – Cursos: Enfermagem Geral, Fisioterapia, Análises Clínicas.
   - Eiffel (Naipalala).
   - Oulondelo (Naipalala) – Ciências Físicas e Biológicas, Económicas e Jurídicas; + 1.º ciclo.
   - IMPO (Naipalala) – Pedagogia: Mate‑Física, Ensino Primário, EMC, Língua Portuguesa.
   - Cesmo (Kaculuvale) – Ciências Físicas e Biológicas, Económicas e Jurídicas.
   - ITAS (Naipalala) – Finanças, Secretariado, Contabilidade, Gestão Empresarial, Recursos Humanos.
* Primárias (todas públicas): várias listadas.
* 1.º ciclo: Cowboy (Castilhos), Ocapale (Kaculuvale), C.E Centralidade, Rei Nande.

### COLÉGIOS (PRIVADOS)
- Colégio Pitágoras (Naipalala): Farmácia, Informática, Eletricidade, Ciências Físicas e Biológicas, Enfermagem Geral, Análises Clínicas.
- Colégio Ednas (Kaculuvale): Ciências Físicas e Biológicas, Económicas e Jurídicas.
- Colégio Popiene (Kaculuvale).
- Colégio Arcanjo (Naipalala): Enfermagem geral, Análises clínicas, Ciências Físicas e Biológicas.
- Colégio Marc Leandres (Kaculuvale): só primário e 1.º ciclo.
- Colégio Bulet Salú 1 (Naipalala) e 2 (Zeca): Ciências Físicas e Biológicas, Económicas e Jurídicas, Ciências Humanas, Eletricidade.
- Colégio Abcunene (Caxila 3): Enfermagem Geral, Análises Clínicas, Informática.

### BANCOS
Horário: Seg‑Sex 08h-15h.
BAI, BFA, BIC (Centro); BCI, BPC, Sol, Económico (Bangula); BPC2, Atlântico (Naipalala).

### COMÉRCIO E LAZER
Shoprite e AngoMarte (Castilhos) abertos todos os dias 08h-20h.
Mercado Ombandja (Centro) – dias úteis e fim-de-semana, desde o amanhecer.
Campo Provincial 11 de Novembro e Campo da Centralidade para desporto.

### DIVISÃO ADMINISTRATIVA (14 MUNICÍPIOS OFICIAIS DO CUNENE)
1. Cahama – comunas: Cahama, Otchinjau. Administrador: José Mário Katiti.
2. Cuanhama – comunas: Ondjiva, Môngua. Administrador: José Felisberto Kalomo.
3. Curoca – comunas: Oncócua, Chitado. Administrador: António Dos Santos Luepo.
4. Cuvelai – comunas: Mupa, Mukolongodjo, Calonga, Cubati. Administrador: Germano Baptista Nambalo.
5. Namacunde – comunas: Namacunde, Chiede. Administrador: Cristuiana Nameomunu.
6. Ombadja – comunas: Humpe, Mucope, Naulila, Ombala yo Mungu, Xangongo. Administrador: Hilario Sikalepo.
7. Chiéde | 8. Nehone – comunas: Nehone, Evale. | 9. Humbe – comunas: Mucope, Humbe.
10. Mupa | 11. Naulila | 12. Chitado | 13. Cafima | 14. Chissuata.
"""

# ══════════════════════════════════════════════════════════════════════
# 6. UTILITÁRIOS GERAIS
# ══════════════════════════════════════════════════════════════════════
def mascarar_telefone(tel: str) -> str:
    """Pseudonimização: guarda apenas os últimos 4 dígitos nos logs."""
    return "****" + tel[-4:] if len(tel) >= 4 else "****"

def verificar_rate_limit(telefone: str) -> bool:
    """Devolve True se o utilizador ainda está dentro do limite de mensagens/min."""
    agora = time.monotonic()
    fila = RATE_LIMIT_STORE[telefone]
    # Remove entradas com mais de 60 segundos
    while fila and agora - fila[0] > 60:
        fila.popleft()
    if len(fila) >= MAX_MSG_POR_MINUTO:
        return False
    fila.append(agora)
    return True

# ══════════════════════════════════════════════════════════════════════
# 7. ENVIO DE MENSAGENS VIA WHATSAPP API
# ══════════════════════════════════════════════════════════════════════
_WA_URL = lambda: f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_ID}/messages"
_WA_HEADERS = lambda: {
    "Authorization": f"Bearer {WHATSAPP_TOKEN}",
    "Content-Type": "application/json"
}

def _post_whatsapp(payload: dict) -> None:
    """Envia um payload para a API do WhatsApp com tratamento de erros."""
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID:
        return
    try:
        r = requests.post(_WA_URL(), headers=_WA_HEADERS(), json=payload, timeout=10)
        if r.status_code not in (200, 201):
            print(f"[WA_API] HTTP {r.status_code}: {r.text[:200]}")
    except requests.RequestException as e:
        print(f"[WA_API] Erro de rede: {e}")


def enviar_mensagem_whatsapp(telefone: str, texto: str) -> None:
    """Envia mensagem de texto simples. Parte automaticamente se > 3800 chars."""
    texto = texto.replace("**", "*")
    ULTIMA_MSG_BOT[telefone] = texto
    if len(texto) > 3800:
        _enviar_partida(telefone, texto)
        return
    _post_whatsapp({
        "messaging_product": "whatsapp",
        "to": telefone,
        "type": "text",
        "text": {"body": texto}
    })


def _enviar_partida(telefone: str, texto: str) -> None:
    """Divide texto longo em blocos e envia sequencialmente."""
    max_len = 3800
    while len(texto) > max_len:
        corte = texto.rfind(" ", 0, max_len) or max_len
        enviar_mensagem_whatsapp(telefone, texto[:corte].strip())
        texto = texto[corte:].strip()
        time.sleep(0.5)
    if texto:
        enviar_mensagem_whatsapp(telefone, texto)


def enviar_localizacao_whatsapp(telefone: str, lat: float, lon: float,
                                 nome: str, endereco: str) -> None:
    """Envia pin de localização pelo WhatsApp."""
    _post_whatsapp({
        "messaging_product": "whatsapp",
        "to": telefone,
        "type": "location",
        "location": {
            "latitude": lat,
            "longitude": lon,
            "name": nome,
            "address": endereco
        }
    })


def enviar_botoes_whatsapp(telefone: str, corpo: str,
                            botoes: list[dict]) -> None:
    """
    Envia mensagem com botões interactivos (até 3 botões).
    botoes = [{"id": "btn_1", "title": "Texto botão"}, …]
    NOVO — usa Interactive Reply Buttons da WhatsApp Cloud API.
    """
    payload_botoes = [
        {"type": "reply", "reply": {"id": b["id"], "title": b["title"][:20]}}
        for b in botoes[:3]
    ]
    _post_whatsapp({
        "messaging_product": "whatsapp",
        "to": telefone,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": corpo},
            "action": {"buttons": payload_botoes}
        }
    })

# ══════════════════════════════════════════════════════════════════════
# 8. BASE DE DADOS
# ══════════════════════════════════════════════════════════════════════
def guardar_reportagem_bd(telefone: str, relato: str) -> bool:
    """
    Persiste a reportagem na base de dados PostgreSQL.
    O número de telefone é guardado mascarado (pseudonimização — Lei 7/17).
    """
    if not DATABASE_URL:
        print("[BD] DATABASE_URL não configurada; reportagem não persistida.")
        return False
    tel_mascarado = mascarar_telefone(telefone)
    try:
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS reportagens (
                        id             SERIAL PRIMARY KEY,
                        telefone       VARCHAR(20),
                        relato         TEXT,
                        data_registro  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cur.execute(
                    "INSERT INTO reportagens (telefone, relato) VALUES (%s, %s)",
                    (tel_mascarado, relato)
                )
                conn.commit()
        return True
    except psycopg2.Error as e:
        print(f"[BD] Erro ao guardar reportagem: {e}")
        return False

# ══════════════════════════════════════════════════════════════════════
# 9. LIMPEZA PERIÓDICA DE MEMÓRIA (thread de fundo)
# ══════════════════════════════════════════════════════════════════════
def _limpar_memoria_loop() -> None:
    """Remove sessões inactivas há mais de 1 hora."""
    while True:
        time.sleep(600)
        agora = datetime.utcnow()
        expirados = [
            tel for tel, ts in MEMORIA_TIMESTAMPS.items()
            if (agora - ts).total_seconds() > 3600
        ]
        for tel in expirados:
            for d in (MEMORIA_CONVERSAS, MEMORIA_TIMESTAMPS,
                      ESTADO_REPORTAGEM, ESTADO_NAVEGACAO,
                      ESTADO_ROTA, ULTIMA_MSG_BOT, RATE_LIMIT_STORE):
                d.pop(tel, None)
        if expirados:
            print(f"[MEMÓRIA] {len(expirados)} sessão(ões) expirada(s) removida(s).")

threading.Thread(target=_limpar_memoria_loop, daemon=True, name="LimpezaMemória").start()

# ══════════════════════════════════════════════════════════════════════
# 10. RESPOSTAS RÁPIDAS DO SUB-MENU DE INFORMAÇÕES
# ══════════════════════════════════════════════════════════════════════
_RESPOSTAS_INFO = {
    "A": ("Horário Administração Pública: Seg‑Qui 08h‑15h30, Sex 08h‑15h.\n"
          "Repartições: Centro (Governo, Tribunal, AGT), Kaculuvale (Adm. Provincial, Mediateca), "
          "Castilhos (PIC), Naipalala (Viação, Bombeiros). Precisas de algo específico?"),
    "B": ("🏥 *Saúde em Ondjiva*\n"
          "Urgências 24h. Consultas externas Seg‑Sex 08h‑15h.\n"
          "• Hospital Ekuma (Bairro Ekuma)\n"
          "• Hospital Simeone Mucunde (Naipalala)\n"
          "• Hospital Municipal (Centro)\n"
          "Linha MINSA gratuita: *080 0200 200*. Quer mais detalhes?"),
    "C": ("📚 *Ensino em Ondjiva*\n"
          "Escolas públicas: ITSO (saúde), Oulondelo, IMPO (pedagogia), Cesmo, ITAS, Eiffel, "
          "várias primárias.\nColégios privados: Pitágoras, Ednas, Popiene, Marc Leandres, "
          "Bulet Salú 1/2, Abcunene.\nPosso detalhar cursos de uma escola. Qual te interessa?"),
    "D": ("🏦 *Bancos* — Seg‑Sex 08h‑15h\n"
          "• Centro: BAI, BFA, BIC\n"
          "• Bangula: BCI, BPC, Sol, Económico\n"
          "• Naipalala: BPC2, Atlântico"),
    "E": ("🛒 *Comércio e Lazer*\n"
          "• Shoprite & AngoMarte (Castilhos): todos os dias 08h‑20h\n"
          "• Mercado Ombandja (Centro): todos os dias desde o amanhecer\n"
          "• Desporto: Campo Provincial 11 de Novembro e Campo da Centralidade"),
    "F": ("🗺️ *Divisão Administrativa do Cunene*\n"
          "A província tem *14 municípios*: Cahama, Cuanhama, Curoca, Cuvelai, Namacunde, "
          "Ombadja, Chiéde, Nehone, Humbe, Mupa, Naulila, Chitado, Cafima e Chissuata.\n\n"
          "Escreve *lista completa dos municípios* para ver comunas e administradores."),
    "G": ("🌊 *Cheias e Alertas Meteorológicos*\n"
          "As cheias do Rio Cunene são recorrentes entre Nov–Fev.\n"
          "Em caso de alerta:\n"
          "• Liga: Protecção Civil *118* | Polícia *113* | Bombeiros *115*\n"
          "• Ponto de evacuação: Campo da Centralidade (Ondjiva)\n"
          "• Segue o INAMET para previsões oficiais."),
}

# ══════════════════════════════════════════════════════════════════════
# 11. PROCESSAMENTO PRINCIPAL DE TEXTO
# ══════════════════════════════════════════════════════════════════════
def processar_texto(telefone: str, user_text: str) -> str:
    """
    Recebe a mensagem do utilizador e devolve a resposta do bot.
    Ordem de prioridade:
      1. Rate-limit
      2. Tradução Kwanyama → pt
      3. Emergência directa
      4. Cheias (NOVO)
      5. Máquina de estados: reportagem
      6. Máquina de estados: navegação (menu)
      7. Fallback sub-menu (letras A–G após menu de info)
      8. Activação de menu
      9. Início de reportagem
     10. Rota dinâmica
     11. Localização estática
     12. IA (Groq / LLaMA)
    """
    # ── Rate-limit ────────────────────────────────────────────────────
    if not verificar_rate_limit(telefone):
        return "⚠️ Estás a enviar mensagens muito depressa. Aguarda um momento e tenta novamente."

    MEMORIA_TIMESTAMPS[telefone] = datetime.utcnow()

    # ── Pré-processamento: Kwanyama → pt (H2 do TFC) ─────────────────
    user_text_original = user_text
    user_text = traduzir_kwanyama(user_text)
    texto_baixo = user_text.lower().strip()

    # ── 1. Emergência directa ─────────────────────────────────────────
    if any(p in texto_baixo for p in ["emergencia", "emergência", "socorro", "ajuda urgente"]):
        return ("🚨 *Emergência!*\n"
                "• Polícia: *113*\n"
                "• Bombeiros: *115*\n"
                "• Protecção Civil: *118*\n"
                "Procura um lugar seguro e liga imediatamente! 🆘")

    # ── 2. Cheias / Inundações (NOVO) ────────────────────────────────
    if any(p in texto_baixo for p in ["cheia", "inundação", "inundacao", "rio cunene",
                                       "água subiu", "agua subiu", "ohambo"]):
        return _RESPOSTAS_INFO["G"]

    # ── 3. Máquina de estados: reportagem ────────────────────────────
    if telefone in ESTADO_REPORTAGEM:
        return _processar_estado_reportagem(telefone, user_text)

    # ── 4. Máquina de estados: navegação ─────────────────────────────
    if telefone in ESTADO_NAVEGACAO:
        resultado = _processar_estado_navegacao(telefone, texto_baixo, user_text)
        if resultado is not None:
            return resultado

    # ── 5. Fallback de sub-menu (letras A–G) ─────────────────────────
    ultima = ULTIMA_MSG_BOT.get(telefone, "")
    if ("escolhe a categoria" in ultima or "Informações oficiais" in ultima) \
            and texto_baixo.upper() in _RESPOSTAS_INFO:
        ESTADO_NAVEGACAO.pop(telefone, None)
        return _RESPOSTAS_INFO[texto_baixo.upper()]

    # ── 6. Activação do menu principal ───────────────────────────────
    if texto_baixo in ["menu", "ajuda", "help", "guia", "opções", "opcoes",
                        "inicio", "início", "oi", "olá", "ola"] \
            or "como usar" in texto_baixo:
        ESTADO_NAVEGACAO[telefone] = {"nivel": "menu"}
        return (
            "📋 *Menu Principal — Bot Cunene*\n\n"
            "Escolhe o número:\n"
            "1️⃣ Reportar um problema\n"
            "2️⃣ Localização de locais\n"
            "3️⃣ Informações oficiais\n"
            "4️⃣ Emergências\n"
            "5️⃣ Mercado & preços agrícolas\n"  # NOVO
            "6️⃣ Cheias e alertas\n"            # NOVO
            "\nOu faz uma pergunta directa ao bot. ✨"
        )

    # ── 7. Início de reportagem ───────────────────────────────────────
    if texto_baixo.startswith("reportagem"):
        return _iniciar_reportagem(telefone, user_text)

    # ── 8. Rota dinâmica ─────────────────────────────────────────────
    for chave, dados in COORDENADAS_ONDJIVA.items():
        if chave in texto_baixo and any(p in texto_baixo for p in
                                         ["como chegar", "rota", "caminho", "trajeto"]):
            ESTADO_ROTA[telefone] = dados
            return (f"🗺️ Queres ir para *{dados['nome']}*.\n\n"
                    "📍 Partilha a tua *Localização Actual* aqui no WhatsApp "
                    "(clica no 📎 › Localização) para eu gerar a rota exata.")

    # ── 9. Localização estática ───────────────────────────────────────
    for chave, dados in COORDENADAS_ONDJIVA.items():
        if chave in texto_baixo and any(p in texto_baixo for p in
                                         ["localização", "localizacao", "onde fica",
                                          "onde esta", "mapa", "peni"]):
            enviar_localizacao_whatsapp(telefone, dados["lat"], dados["lon"],
                                        dados["nome"], dados["endereco"])
            return (f"📍 *{dados['nome']}*\n{dados['endereco']}\n\n"
                    "💡 Clica no Pin acima e depois em *'Como chegar'* para a rota.")

    # ── 10. IA (LLaMA via Groq) ───────────────────────────────────────
    return _resposta_ia(telefone, user_text)


# ──────────────────────────────────────────────────────────────────────
# Auxiliares do processador principal
# ──────────────────────────────────────────────────────────────────────
def _processar_estado_reportagem(telefone: str, user_text: str) -> str:
    dados = ESTADO_REPORTAGEM[telefone]
    if (datetime.utcnow() - dados["inicio"]).total_seconds() > TIMEOUT_REPORTAGEM:
        ESTADO_REPORTAGEM.pop(telefone)
        return "⏳ Reportagem cancelada por inactividade. Começa de novo com *Reportagem …*"
    if dados["passo"] == 1:
        dados["tempo"] = user_text.strip()
        dados["passo"] = 2
        return "Obrigado. *O que causou essa situação?* (Responde 'Não sei' se não souberes.)"
    elif dados["passo"] == 2:
        dados["causa"] = user_text.strip()
        relato = (f"PROBLEMA: {dados['problema']} | "
                  f"DURAÇÃO: {dados['tempo']} | "
                  f"CAUSA: {dados['causa']}")
        ok = guardar_reportagem_bd(telefone, relato)
        ESTADO_REPORTAGEM.pop(telefone)
        estado_bd = "✅ registada na base de dados." if ok else "⚠️ (base de dados indisponível, contacta as autoridades directamente)"
        return (f"✅ *Ocorrência enviada!* {estado_bd}\n\n"
                f"• *Problema:* {dados['problema']}\n"
                f"• *Duração:* {dados['tempo']}\n"
                f"• *Causa:* {dados['causa']}\n\n"
                "Obrigado por ajudares Ondjiva! Escreve *menu* para mais opções.")
    return ""


def _processar_estado_navegacao(telefone: str, texto_baixo: str,
                                  user_text: str) -> str | None:
    """Devolve resposta ou None (para continuar o fluxo normal)."""
    estado = ESTADO_NAVEGACAO[telefone]
    nivel = estado.get("nivel", "menu")

    if nivel == "menu":
        if texto_baixo == "1":
            ESTADO_NAVEGACAO.pop(telefone)
            return "Escreve *Reportagem* seguido do problema.\nEx: *Reportagem falta de água no Kafitu*"
        elif texto_baixo == "2":
            ESTADO_NAVEGACAO[telefone]["nivel"] = "localizacao_pedido"
            return "📍 Diz o nome do local (ex: Shoprite, Hospital Ekuma, Mediateca, Mercado Ombandja…)"
        elif texto_baixo == "3":
            ESTADO_NAVEGACAO[telefone]["nivel"] = "info_submenu"
            return (
                "📋 *Informações Oficiais — escolhe a categoria:*\n\n"
                "A — Administração Pública\n"
                "B — Saúde\n"
                "C — Ensino (escolas e cursos)\n"
                "D — Bancos\n"
                "E — Comércio e Lazer\n"
                "F — Divisão Administrativa\n"
                "G — Cheias e Alertas Meteorológicos"  # NOVO
            )
        elif texto_baixo == "4":
            ESTADO_NAVEGACAO.pop(telefone)
            return ("🚨 *Emergências*\n"
                    "• Polícia: *113*\n"
                    "• Bombeiros: *115*\n"
                    "• Protecção Civil: *118*\n"
                    "Procura um lugar seguro imediatamente!")
        elif texto_baixo == "5":   # NOVO — Mercado
            ESTADO_NAVEGACAO.pop(telefone)
            return (
                "🛒 *Mercado Agrícola — Ombandja (Ondjiva)*\n\n"
                "Produtos típicos: milho, massango, feijão, carne, gado, artesanato Kwanyama.\n"
                "Os preços variam diariamente. Para valores actualizados, visita o mercado "
                "ou contacta a Administração Municipal.\n\n"
                "📍 Quer a localização do Mercado? Escreve: *localização mercado ombandja*"
            )
        elif texto_baixo == "6":   # NOVO — Cheias
            ESTADO_NAVEGACAO.pop(telefone)
            return _RESPOSTAS_INFO["G"]
        else:
            ESTADO_NAVEGACAO.pop(telefone)
            return None   # continua fluxo normal (IA)

    elif nivel == "info_submenu":
        opcao = texto_baixo.upper().strip()
        if opcao in _RESPOSTAS_INFO:
            ESTADO_NAVEGACAO.pop(telefone)
            return _RESPOSTAS_INFO[opcao]
        else:
            ESTADO_NAVEGACAO.pop(telefone)
            return None

    elif nivel == "localizacao_pedido":
        local = texto_baixo
        ESTADO_NAVEGACAO.pop(telefone)
        for chave, dados in COORDENADAS_ONDJIVA.items():
            if chave in local:
                enviar_localizacao_whatsapp(telefone, dados["lat"], dados["lon"],
                                            dados["nome"], dados["endereco"])
                return (f"📍 *{dados['nome']}*\n{dados['endereco']}\n\n"
                        "💡 Clica no Pin e depois em *'Como chegar'* para a rota.")
        return "❌ Local não encontrado. Tenta: Shoprite, Hospital Ekuma, Mediateca, Mercado Ombandja…"

    return None


def _iniciar_reportagem(telefone: str, user_text: str) -> str:
    problema = user_text.strip()[10:].strip()
    if not problema:
        return "Escreve *Reportagem* seguido do problema.\nEx: *Reportagem falta de água no Kafitu*"
    ESTADO_REPORTAGEM[telefone] = {
        "passo":    1,
        "problema": problema,
        "tempo":    "",
        "causa":    "",
        "inicio":   datetime.utcnow()
    }
    return f"📝 *Ocorrência registada:* {problema}\n\nHá quanto tempo estão nessa situação?"


def _resposta_ia(telefone: str, user_text: str) -> str:
    """Consulta o modelo LLaMA via Groq e devolve a resposta."""
    if not client:
        return "Serviço temporariamente indisponível. Tenta mais tarde ou escreve *menu*."

    if telefone not in MEMORIA_CONVERSAS:
        MEMORIA_CONVERSAS[telefone] = []

    MEMORIA_CONVERSAS[telefone].append({"role": "user", "content": user_text})
    # Janela de contexto: últimas 16 mensagens
    if len(MEMORIA_CONVERSAS[telefone]) > 16:
        MEMORIA_CONVERSAS[telefone] = MEMORIA_CONVERSAS[telefone][-16:]

    # Relógio e saudação dinâmica
    agora = datetime.utcnow() + timedelta(hours=1)   # UTC+1 Angola
    hora_formatada = agora.strftime("%H:%M")
    data_formatada = agora.strftime("%d/%m/%Y")
    h = agora.hour
    if 5 <= h < 12:
        saudacao, periodo = "Bom dia", "da manhã"
    elif 12 <= h < 18:
        saudacao, periodo = "Boa tarde", "da tarde"
    else:
        saudacao, periodo = "Boa noite", "da noite"

    is_inicio = len(MEMORIA_CONVERSAS[telefone]) <= 2

    regra_relogio = (
        f"\n\n[SISTEMA — RELÓGIO]\nHoje: {data_formatada}, {hora_formatada} {periodo}.\n"
    )
    if is_inicio:
        regra_relogio += f"DIRETIVA STRICT: Começa OBRIGATORIAMENTE com '{saudacao}, '."
    else:
        regra_relogio += "DIRETIVA STRICT: PROIBIDO usar saudações nesta resposta. Vai direto ao assunto."

    mensagens_ia = (
        [{"role": "system", "content": CONTEXTO_ONDJIVA + regra_relogio}]
        + MEMORIA_CONVERSAS[telefone]
    )

    try:
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            temperature=0.0,
            messages=mensagens_ia,
            max_tokens=512
        )
        resposta = resp.choices[0].message.content.strip()
        MEMORIA_CONVERSAS[telefone].append({"role": "assistant", "content": resposta})

        if len(resposta) > 3800:
            _enviar_partida(telefone, resposta)
            return ""   # já enviado
        return resposta

    except Exception as e:
        print(f"[IA] Erro: {e}")
        return ("Peço desculpa, estou com uma dificuldade técnica. Tenta mais tarde.\n"
                "Se for urgente: Polícia *113* | Bombeiros *115*")

# ══════════════════════════════════════════════════════════════════════
# 12. PROCESSAR LOCALIZAÇÃO PARTILHADA PELO UTILIZADOR
# ══════════════════════════════════════════════════════════════════════
def processar_localizacao(telefone: str, lat: float, lon: float) -> str:
    if telefone in ESTADO_ROTA:
        destino = ESTADO_ROTA.pop(telefone)
        link = (f"https://www.google.com/maps/dir/?api=1"
                f"&origin={lat},{lon}"
                f"&destination={destino['lat']},{destino['lon']}"
                f"&travelmode=driving")
        return (f"🚗 *Rota para {destino['nome']}*\n\n"
                f"Clica para abrir o GPS:\n👉 {link}")
    return ("📍 Localização recebida!\n"
            "Escreve *Como chegar a [nome do local]* para gerar uma rota.")

# ══════════════════════════════════════════════════════════════════════
# 13. ROTAS DO FLASK
# ══════════════════════════════════════════════════════════════════════
@app.route("/")
def home():
    return "Bot Cunene v2.0 operacional. ✅", 200


@app.route("/health")
def health():
    """Health-check para Railway, Render, UptimeRobot, etc."""
    return jsonify({
        "status": "ok",
        "version": "2.0",
        "sessoes_ativas": len(MEMORIA_TIMESTAMPS),
        "ia_disponivel": client is not None
    }), 200


@app.route("/webhook", methods=["GET"])
def verificar():
    """Verificação do webhook pela Meta."""
    mode      = request.args.get("hub.mode")
    token     = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Falha na verificação", 403


@app.route("/webhook", methods=["POST"])
def webhook():
    """Recepção de mensagens da WhatsApp Cloud API."""
    body = request.get_json(silent=True)
    if not body or body.get("object") != "whatsapp_business_account":
        return jsonify({"status": "ignored"}), 200

    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            if "messages" not in value:
                continue

            msg = value["messages"][0]
            tel = msg["from"]

            # Mensagem de texto
            if msg["type"] == "text":
                texto  = msg["text"]["body"]
                print(f"[MSG] {mascarar_telefone(tel)}: {texto[:60]}")
                resposta = processar_texto(tel, texto)
                if resposta:
                    enviar_mensagem_whatsapp(tel, resposta)

            # Resposta a botão interactivo
            elif msg["type"] == "interactive":
                tipo = msg["interactive"].get("type")
                if tipo == "button_reply":
                    btn_id = msg["interactive"]["button_reply"]["id"]
                    print(f"[BTN] {mascarar_telefone(tel)}: {btn_id}")
                    resposta = processar_texto(tel, btn_id)
                    if resposta:
                        enviar_mensagem_whatsapp(tel, resposta)

            # Localização partilhada
            elif msg["type"] == "location":
                lat = msg["location"]["latitude"]
                lon = msg["location"]["longitude"]
                resposta = processar_localizacao(tel, lat, lon)
                if resposta:
                    enviar_mensagem_whatsapp(tel, resposta)

    return jsonify({"status": "ok"}), 200

# ══════════════════════════════════════════════════════════════════════
# 14. GRACEFUL SHUTDOWN (SIGTERM — Railway/Render friendly)
# ══════════════════════════════════════════════════════════════════════
def _handle_sigterm(*_):
    print("[SERVER] SIGTERM recebido — a encerrar graciosamente.")
    sys.exit(0)

signal.signal(signal.SIGTERM, _handle_sigterm)

# ══════════════════════════════════════════════════════════════════════
# 15. PONTO DE ENTRADA
# ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"[SERVER] Bot Cunene v2.0 a iniciar na porta {port}…")
    app.run(host="0.0.0.0", port=port, debug=False)
