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
# COORDENADAS DE ONDJIVA (Lista Completa com Exatidão Atualizada)
# ==========================================
COORDENADAS_ONDJIVA = {
    "shoprite": {"lat": -17.06568, "lon": 15.72992, "nome": "Shoprite Ondjiva", "endereco": "Bairro Castilhos, Ondjiva"},
    "angomarte": {"lat": -17.0675, "lon": 15.7180, "nome": "AngoMarte", "endereco": "Bairro Castilhos, Ondjiva"},
    "governo provincial": {"lat": -17.0665, "lon": 15.7340, "nome": "Governo Provincial do Cunene", "endereco": "Centro da Cidade, Ondjiva"},
    "tribunal": {"lat": -17.0665, "lon": 15.7345, "nome": "Tribunal Provincial", "endereco": "Centro da Cidade, Ondjiva"},
    "agt": {"lat": -17.0670, "lon": 15.7348, "nome": "AGT", "endereco": "Centro da Cidade, Ondjiva"},
    "aeroporto": {"lat": -17.0422, "lon": 15.7511, "nome": "Aeroporto Provincial 11 de Novembro", "endereco": "Bairro Kaculuvale, Ondjiva"},
    "mediateca": {"lat": -17.0595, "lon": 15.7450, "nome": "Mediateca Lucas Damba", "endereco": "Bairro Kaculuvale, Ondjiva"},
    "administração provincial": {"lat": -17.0598, "lon": 15.7445, "nome": "Administração Provincial", "endereco": "Bairro Kaculuvale, Ondjiva"},
    "tribuna": {"lat": -17.0663, "lon": 15.7358, "nome": "Tribuna", "endereco": "Centro da Cidade, Ondjiva"},
    "hospital ekuma": {"lat": -17.0612, "lon": 15.7425, "nome": "Hospital Provincial da Ekuma", "endereco": "Bairro Ekuma, Ondjiva"},
    "hospital simeone mucunde": {"lat": -17.0721, "lon": 15.7284, "nome": "Hospital Central Simeone Mucunde", "endereco": "Bairro Naipalala, Ondjiva"},
    "hospital municipal": {"lat": -17.0660, "lon": 15.7350, "nome": "Hospital Municipal de Ondjiva", "endereco": "Centro da Cidade, Ondjiva"},
    "comando provincial da polícia": {"lat": -17.0662, "lon": 15.7352, "nome": "Comando Provincial da Polícia Nacional", "endereco": "Centro da Cidade, Ondjiva"},
    "justiça provincial": {"lat": -17.0722, "lon": 15.7288, "nome": "Justiça Provincial", "endereco": "Bairro Naipalala, Ondjiva"},
    "pitágoras": {"lat": -17.0735, "lon": 15.7255, "nome": "Colégio Pitágoras", "endereco": "Bairro Naipalala, Ondjiva"},
}



# ==========================================
# 2. BASE DE CONHECIMENTO PARA A IA (FUNDIDA E BLINDADA)
# ==========================================
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
10. Menu numérico: Se o utilizador envia um número (1,2,3,4) isolado, ignora, pois o sistema externo trata disso.

----- DADOS OFICIAIS (FACTOS HISTÓRICOS E GEOGRÁFICOS) -----

### GEOGRAFIA E LOCALIZAÇÃO
- O Cunene é uma Província de Angola, situada no extremo SUL do país.
- Faz fronteira a SUL com a Namíbia e a NORTE/NOROESTE com a Huíla. Angola tem 21 províncias oficiais no total.

### HISTÓRIA E CULTURA (CUNENE)
- Raízes: A cultura é dominada pelos povos Nyaneka-Humbe e Ovambo.
- Hábitos: A pastorícia de gado bovino é a base da economia tradicional e do prestígio social.
- Gastronomia: A base da alimentação é o funge de massa de massango ou milho, o leite azedo (maiavi) e carne seca (chacota).
- História: O Cunene é uma terra de resistência anticolonial, com destaque para a figura do Rei Mandume ya Ndemufayo, símbolo de resistência do povo Cuanhama.

----- DADOS DOS SERVIÇOS DE ONDJIVA -----

### ADMINISTRAÇÃO PÚBLICA
Horário: Seg‑Qui 08h-15h30, Sex 08h-15h.
Governo Provincial, Tribunal, AGT, Palácio, Polícia (comando) – Centro da Cidade.
Administração Provincial, Mediateca, Aeroporto – Bairro Kaculuvale.
Comando Municipal, PIC – Castilhos.
Viação, Bombeiros, Polícia Fiscal – Naipalala.
Guarda Fronteira – Kafitu1.
Governadora: Gerdina Didalelwa.

### SAÚDE
Urgências 24h. Consultas externas: Seg‑Sex 08h-15h.
Hospital Ekuma (Ekuma), Hospital Simeone Mucunde (Naipalala), Hospital Municipal (Centro da cidade).

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
Todos oferecem ensino primário e 1.º ciclo, mais os cursos indicados:
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

### COMÉRCIO
Shoprite e AngoMarte (Castilhos) abertos todos os dias 08h-20h.

### DIVISÃO ADMINISTRATIVA (14 MUNICÍPIOS OFICIAIS DO CUNENE)
1. Cahama – comunas: Cahama, Otchinjau. Administrador: José Mário Katiti.
2. Cuanhama – comunas: Ondjiva, Môngua. Administrador: José Felisberto Kalomo.
3. Curoca – comunas: Oncócua, Chitado. Administrador: António Dos Santos Luepo.
4. Cuvelai – comunas: Mupa, Mukolongodjo, Calonga, Cubati. Administrador: Germano Baptista Nambalo.
5. Namacunde – comunas: Namacunde, Chiede. Administrador: Cristuiana Nameomunu.
6. Ombadja – comunas: Humpe, Mucope, Naulila, Ombala yo Mungu, Xangongo. Administrador: Hilario Sikalepo.
7. Chiéde – sem comunas. Sem administrador.
8. Nehone – comunas: Nehone, Evale. Sem administrador.
9. Humbe – comunas: Mucope, Humbe. Sem administrador.
10. Mupa – sem comunas. Sem administrador.
11. Naulila – sem comunas. Sem administrador.
12. Chitado – sem comunas. Sem administrador.
13. Cafima – sem comunas. Sem administrador.
14. Chissuata – sem comunas. Sem administrador.
"""

# ==========================================
# 3. FUNÇÕES DE ENVIO E BASE DE DADOS
# ==========================================
def enviar_mensagem_whatsapp(telefone_destino, texto):
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID:
        return
    texto = texto.replace("**", "*")
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
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID:
        return
    url = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": telefone_destino,
        "type": "location",
        "location": {
            "latitude": latitude,
            "longitude": longitude,
            "name": nome_local,
            "address": endereco
        }
    }
    requests.post(url, headers=headers, json=payload)

def guardar_reportagem_bd(telefone, relato):
    if not DATABASE_URL:
        return False
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
# 5. PROCESSAMENTO PRINCIPAL
# ==========================================
def processar_texto(telefone_origem, user_text):
    texto_baixo = user_text.lower().strip()
    MEMORIA_TIMESTAMPS[telefone_origem] = datetime.utcnow()

    # Fallback inteligente para sub-menu
    ultima = ULTIMA_MENSAGEM_BOT.get(telefone_origem, "")
    if ("escolhe a categoria" in ultima or "Informações oficiais – escolhe a categoria" in ultima) and texto_baixo.upper() in ["A","B","C","D","E","F"]:
        opcao = texto_baixo.upper()
        ESTADO_NAVEGACAO.pop(telefone_origem, None)
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
            if texto_baixo in ["1", "2", "3", "4"]:
                opcao = texto_baixo
                if opcao == "1":
                    ESTADO_NAVEGACAO.pop(telefone_origem)
                    return "Escreve *Reportagem* seguido do problema (ex: Reportagem falta de água no Kafitu)."
                elif opcao == "2":
                    ESTADO_NAVEGACAO[telefone_origem]["nivel"] = "localizacao_pedido"
                    return "📍 Diz-me o nome do local que queres localizar (ex: Shoprite, Hospital Ekuma, Mediateca…)."
                elif opcao == "3":
                    ESTADO_NAVEGACAO[telefone_origem]["nivel"] = "info_submenu"
                    return (
                        "📋 *Informações oficiais – escolhe a categoria:*\n"
                        "A - Administração Pública\n"
                        "B - Saúde\n"
                        "C - Ensino (escolas e cursos)\n"
                        "D - Bancos\n"
                        "E - Comércio e Lazer\n"
                        "F - Divisão Administrativa"
                    )
                elif opcao == "4":
                    ESTADO_NAVEGACAO.pop(telefone_origem)
                    return "🚨 *Emergências:* Polícia 113, Bombeiros 115. Procura um local seguro."
            else:
                ESTADO_NAVEGACAO.pop(telefone_origem)

        elif nivel == "info_submenu":
            opcao = texto_baixo.upper().strip()
            categorias = {"A": "adm", "B": "saude", "C": "ensino", "D": "bancos", "E": "comercio", "F": "divisao"}
            if opcao in categorias:
                ESTADO_NAVEGACAO.pop(telefone_origem)
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
                    return "Bancos Seg‑Sex 08h‑15h. BAI, BFA, BIC no Centro da cidade; BCI, BPC, Sol, Económico em Bangula; BPC2 e Atlântico em Naipalala."
                elif opcao == "E":
                    return "Shoprite e AngoMarte (Castilhos) abertos todos os dias 08h‑20h. Campo Provincial 11 de novembro e da Campo da Centralidade para desporto."
                elif opcao == "F":
                    return (
                        "A província do Cunene é formada por *14 municípios*:\n"
                        "Cahama, Cuanhama, Curoca, Cuvelai, Namacunde, Ombadja, Chiéde, Nehone, Humbe, Mupa, Naulila, Chitado, Cafima, Chissuata.\n\n"
                        "Se quiseres a lista completa com comunas e administradores, escreve: *lista completa dos municípios*."
                    )
            else:
                ESTADO_NAVEGACAO.pop(telefone_origem)

        elif nivel == "localizacao_pedido":
            local_desejado = texto_baixo
            ESTADO_NAVEGACAO.pop(telefone_origem)
            for chave, dados in COORDENADAS_ONDJIVA.items():
                if chave in local_desejado:
                    enviar_localizacao_whatsapp(telefone_origem, dados["lat"], dados["lon"], dados["nome"], dados["endereco"])
                    return (f"📍 *{dados['nome']}*\n"
                            f"{dados['endereco']}\n\n"
                            f"💡 *Dica:* Clica no Pin da localização acima e depois no botão *'Como chegar'* no teu telemóvel para veres a rota exata a partir de onde estás.")
            return "Não encontrei esse local. Tenta novamente com o nome correcto (ex: Shoprite, Hospital Ekuma)."

    # --- EMERGÊNCIA DIRECTA ---
    if any(p in texto_baixo for p in ["emergencia", "emergência", "socorro"]):
        return "🚨 *Emergência:* Polícia 113 | Bombeiros 115. Se estiveres em perigo, abriga-se em um lugar seguro e ligue para os serviços de emergência🚨🆘!"

    # --- ACTIVAÇÃO DO MENU ---
    if texto_baixo in ["menu", "ajuda", "help", "guia", "opções", "opcoes"] or "como usar" in texto_baixo:
        ESTADO_NAVEGACAO[telefone_origem] = {"nivel": "menu"}
        return (
            "📋 *Menu Principal*\n\n"
            "Escolhe o número:\n"
            "1️⃣ Reportar um problema\n"
            "2️⃣ Localização de locais\n"
            "3️⃣ Informações oficiais\n"
            "4️⃣ Emergências\n\n"
            "Responde apenas com o número."
            "Obs: Ou podes fazer perguntas abertas com o bot.✨"
        )

    # --- REPORTAGEM ---
    if texto_baixo.startswith("reportagem"):
        problema = user_text.strip()[10:].strip()
        if not problema:
            return "Escreve *Reportagem* seguido do problema (ex: Reportagem falta de água no Kafitu)."
        ESTADO_REPORTAGEM[telefone_origem] = {
            'passo': 1,
            'problema': problema,
            'tempo': '',
            'causa': '',
            'inicio': datetime.utcnow()
        }
        return f"📝 *Ocorrência registada:* {problema}\nHá quanto tempo estão nessa situação?"

    # --- MÁQUINA DE ESTADOS DA REPORTAGEM ---
    if telefone_origem in ESTADO_REPORTAGEM:
        dados = ESTADO_REPORTAGEM[telefone_origem]
        if (datetime.utcnow() - dados['inicio']).total_seconds() > 900:
            ESTADO_REPORTAGEM.pop(telefone_origem)
            return "⏳ A tua reportagem foi cancelada por inatividade. Começa de novo com *Reportagem …*."
        if dados['passo'] == 1:
            dados['tempo'] = user_text.strip()
            dados['passo'] = 2
            return "Obrigado. Agora diz-me: *O que causou essa situação?* (responde 'Não sei' se não souberes)."
        elif dados['passo'] == 2:
            dados['causa'] = user_text.strip()
            relato = f"PROBLEMA: {dados['problema']} | DURAÇÃO: {dados['tempo']} | CAUSA: {dados['causa']}"
            guardar_reportagem_bd(telefone_origem, relato)
            ESTADO_REPORTAGEM.pop(telefone_origem)
            return (
                "✅ *Ocorrência enviada com sucesso!*\n"
                f"• {dados['problema']}\n"
                f"• Duração: {dados['tempo']}\n"
                f"• Causa: {dados['causa']}\n\n"
                "Obrigado por ajudares Ondjiva! Escreve *menu* para outras opções."
            )

    # --- LOCALIZAÇÃO DIRECTA ---
    for chave, dados in COORDENADAS_ONDJIVA.items():
        if chave in texto_baixo and any(p in texto_baixo for p in ["localização", "localizacao", "onde fica", "onde esta", "mapa", "rota"]):
            enviar_localizacao_whatsapp(telefone_origem, dados["lat"], dados["lon"], dados["nome"], dados["endereco"])
            return (f"📍 *{dados['nome']}*\n"
                    f"{dados['endereco']}\n\n"
                    f"💡 *Dica:* Clica no Pin da localização acima e depois no botão *'Como chegar'* no teu telemóvel para veres a rota exata a partir de onde estás.")

    # --- IA ---
    try:
        if not client:
            return "Serviço temporariamente indisponível. Tenta mais tarde."

        if telefone_origem not in MEMORIA_CONVERSAS:
            MEMORIA_CONVERSAS[telefone_origem] = []

        MEMORIA_CONVERSAS[telefone_origem].append({"role": "user", "content": user_text})
        if len(MEMORIA_CONVERSAS[telefone_origem]) > 16:
            MEMORIA_CONVERSAS[telefone_origem] = MEMORIA_CONVERSAS[telefone_origem][-16:]

        agora = datetime.utcnow() + timedelta(hours=1)
        hora_formatada = agora.strftime("%H:%M")
        data_formatada = agora.strftime("%d/%m/%Y")
        hora_atual = agora.hour
        
        if 5 <= hora_atual < 12:
            saudacao = "Bom dia"
            periodo = "da manhã"
        elif 12 <= hora_atual < 18:
            saudacao = "Boa tarde"
            periodo = "da tarde"
        else:
            saudacao = "Boa noite"
            periodo = "da noite"

        is_inicio_conversa = len(MEMORIA_CONVERSAS[telefone_origem]) <= 2

        regra_relogio = f"\n\n[SISTEMA - RELÓGIO]\nHoje: {data_formatada}, {hora_formatada} {periodo}.\n"
        
        if is_inicio_conversa:
            regra_relogio += f"DIRETIVA STRICT: Começa a tua resposta OBRIGATORIAMENTE com '{saudacao}, '."
        else:
            regra_relogio += "DIRETIVA STRICT: É ESTRITAMENTE PROIBIDO usar saudações (Bom dia/Boa tarde/Boa noite) nesta resposta. Vai direto ao assunto e responde à pergunta."

        contexto = CONTEXTO_ONDJIVA + regra_relogio
        mensagens_ia = [{"role": "system", "content": contexto}] + MEMORIA_CONVERSAS[telefone_origem]

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            temperature=0.0,
            messages=mensagens_ia
        )
        resposta_ia = response.choices[0].message.content.strip()
        MEMORIA_CONVERSAS[telefone_origem].append({"role": "assistant", "content": resposta_ia})

        if len(resposta_ia) > 3800:
            enviar_mensagens_partidas(telefone_origem, resposta_ia)
            return ""  # já enviado
        return resposta_ia

    except Exception as e:
        print(f"Erro IA: {e}")
        return "Peço desculpa, estou com uma dificuldade técnica. Tenta mais tarde. Se for urgente, liga 113 ou 115."

# ==========================================
# 6. ROTAS DO FLASK
# ==========================================
@app.route('/')
def home():
    return "Bot Cunene operacional.", 200

@app.route('/webhook', methods=['GET'])
def verificar():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode and token and mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Falha na verificação", 403

@app.route('/webhook', methods=['POST'])
def webhook():
    body = request.get_json()
    if body.get("object"):
        entry = body["entry"][0]
        if "changes" in entry:
            value = entry["changes"][0]["value"]
            if "messages" in value:
                msg = value["messages"][0]
                if msg["type"] == "text":
                    tel = msg["from"]
                    texto = msg["text"]["body"]
                    resposta = processar_texto(tel, texto)
                    if resposta:
                        enviar_mensagem_whatsapp(tel, resposta)
    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
