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
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "cunene2026")
DATABASE_URL = os.environ.get("DATABASE_URL")

client = None
if GROQ_API_KEY:
    base_url = os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    client = OpenAI(api_key=GROQ_API_KEY, base_url=base_url)

app = Flask(__name__)

# Estruturas de memória
MEMORIA_CONVERSAS = {}
MEMORIA_TIMESTAMPS = {}
ESTADO_REPORTAGEM = {}
ESTADO_NAVEGACAO = {}
ESTADO_ROTA = {}
ULTIMA_MENSAGEM_BOT = {}

# ==========================================
# COORDENADAS DE ONDJIVA
# ==========================================
COORDENADAS_ONDJIVA = {
    "shoprite": {"lat": -17.06568, "lon": 15.72992, "nome": "Shoprite Ondjiva", "endereco": "Bairro Castilhos, Ondjiva"},
    "angomarte": {"lat": -17.0675, "lon": 15.7180, "nome": "AngoMarte", "endereco": "Bairro Castilhos, Ondjiva"},
    "governo provincial": {"lat": -17.0665, "lon": 15.7340, "nome": "Governo Provincial do Cunene", "endereco": "Bairro Bangula, Ondjiva"},
    "tribunal": {"lat": -17.0665, "lon": 15.7345, "nome": "Tribunal Provincial", "endereco": "Bairro Bangula, Ondjiva"},
    "agt": {"lat": -17.0670, "lon": 15.7348, "nome": "AGT", "endereco": "Bairro Bangula, Ondjiva"},
    "aeroporto": {"lat": -17.0422, "lon": 15.7511, "nome": "Aeroporto Provincial 11 de Novembro", "endereco": "Bairro Kaculuvale, Ondjiva"},
    "mediateca": {"lat": -17.0595, "lon": 15.7450, "nome": "Mediateca Lucas Damba", "endereco": "Bairro Kaculuvale, Ondjiva"},
    "administração provincial": {"lat": -17.0598, "lon": 15.7445, "nome": "Administração Provincial", "endereco": "Bairro Kaculuvale, Ondjiva"},
    "hospital ekuma": {"lat": -17.0612, "lon": 15.7425, "nome": "Hospital Provincial da Ekuma", "endereco": "Bairro Ekuma, Ondjiva"},
    "hospital simeone mucunde": {"lat": -17.0721, "lon": 15.7284, "nome": "Hospital Central Simeone Mucunde", "endereco": "Bairro Naipalala, Ondjiva"},
    "hospital municipal": {"lat": -17.0660, "lon": 15.7350, "nome": "Hospital Municipal de Ondjiva", "endereco": "Bairro Bangula, Ondjiva"},
    "comando provincial da polícia": {"lat": -17.0662, "lon": 15.7352, "nome": "Comando Provincial da Polícia Nacional", "endereco": "Bairro Bangula, Ondjiva"},
    "pitágoras": {"lat": -17.0735, "lon": 15.7255, "nome": "Colégio Pitágoras", "endereco": "Bairro Naipalala, Ondjiva"},
    "praça da lemanha": {"lat": -17.0580, "lon": 15.7430, "nome": "Praça da Lemanha", "endereco": "Bairro Kaculuvale, Ondjiva"},
    "praça do xomucuio": {"lat": -17.0700, "lon": 15.7300, "nome": "Praça do Xomucuio", "endereco": "Ondjiva"},
}

# ==========================================
# BASE DE DADOS - HOSPITAIS
# ==========================================
HOSPITAIS_ONDJIVA = {
    "hospital provincial da ekuma": {
        "nome": "Hospital Provincial da Ekuma",
        "bairro": "Ekuma",
        "tipo": "Provincial",
        "urgencias": "24 horas",
        "consultas": "Segunda a Sexta, 08h às 15h"
    },
    "hospital central simeone mucunde": {
        "nome": "Hospital Central Simeone Mucunde",
        "bairro": "Naipalala",
        "tipo": "Central",
        "urgencias": "24 horas",
        "consultas": "Segunda a Sexta, 08h às 15h"
    },
    "hospital municipal de ondjiva": {
        "nome": "Hospital Municipal de Ondjiva",
        "bairro": "Bangula",
        "tipo": "Municipal",
        "urgencias": "24 horas",
        "consultas": "Segunda a Sexta, 08h às 15h"
    }
}

ALCUNHAS_HOSPITAIS = {
    "ekuma": "hospital provincial da ekuma",
    "simeone mucunde": "hospital central simeone mucunde",
    "hospital central": "hospital central simeone mucunde",
    "hospital municipal": "hospital municipal de ondjiva",
    "hospital do bangula": "hospital municipal de ondjiva",
}

# ==========================================
# BASE DE DADOS - ESCOLAS PÚBLICAS
# ==========================================
ESCOLAS_PUBLICAS = {
    "instituto de saúde de ondjiva": {
        "nome": "Instituto de Saúde de Ondjiva (ISO)",
        "tipo": "Pública",
        "bairro": "Ekuma",
        "nivel": "Médio Técnico",
        "cursos": ["Enfermagem Geral", "Fisioterapia", "Análises Clínicas"],
        "turnos": ["Manhã: 07h-12h30", "Tarde: 13h-18h05", "Noite: 18h-22h30"]
    },
    "eiffel": {
        "nome": "Colégio Eiffel",
        "tipo": "Pública",
        "bairro": "Naipalala",
        "nivel": "Médio",
        "cursos": ["Ciências Físicas e Biológicas"],
        "turnos": ["Manhã: 07h-12h30", "Tarde: 13h-18h05"]
    },
    "complexo escolar oulondelo": {
        "nome": "Complexo Escolar Oulondelo",
        "tipo": "Pública",
        "bairro": "Naipalala",
        "nivel": "Médio + 1º Ciclo",
        "cursos": ["Ciências Físicas e Biológicas", "Ciências Económicas e Jurídicas"],
        "turnos": ["Manhã: 07h-12h30", "Tarde: 13h-18h05"]
    },
    "instituto médio de pedagogia de ondjiva": {
        "nome": "Instituto Médio de Pedagogia de Ondjiva (IMPO)",
        "tipo": "Pública",
        "bairro": "Naipalala",
        "nivel": "Médio Técnico",
        "cursos": ["Matemática e Física", "Ensino Primário", "Educação Moral e Cívica", "Língua Portuguesa", "Bio-Química"],
        "turnos": ["Manhã: 07h-12h30", "Tarde: 13h-18h05", "Noite: 18h-22h30"]
    },
    "complexo escolar cesmo": {
        "nome": "Complexo Escolar CESMO",
        "tipo": "Pública",
        "bairro": "Kaculuvale",
        "nivel": "Médio",
        "cursos": ["Ciências Físicas e Biológicas", "Ciências Económicas e Jurídicas"],
        "turnos": ["Manhã: 07h-12h30", "Tarde: 13h-18h05"]
    },
    "itas": {
        "nome": "Instituto Técnico de Administração e Serviços (ITAS)",
        "tipo": "Pública",
        "bairro": "Naipalala",
        "nivel": "Médio Técnico",
        "cursos": ["Finanças", "Secretariado", "Contabilidade", "Gestão Empresarial", "Recursos Humanos"],
        "turnos": ["Manhã: 07h-12h30", "Tarde: 13h-18h05", "Noite: 18h-22h30"]
    },
}

# ==========================================
# BASE DE DADOS - ESCOLAS PRIVADAS
# ==========================================
ESCOLAS_PRIVADAS = {
    "colégio pitágoras": {
        "nome": "Colégio Pitágoras",
        "tipo": "Privada",
        "bairro": "Naipalala",
        "nivel": "Primário + 1º Ciclo + Médio",
        "cursos": ["Farmácia", "Informática", "Eletricidade", "Ciências Físicas e Biológicas", "Enfermagem Geral", "Análises Clínicas"],
        "turnos": ["Manhã: 07h-12h30", "Tarde: 13h-18h05"]
    },
    "colégio ednas": {
        "nome": "Colégio Ednas",
        "tipo": "Privada",
        "bairro": "Kaculuvale",
        "nivel": "Primário + 1º Ciclo + Médio",
        "cursos": ["Ciências Físicas e Biológicas", "Ciências Económicas e Jurídicas"],
        "turnos": ["Manhã: 07h-12h30", "Tarde: 13h-18h05"]
    },
    "colégio popiene": {
        "nome": "Colégio Popiene",
        "tipo": "Privada",
        "bairro": "Kaculuvale",
        "nivel": "Primário",
        "cursos": [],
        "turnos": ["Manhã: 07h-12h30", "Tarde: 13h-18h05"]
    },
    "colégio arcanjo": {
        "nome": "Colégio Arcanjo",
        "tipo": "Privada",
        "bairro": "Naipalala",
        "nivel": "Primário + 1º Ciclo + Médio",
        "cursos": ["Enfermagem Geral", "Análises Clínicas", "Ciências Físicas e Biológicas"],
        "turnos": ["Manhã: 07h-12h30", "Tarde: 13h-18h05"]
    },
    "colégio marc leandres": {
        "nome": "Colégio Marc Leandres",
        "tipo": "Privada",
        "bairro": "Kaculuvale",
        "nivel": "Primário + 1º Ciclo",
        "cursos": [],
        "turnos": ["Manhã: 07h-12h30", "Tarde: 13h-18h05"]
    },
    "colégio bulet salú 1": {
        "nome": "Colégio Bulet Salú 1",
        "tipo": "Privada",
        "bairro": "Naipalala",
        "nivel": "Primário + 1º Ciclo + Médio",
        "cursos": ["Ciências Físicas e Biológicas", "Ciências Económicas e Jurídicas", "Ciências Humanas", "Eletricidade"],
        "turnos": ["Manhã: 07h-12h30", "Tarde: 13h-18h05"]
    },
    "colégio bulet salú 2": {
        "nome": "Colégio Bulet Salú 2",
        "tipo": "Privada",
        "bairro": "Zeca",
        "nivel": "Primário + 1º Ciclo + Médio",
        "cursos": ["Ciências Físicas e Biológicas", "Ciências Económicas e Jurídicas", "Ciências Humanas", "Eletricidade"],
        "turnos": ["Manhã: 07h-12h30", "Tarde: 13h-18h05"]
    },
    "colégio abcunene": {
        "nome": "Colégio Abcunene",
        "tipo": "Privada",
        "bairro": "Caxila 3",
        "nivel": "Primário + 1º Ciclo + Médio",
        "cursos": ["Enfermagem Geral", "Análises Clínicas", "Informática"],
        "turnos": ["Manhã: 07h-12h30", "Tarde: 13h-18h05"]
    },
}

ESCOLAS_ONDJIVA = {**ESCOLAS_PUBLICAS, **ESCOLAS_PRIVADAS}

ALCUNHAS_ESCOLAS = {
    "iso": "instituto de saúde de ondjiva",
    "instituto de saúde": "instituto de saúde de ondjiva",
    "escola de enfermagem": "instituto de saúde de ondjiva",
    "eiffel": "eiffel",
    "oulondelo": "complexo escolar oulondelo",
    "impo": "instituto médio de pedagogia de ondjiva",
    "pedagogia": "instituto médio de pedagogia de ondjiva",
    "cesmo": "complexo escolar cesmo",
    "itas": "itas",
    "administração e serviços": "itas",
    "pitágoras": "colégio pitágoras",
    "pitagoras": "colégio pitágoras",
    "ednas": "colégio ednas",
    "popiene": "colégio popiene",
    "arcanjo": "colégio arcanjo",
    "marc leandres": "colégio marc leandres",
    "bulet salú 1": "colégio bulet salú 1",
    "bulet salú 2": "colégio bulet salú 2",
    "bulet salu": "colégio bulet salú 1",
    "bulet": "colégio bulet salú 1",
    "abcunene": "colégio abcunene",
    "abc": "colégio abcunene",
}

# ==========================================
# BASE DE DADOS - MERCADOS
# ==========================================
MERCADOS_ONDJIVA = {
    "praça da lemanha": {
        "nome": "Praça da Lemanha",
        "bairro": "Kaculuvale",
        "tipo": "Mercado/Praça",
        "produtos": ["Fuba", "Milho", "Arroz", "Massa", "Frango", "Peixe", "Tomate", "Cebola", "Alho", "Batata", "Feijão", "Óleo", "Sal", "Açúcar"],
        "horario": "Todos os dias, das primeiras horas da manhã até ao final da tarde",
        "localizacao": {"lat": -17.0580, "lon": 15.7430}
    },
    "praça do xomucuio": {
        "nome": "Praça do Xomucuio",
        "bairro": "Ondjiva",
        "tipo": "Mercado/Praça",
        "produtos": ["Fuba", "Milho", "Arroz", "Massa", "Frango", "Peixe", "Tomate", "Cebola", "Alho", "Batata", "Feijão", "Óleo", "Sal", "Açúcar"],
        "horario": "Todos os dias, das primeiras horas da manhã até ao final da tarde",
        "localizacao": {"lat": -17.0700, "lon": 15.7300}
    }
}

# ==========================================
# BASE DE DADOS - CHEIAS E ALERTAS
# ==========================================
CHEIAS_ALERTAS = {
    "estacao_seca": {
        "periodo": "Março a Outubro",
        "descricao": "Clima seco e quente. Época ideal para visitar e aproveitar atividades ao ar livre.",
        "temperatura": "Média diária até 30°C"
    },
    "estacao_chuvosa": {
        "periodo": "Novembro a Fevereiro",
        "descricao": "Chuvas mais frequentes e intensas, trazendo alívio para a seca do verão. As cheias do Rio Cunene são recorrentes nesta época.",
        "temperatura": "Média diária entre 20°C e 25°C"
    },
    "areas_risco": [
        {"zona": "Bairro Kafitu", "risco": "Alto - Zona baixa, propensa a inundações"},
        {"zona": "Bairro Onahumba", "risco": "Médio - Algumas áreas alagadiças"},
        {"zona": "Margens do Rio Cunene", "risco": "Alto - Cheias durante a estação chuvosa"},
        {"zona": "Bairro Castilhos", "risco": "Baixo - Área relativamente elevada"},
    ],
    "contactos_emergencia": {
        "bombeiros": "115",
        "policia": "113",
        "protecao_civil": "Protecção Civil - Atender às instruções oficiais em caso de cheias",
        "governo_provincial": "Governo Provincial do Cunene - Bairro Bangula"
    },
    "recomendacoes": [
        "Esteja atento às previsões meteorológicas",
        "Siga as instruções da Protecção Civil em caso de cheias",
        "Verifique as previsões antes de planear atividades",
        "As condições climáticas podem variar de ano para ano",
        "Evite construir em zonas baixas ou próximas de linhas de água",
        "Tenha um plano de evacuação familiar",
        "Guarde documentos importantes em local seguro e elevado",
        "Não atravesse zonas alagadas a pé ou de carro",
        "Em caso de emergência, procure um local elevado e seguro"
    ]
}

CLIMA_CUNENE = {
    "tipo": "Árido a semi-árido",
    "estacoes": "Duas estações distintas ao longo do ano",
    "nota": "As condições climáticas podem variar de ano para ano. Verifique sempre as previsões meteorológicas antes de planear as suas atividades."
}

# ==========================================
# BASE DE DADOS - MUNICÍPIOS DO CUNENE
# ==========================================
MUNICIPIOS_CUNENE = [
    {
        "numero": 1,
        "nome": "Cahama",
        "comunas": ["Cahama", "Otchinjau"],
        "administrador": "José Mário Katiti"
    },
    {
        "numero": 2,
        "nome": "Cuanhama",
        "comunas": ["Ondjiva", "Môngua"],
        "administrador": "José Felisberto Kalomo"
    },
    {
        "numero": 3,
        "nome": "Curoca",
        "comunas": ["Oncócua", "Chitado"],
        "administrador": "António Dos Santos Luepo"
    },
    {
        "numero": 4,
        "nome": "Cuvelai",
        "comunas": ["Mupa", "Mukolongodjo", "Calonga", "Cubati"],
        "administrador": "Germano Baptista Nambalo"
    },
    {
        "numero": 5,
        "nome": "Namacunde",
        "comunas": ["Namacunde", "Chiede"],
        "administrador": "Cristuiana Nameomunu"
    },
    {
        "numero": 6,
        "nome": "Ombadja",
        "comunas": ["Humpe", "Mucope", "Naulila", "Ombala yo Mungu", "Xangongo"],
        "administrador": "Hilario Sikalepo"
    },
    {
        "numero": 7,
        "nome": "Chiéde",
        "comunas": [],
        "administrador": None
    },
    {
        "numero": 8,
        "nome": "Nehone",
        "comunas": ["Nehone", "Evale"],
        "administrador": None
    },
    {
        "numero": 9,
        "nome": "Humbe",
        "comunas": ["Mucope", "Humbe"],
        "administrador": None
    },
    {
        "numero": 10,
        "nome": "Mupa",
        "comunas": [],
        "administrador": None
    },
    {
        "numero": 11,
        "nome": "Naulila",
        "comunas": [],
        "administrador": None
    },
    {
        "numero": 12,
        "nome": "Chitado",
        "comunas": [],
        "administrador": None
    },
    {
        "numero": 13,
        "nome": "Cafima",
        "comunas": [],
        "administrador": None
    },
    {
        "numero": 14,
        "nome": "Chissuata",
        "comunas": [],
        "administrador": None
    },
]

# ==========================================
# CONTEXTO PARA IA (ENXUTO)
# ==========================================
CONTEXTO_ONDJIVA = """
Tu és o Bot_Cunene, assistente digital oficial da província do Cunene, Angola. Falas Português de Angola, de forma calorosa, direta e curta.

## REGRAS DE OURO (OBRIGATÓRIAS):
1. Se não tiveres a certeza de um dado, diz APENAS: "Não tenho essa informação oficial. Sugiro contactar o Governo Provincial."
2. NUNCA inventes nomes, números, horários ou factos.
3. Usa *apenas um asterisco* para negrito no WhatsApp.
4. Mantém as respostas com menos de 500 caracteres, a menos que o utente peça explicitamente detalhes completos.
5. Se a pergunta for vaga, pede esclarecimento educadamente.
6. NUNCA digas "de acordo com a base de dados", "segundo o prompt", "no contexto fornecido" ou qualquer menção ao teu funcionamento interno.

## DADOS OFICIAIS DE ONDJIVA E CUNENE:

### GEOGRAFIA:
- Cunene: Província no SUL de Angola. Capital: Ondjiva. Fronteira sul com a Namíbia, norte/noroeste com a Huíla.
- Angola tem 21 províncias oficiais.
- Clima: Árido a semi-árido. Estação seca: Março a Outubro (até 30°C). Estação chuvosa: Novembro a Fevereiro (20°C a 25°C).
- 14 municípios: Cahama, Cuanhama, Curoca, Cuvelai, Namacunde, Ombadja, Chiéde, Nehone, Humbe, Mupa, Naulila, Chitado, Cafima, Chissuata.

### CULTURA LOCAL:
- Povos: Nyaneka-Humbe e Ovambo.
- Gastronomia: Funge (massa de massango ou milho), maiavi (leite azedo), chacota (carne seca).
- Figura histórica: Rei Mandume ya Ndemufayo (resistência anticolonial Cuanhama).
- Cuanhama: É um município do Cunene E também a língua local.

### BAIRROS DE ONDJIVA:
Naipalala, Kafitu, Onahumba, Pioneiro Zeca, Castilhos, Kaculuvale, Ekuma, Muhongo, Bangula.

### HORÁRIOS PADRÃO:
- Administração Pública: Segunda a Quinta 08h-15h30 | Sexta 08h-15h.
- Saúde (consultas externas): Segunda a Sexta 08h-15h. Urgências: 24h.
- Bancos: Segunda a Sexta 08h-15h.
- Comércio (Shoprite, AngoMarte): Segunda a Sábado 08h-20h | Domingo 08h-13h30.
- Escolas: Manhã 07h-12h30 | Tarde 13h-18h05 | Noite 18h-22h30.

### HOSPITAIS:
- Hospital Provincial da Ekuma (Bairro Ekuma)
- Hospital Central Simeone Mucunde (Bairro Naipalala)
- Hospital Municipal de Ondjiva (Bairro Bangula)

### ESCOLAS PÚBLICAS:
- ISO (Ekuma): Enfermagem, Fisioterapia, Análises Clínicas
- IMPO (Naipalala): Pedagogia, Mate-Física, Ensino Primário, EMC, Língua Portuguesa, Bio-Química
- ITAS (Naipalala): Finanças, Contabilidade, Gestão, RH, Secretariado
- Oulondelo (Naipalala): Ciências Físicas/Biológicas, Económicas/Jurídicas
- Eiffel (Naipalala): Ciências Físicas e Biológicas
- CESMO (Kaculuvale): Ciências Físicas/Biológicas, Económicas/Jurídicas

### COLÉGIOS PRIVADOS:
- Pitágoras (Naipalala): Farmácia, Informática, Eletricidade, Enfermagem
- Ednas (Kaculuvale): Ciências Físicas/Biológicas, Económicas/Jurídicas
- Popiene (Kaculuvale): Só ensino primário
- Arcanjo (Naipalala): Enfermagem, Análises Clínicas
- Marc Leandres (Kaculuvale): Só primário e 1º ciclo
- Bulet Salú 1 (Naipalala) e 2 (Zeca): Ciências Humanas, Eletricidade
- Abcunene (Caxila 3): Enfermagem, Análises Clínicas, Informática

### ADMINISTRAÇÃO PÚBLICA:
- Governo Provincial, Tribunal, AGT: Bairro Bangula
- Administração Provincial, Mediateca, Aeroporto: Bairro Kaculuvale
- Comando Municipal, SIC: Bairro Castilhos
- Viação, Bombeiros, Polícia Fiscal: Bairro Naipalala
- Guarda Fronteira: Kafitu 1
- Governadora: Gerdina Didalelwa

### MERCADOS:
- Praça da Lemanha (Bairro Kaculuvale)
- Praça do Xomucuio
- Produtos: Fuba, milho, arroz, massa, frango, peixe, tomate, cebola, etc.
- Preços: Variam. Para preços exatos, visitar a praça.

### EMERGÊNCIAS:
- Polícia: 113
- Bombeiros: 115
"""

# ==========================================
# FUNÇÕES DE ENVIO WHATSAPP
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
    try:
        requests.post(url, headers=headers, json=payload, timeout=10)
    except Exception as e:
        print(f"Erro ao enviar WhatsApp: {e}")

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
    try:
        requests.post(url, headers=headers, json=payload, timeout=10)
    except Exception as e:
        print(f"Erro ao enviar localização: {e}")

# ==========================================
# BANCO DE DADOS
# ==========================================
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
# LIMPEZA DE MEMÓRIA
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
            ESTADO_ROTA.pop(tel, None)
            ULTIMA_MENSAGEM_BOT.pop(tel, None)

threading.Thread(target=limpar_memoria_antiga, daemon=True).start()

# ==========================================
# HANDLERS BLINDADOS
# ==========================================

# --- HOSPITAIS ---
def pesquisar_hospital(texto_usuario):
    texto = texto_usuario.lower().strip()
    for chave, dados in HOSPITAIS_ONDJIVA.items():
        if chave in texto:
            return dados
    for alcunha, chave_oficial in ALCUNHAS_HOSPITAIS.items():
        if alcunha in texto:
            return HOSPITAIS_ONDJIVA[chave_oficial]
    if "hospital" in texto:
        if "ekuma" in texto:
            return HOSPITAIS_ONDJIVA["hospital provincial da ekuma"]
        elif "simeone" in texto or "mucunde" in texto or "central" in texto:
            return HOSPITAIS_ONDJIVA["hospital central simeone mucunde"]
        elif "municipal" in texto or "bangula" in texto:
            return HOSPITAIS_ONDJIVA["hospital municipal de ondjiva"]
    return None

def formatar_resposta_hospital(dados_hospital):
    return (
        f"🏥 *{dados_hospital['nome']}*\n"
        f"📍 Bairro: {dados_hospital['bairro']}\n"
        f"🕐 Urgências: {dados_hospital['urgencias']}\n"
        f"🕐 Consultas externas: {dados_hospital['consultas']}\n\n"
        f"Para localização exata, diga *mapa {dados_hospital['nome']}*"
    )

def listar_todos_hospitais():
    resposta = "🏥 *Hospitais em Ondjiva*\n\n"
    for i, (chave, dados) in enumerate(HOSPITAIS_ONDJIVA.items(), 1):
        resposta += (
            f"{i}. *{dados['nome']}*\n"
            f"   📍 Bairro: {dados['bairro']}\n"
            f"   🕐 Consultas: {dados['consultas']}\n\n"
        )
    resposta += "Responda com o número ou nome do hospital para mais detalhes."
    return resposta

def handler_hospitais(texto_baixo):
    if any(p in texto_baixo for p in ["todos", "lista", "quais", "quantos"]):
        return listar_todos_hospitais()
    if "especialidade" in texto_baixo:
        hospital = pesquisar_hospital(texto_baixo)
        if hospital:
            return f"🏥 *{hospital['nome']}*\nPeço desculpa, não tenho a lista exata de especialidades. Sugiro contactar diretamente o hospital ou ligar para o Governo Provincial."
    hospital = pesquisar_hospital(texto_baixo)
    if hospital:
        return formatar_resposta_hospital(hospital)
    if "hospital" in texto_baixo:
        return listar_todos_hospitais()
    return None

# --- ESCOLAS ---
def pesquisar_escola(texto_usuario):
    texto = texto_usuario.lower().strip()
    for chave, dados in ESCOLAS_ONDJIVA.items():
        if chave in texto:
            return dados
    for alcunha, chave_oficial in ALCUNHAS_ESCOLAS.items():
        if alcunha in texto:
            return ESCOLAS_ONDJIVA[chave_oficial]
    bairros = {"ekuma": "Ekuma", "naipalala": "Naipalala", "kaculuvale": "Kaculuvale", "zeca": "Zeca", "caxila": "Caxila 3"}
    for chave_bairro, nome_bairro in bairros.items():
        if chave_bairro in texto:
            for chave, dados in ESCOLAS_ONDJIVA.items():
                if dados['bairro'].lower() == nome_bairro.lower():
                    return dados
    for chave, dados in ESCOLAS_ONDJIVA.items():
        for curso in dados.get('cursos', []):
            if curso.lower() in texto:
                return dados
    return None

def formatar_resposta_escola(dados_escola, completo=False):
    tipo_emoji = "🏫" if dados_escola['tipo'] == "Pública" else "🎓"
    if not completo:
        if dados_escola['cursos']:
            cursos_str = ", ".join(dados_escola['cursos'][:3])
            if len(dados_escola['cursos']) > 3:
                cursos_str += f" e mais {len(dados_escola['cursos']) - 3}"
        else:
            cursos_str = "Apenas ensino primário" if dados_escola['nivel'] == "Primário" else "Ensino Primário e 1º Ciclo"
        return (
            f"{tipo_emoji} *{dados_escola['nome']}*\n"
            f"📚 {dados_escola['tipo']} | {dados_escola['nivel']}\n"
            f"📍 Bairro: {dados_escola['bairro']}\n"
            f"📖 Cursos: {cursos_str}\n"
            f"🕐 {dados_escola['turnos'][0]}\n\n"
            f"Deseja a lista completa de cursos e todos os turnos?"
        )
    else:
        if dados_escola['cursos']:
            cursos_str = "\n".join([f"  • {curso}" for curso in dados_escola['cursos']])
        else:
            cursos_str = "  • Ensino Primário" if "Primário" in dados_escola['nivel'] and "Ciclo" not in dados_escola['nivel'] else "  • Ensino Primário e 1º Ciclo"
        turnos_str = "\n".join([f"  • {turno}" for turno in dados_escola['turnos']])
        return (
            f"{tipo_emoji} *{dados_escola['nome']}*\n"
            f"📚 {dados_escola['tipo']} | {dados_escola['nivel']}\n"
            f"📍 Bairro: {dados_escola['bairro']}\n\n"
            f"📖 *Cursos:*\n{cursos_str}\n\n"
            f"🕐 *Turnos:*\n{turnos_str}\n\n"
            f"Para localização exata, diga *mapa {dados_escola['nome']}*"
        )

def listar_escolas_por_tipo(tipo=None, bairro=None):
    if tipo:
        if tipo == "Pública":
            escolas_filtradas = ESCOLAS_PUBLICAS
        else:
            escolas_filtradas = ESCOLAS_PRIVADAS
    elif bairro:
        escolas_filtradas = {k: v for k, v in ESCOLAS_ONDJIVA.items() if v['bairro'].lower() == bairro.lower()}
    else:
        escolas_filtradas = ESCOLAS_ONDJIVA
    if not escolas_filtradas:
        return "Nenhuma escola encontrada com esse critério."
    if tipo:
        titulo = "🏫 Escolas Públicas" if tipo == "Pública" else "🎓 Colégios Privados"
    elif bairro:
        titulo = f"📚 Escolas no Bairro {bairro}"
    else:
        titulo = "📚 Escolas em Ondjiva"
    resposta = f"{titulo}\n\n"
    for i, (chave, dados) in enumerate(escolas_filtradas.items(), 1):
        if dados['cursos']:
            cursos = ", ".join(dados['cursos'][:3])
            if len(dados['cursos']) > 3:
                cursos += "..."
        else:
            cursos = "Ensino Primário" if dados['nivel'] == "Primário" else "Ensino Primário e 1º Ciclo"
        resposta += (
            f"{i}. *{dados['nome']}*\n"
            f"   📍 {dados['bairro']}\n"
            f"   📖 {cursos}\n\n"
        )
    resposta += "Responda com o número ou nome da escola para mais detalhes."
    return resposta

def handler_escolas(texto_baixo):
    if "pública" in texto_baixo or "publica" in texto_baixo:
        return listar_escolas_por_tipo(tipo="Pública")
    if "privada" in texto_baixo or "particular" in texto_baixo:
        return listar_escolas_por_tipo(tipo="Privada")
    bairros_ondjiva = ["ekuma", "naipalala", "kaculuvale", "castilhos", "caxila", "zeca", "muhongo", "bangula", "kafitu", "onahumba", "pioneiro zeca"]
    for bairro in bairros_ondjiva:
        if bairro in texto_baixo:
            return listar_escolas_por_tipo(bairro=bairro.capitalize())
    if "enfermagem" in texto_baixo:
        return (
            "📖 *Escolas com Enfermagem Geral:*\n"
            "🏫 ISO - Instituto de Saúde (Pública - Ekuma)\n"
            "🎓 Colégio Pitágoras (Privada - Naipalala)\n"
            "🎓 Colégio Arcanjo (Privada - Naipalala)\n"
            "🎓 Colégio Abcunene (Privada - Caxila 3)"
        )
    if "informática" in texto_baixo or "informatica" in texto_baixo:
        return (
            "📖 *Escolas com Informática:*\n"
            "🎓 Colégio Pitágoras (Privada - Naipalala)\n"
            "🎓 Colégio Abcunene (Privada - Caxila 3)"
        )
    if "contabilidade" in texto_baixo or "finanças" in texto_baixo or "financas" in texto_baixo:
        return "📖 *Escola com Finanças/Contabilidade:*\n🏫 ITAS (Pública - Naipalala)"
    escola = pesquisar_escola(texto_baixo)
    if escola:
        if any(p in texto_baixo for p in ["completo", "detalhes", "todos", "tudo"]):
            return formatar_resposta_escola(escola, completo=True)
        return formatar_resposta_escola(escola)
    if any(p in texto_baixo for p in ["escola", "colégio", "colegio", "liceu", "instituto"]):
        return (
            "📚 *Escolas em Ondjiva*\n\n"
            "🏫 *Públicas:* ISO, Eiffel, Oulondelo, IMPO, CESMO, ITAS\n"
            "🎓 *Privadas:* Pitágoras, Ednas, Popiene, Arcanjo, Marc Leandres, Bulet Salú, Abcunene\n\n"
            "Diga 'escolas públicas', 'colégios privados' ou o nome da escola para detalhes."
        )
    return None

def handler_faculdades(texto_baixo):
    if "faculdade" in texto_baixo or "universidade" in texto_baixo or "superior" in texto_baixo:
        if "rei luhuna" in texto_baixo or "muhongo" in texto_baixo:
            return "🏛️ *Faculdade Rei Luhuna*\n📍 Bairro Muhongo\nPara mais informações sobre cursos, contacte diretamente a instituição."
        if "mandume" in texto_baixo or "naipalala" in texto_baixo:
            return "🏛️ *Faculdade Mandume*\n📍 Bairro Naipalala\nPara mais informações sobre cursos, contacte diretamente a instituição."
        return (
            "🏛️ *Faculdades em Ondjiva:*\n"
            "• Faculdade Rei Luhuna (Bairro Muhongo)\n"
            "• Faculdade Mandume (Bairro Naipalala)\n\n"
            "Para mais detalhes sobre cursos, contacte diretamente as instituições."
        )
    return None

# --- MERCADOS ---
def handler_mercados(texto_baixo):
    if any(p in texto_baixo for p in ["preço", "preco", "preços", "precos", "custa", "custo", "valor", "quanto"]):
        mercado_encontrado = None
        for chave, dados in MERCADOS_ONDJIVA.items():
            if chave in texto_baixo:
                mercado_encontrado = dados
                break
        if mercado_encontrado:
            return (
                f"🛒 *{mercado_encontrado['nome']}*\n\n"
                f"💰 Os preços variam conforme a época e a disponibilidade dos produtos.\n\n"
                f"📌 Para preços exatos e atualizados, visite a praça pessoalmente.\n\n"
                f"📍 Bairro: {mercado_encontrado['bairro']}\n"
                f"🕐 {mercado_encontrado['horario']}"
            )
        else:
            return (
                "💰 Os preços nos mercados de Ondjiva variam conforme a época e a disponibilidade dos produtos.\n\n"
                "📌 Para preços exatos e atualizados, visite as praças pessoalmente:\n"
                "• Praça da Lemanha (Bairro Kaculuvale)\n"
                "• Praça do Xomucuio"
            )
    if "lemanha" in texto_baixo:
        mercado = MERCADOS_ONDJIVA["praça da lemanha"]
        produtos_str = ", ".join(mercado["produtos"])
        return (
            f"🛒 *{mercado['nome']}*\n"
            f"📍 Bairro: {mercado['bairro']}\n"
            f"🕐 {mercado['horario']}\n\n"
            f"📦 *Produtos típicos:*\n{produtos_str}\n\n"
            f"Diga 'mapa Praça da Lemanha' para localização.\n"
            f"💰 Para preços, diga 'preços da Lemanha'."
        )
    if "xomucuio" in texto_baixo:
        mercado = MERCADOS_ONDJIVA["praça do xomucuio"]
        produtos_str = ", ".join(mercado["produtos"])
        return (
            f"🛒 *{mercado['nome']}*\n"
            f"📍 Bairro: {mercado['bairro']}\n"
            f"🕐 {mercado['horario']}\n\n"
            f"📦 *Produtos típicos:*\n{produtos_str}\n\n"
            f"Diga 'mapa Praça do Xomucuio' para localização.\n"
            f"💰 Para preços, diga 'preços do Xomucuio'."
        )
    if "produto" in texto_baixo or "vendem" in texto_baixo or "vende" in texto_baixo or "tem" in texto_baixo or "encontra" in texto_baixo:
        for chave, dados in MERCADOS_ONDJIVA.items():
            if chave in texto_baixo:
                produtos_str = ", ".join(dados["produtos"])
                return (
                    f"🛒 *{dados['nome']}*\n\n"
                    f"📦 *Produtos disponíveis:*\n{produtos_str}\n\n"
                    f"💰 Para preços, visite a praça - os valores variam conforme a época."
                )
    if any(p in texto_baixo for p in ["todos", "lista", "quais", "quantos", "mercado", "praça", "praca", "feira"]):
        return (
            "🛒 *Mercados e Praças de Ondjiva*\n\n"
            "1. *Praça da Lemanha*\n"
            "   📍 Bairro Kaculuvale\n\n"
            "2. *Praça do Xomucuio*\n"
            "   📍 Ondjiva\n\n"
            "📦 *Produtos típicos:* Fuba, milho, arroz, massa, frango, peixe, tomate, cebola, alho, batata, feijão, óleo, sal, açúcar e muito mais.\n\n"
            "💰 Para preços atualizados, visite a praça pessoalmente.\n\n"
            "Digite o nome da praça para mais detalhes."
        )
    return None

# --- CHEIAS E ALERTAS ---
def handler_cheias_alertas(texto_baixo):
    if any(p in texto_baixo for p in ["clima", "climático", "climatico"]):
        if "como é" in texto_baixo or "tipo" in texto_baixo or "qual" in texto_baixo:
            return (
                f"🌍 *Clima do Cunene*\n\n"
                f"📋 Tipo: {CLIMA_CUNENE['tipo']}\n"
                f"📅 Estações: {CLIMA_CUNENE['estacoes']}\n\n"
                f"☀️ *Estação seca:* Março a Outubro - Clima seco e quente (até 30°C)\n"
                f"🌧️ *Estação chuvosa:* Novembro a Fevereiro - Chuvas frequentes (20°C a 25°C)\n\n"
                f"⚠️ As cheias do Rio Cunene são recorrentes na estação chuvosa.\n\n"
                f"💡 {CLIMA_CUNENE['nota']}"
            )
    if "seca" in texto_baixo or "seco" in texto_baixo or "verão" in texto_baixo or "verao" in texto_baixo:
        return (
            f"☀️ *Estação Seca no Cunene*\n\n"
            f"📅 Período: {CHEIAS_ALERTAS['estacao_seca']['periodo']}\n"
            f"🌡️ Temperatura: {CHEIAS_ALERTAS['estacao_seca']['temperatura']}\n\n"
            f"📝 {CHEIAS_ALERTAS['estacao_seca']['descricao']}\n\n"
            f"Para saber sobre a estação chuvosa, diga 'estação chuvosa'."
        )
    if any(p in texto_baixo for p in ["chuvosa", "chuva", "chove", "inverno"]):
        return (
            f"🌧️ *Estação Chuvosa no Cunene*\n\n"
            f"📅 Período: {CHEIAS_ALERTAS['estacao_chuvosa']['periodo']}\n"
            f"🌡️ Temperatura: {CHEIAS_ALERTAS['estacao_chuvosa']['temperatura']}\n\n"
            f"📝 {CHEIAS_ALERTAS['estacao_chuvosa']['descricao']}\n\n"
            f"⚠️ As cheias do Rio Cunene são recorrentes nesta época.\n"
            f"🛡️ Esteja atento às previsões e às instruções da Protecção Civil.\n\n"
            f"Para áreas de risco, diga 'áreas de risco'.\n"
            f"Para recomendações, diga 'recomendações cheias'."
        )
    if "temperatura" in texto_baixo or "quente" in texto_baixo or "frio" in texto_baixo or "grau" in texto_baixo:
        return (
            f"🌡️ *Temperaturas no Cunene*\n\n"
            f"☀️ *Estação seca (Março-Outubro):* Média diária até 30°C\n"
            f"🌧️ *Estação chuvosa (Novembro-Fevereiro):* Média diária entre 20°C e 25°C\n\n"
            f"💡 As condições podem variar de ano para ano."
        )
    if any(p in texto_baixo for p in ["área", "area", "zona", "risco", "perigo", "alaga", "inunda"]):
        if "risco" in texto_baixo or "perigo" in texto_baixo or "alaga" in texto_baixo or "inunda" in texto_baixo:
            resposta = "⚠️ *Áreas de Risco - Cheias em Ondjiva*\n\n"
            for area in CHEIAS_ALERTAS['areas_risco']:
                resposta += f"📍 *{area['zona']}*\n   Risco: {area['risco']}\n\n"
            resposta += (
                "🌧️ As cheias do Rio Cunene são recorrentes durante a estação chuvosa (Novembro a Fevereiro).\n\n"
                "🛡️ Siga sempre as instruções da Protecção Civil.\n\n"
                "Para recomendações de segurança, diga 'recomendações cheias'."
            )
            return resposta
    if any(p in texto_baixo for p in ["contacto", "contato", "telefone", "ligar", "emergência", "emergencia", "socorro", "protecção", "proteção", "proteccao"]):
        if any(p in texto_baixo for p in ["cheia", "inundação", "inundacao", "rio"]):
            return (
                "🆘 *Contactos de Emergência - Cheias*\n\n"
                f"🚒 Bombeiros: {CHEIAS_ALERTAS['contactos_emergencia']['bombeiros']}\n"
                f"👮 Polícia: {CHEIAS_ALERTAS['contactos_emergencia']['policia']}\n"
                f"🛡️ {CHEIAS_ALERTAS['contactos_emergencia']['protecao_civil']}\n"
                f"🏛️ {CHEIAS_ALERTAS['contactos_emergencia']['governo_provincial']}\n\n"
                "⚠️ Em caso de cheias, siga as instruções da Protecção Civil e procure um local elevado e seguro."
            )
    if "recomenda" in texto_baixo or "dica" in texto_baixo or "conselho" in texto_baixo or "prevenir" in texto_baixo or "cuidado" in texto_baixo or "fazer" in texto_baixo:
        recomendacoes_str = "\n".join([f"  ✓ {r}" for r in CHEIAS_ALERTAS['recomendacoes']])
        return (
            f"🛡️ *Recomendações de Segurança - Cheias*\n\n{recomendacoes_str}\n\n"
            f"🌧️ Lembre-se: As cheias do Rio Cunene são recorrentes na estação chuvosa (Novembro-Fevereiro).\n"
            f"📋 Verifique sempre as previsões meteorológicas antes de planear atividades."
        )
    if "rio cunene" in texto_baixo or "rio" in texto_baixo:
        return (
            "🌊 *Rio Cunene*\n\n"
            "⚠️ As cheias do Rio Cunene são recorrentes e podem ocorrer durante a estação chuvosa (Novembro a Fevereiro).\n\n"
            "📋 É importante:\n"
            "• Estar atento às previsões meteorológicas\n"
            "• Seguir as instruções da Protecção Civil\n"
            "• Evitar construir próximo das margens\n\n"
            "Para áreas de risco, diga 'áreas de risco'."
        )
    if any(p in texto_baixo for p in ["cheia", "cheias", "inundação", "inundacao", "alerta", "alagamento", "estação", "epoca", "época"]):
        return (
            "⚠️ *Cheias e Clima — Província do Cunene*\n\n"
            f"🌍 Clima: {CLIMA_CUNENE['tipo']}\n\n"
            f"☀️ *Estação seca:* Março a Outubro (até 30°C)\n"
            f"🌧️ *Estação chuvosa:* Novembro a Fevereiro (20°C a 25°C)\n\n"
            "⚠️ As cheias do Rio Cunene são recorrentes na estação chuvosa.\n\n"
            "📋 Pode consultar:\n"
            "• Diga 'estação seca' ou 'estação chuvosa'\n"
            "• Diga 'áreas de risco'\n"
            "• Diga 'recomendações cheias'\n"
            "• Diga 'contactos emergência cheias'\n"
            "• Diga 'temperaturas'\n\n"
            "🆘 Emergência: Bombeiros 115 | Polícia 113\n\n"
            f"💡 {CLIMA_CUNENE['nota']}"
        )
    return None

# --- MUNICÍPIOS ---
def handler_municipios(texto_baixo):
    if "lista completa" in texto_baixo or "todos" in texto_baixo or "completo" in texto_baixo:
        resposta = "🏛️ *14 Municípios da Província do Cunene*\n\n"
        for m in MUNICIPIOS_CUNENE:
            comunas_str = ", ".join(m["comunas"]) if m["comunas"] else "Sem comunas"
            admin_str = m["administrador"] if m["administrador"] else "Sem administrador"
            resposta += (
                f"{m['numero']}. *{m['nome']}*\n"
                f"   📍 Comunas: {comunas_str}\n"
                f"   👤 Administrador: {admin_str}\n\n"
            )
        resposta += "Para detalhes de um município específico, diga o nome do município."
        return resposta
    if "nome" in texto_baixo or "quais" in texto_baixo or "quantos" in texto_baixo:
        nomes = [m["nome"] for m in MUNICIPIOS_CUNENE]
        return (
            f"A província do Cunene tem *14 municípios*:\n\n"
            f"{', '.join(nomes)}.\n\n"
            f"Se quiseres a lista completa com comunas e administradores, escreve: *lista completa dos municípios*."
        )
    if "administrador" in texto_baixo:
        resposta = "👤 *Municípios com Administrador*\n\n"
        for m in MUNICIPIOS_CUNENE:
            if m["administrador"]:
                resposta += f"• *{m['nome']}*: {m['administrador']}\n"
        resposta += "\nOs restantes municípios ainda não têm administrador nomeado."
        return resposta
    for m in MUNICIPIOS_CUNENE:
        if m["nome"].lower() in texto_baixo:
            comunas_str = ", ".join(m["comunas"]) if m["comunas"] else "Sem comunas"
            admin_str = m["administrador"] if m["administrador"] else "Sem administrador nomeado"
            return (
                f"🏛️ *Município de {m['nome']}*\n"
                f"🔢 Nº {m['numero']} de 14\n"
                f"📍 Comunas: {comunas_str}\n"
                f"👤 Administrador: {admin_str}"
            )
    for m in MUNICIPIOS_CUNENE:
        nome_sem_acento = m["nome"].lower().replace("é", "e").replace("ô", "o").replace("ã", "a").replace("í", "i")
        texto_sem_acento = texto_baixo.replace("é", "e").replace("ô", "o").replace("ã", "a").replace("í", "i")
        if nome_sem_acento in texto_sem_acento:
            comunas_str = ", ".join(m["comunas"]) if m["comunas"] else "Sem comunas"
            admin_str = m["administrador"] if m["administrador"] else "Sem administrador nomeado"
            return (
                f"🏛️ *Município de {m['nome']}*\n"
                f"🔢 Nº {m['numero']} de 14\n"
                f"📍 Comunas: {comunas_str}\n"
                f"👤 Administrador: {admin_str}"
            )
    return None

# --- ADMINISTRAÇÃO PÚBLICA ---
def handler_administracao(texto_baixo):
    if any(p in texto_baixo for p in ["governo provincial", "tribunal", "agt", "palácio"]):
        locais = {
            "governo provincial": "Governo Provincial do Cunene",
            "tribunal": "Tribunal Provincial",
            "agt": "AGT",
            "palácio": "Palácio do Governo"
        }
        for chave, nome in locais.items():
            if chave in texto_baixo:
                return f"🏛️ *{nome}*\n📍 Bairro Bangula\n🕐 Segunda a Quinta: 08h-15h30 | Sexta: 08h-15h"
    if "administração provincial" in texto_baixo or "mediateca" in texto_baixo or "aeroporto" in texto_baixo:
        locais = {
            "administração provincial": "Administração Provincial",
            "mediateca": "Mediateca Lucas Damba",
            "aeroporto": "Aeroporto Provincial 11 de Novembro"
        }
        for chave, nome in locais.items():
            if chave in texto_baixo:
                return f"🏛️ *{nome}*\n📍 Bairro Kaculuvale\n🕐 Segunda a Quinta: 08h-15h30 | Sexta: 08h-15h"
    if "comando municipal" in texto_baixo or "sic" in texto_baixo or "polícia de investigação" in texto_baixo:
        return "👮 *Comando Municipal da Polícia / SIC*\n📍 Bairro Castilhos\n🕐 Segunda a Quinta: 08h-15h30 | Sexta: 08h-15h"
    if "viação" in texto_baixo or "transita" in texto_baixo or "bombeiros" in texto_baixo or "polícia fiscal" in texto_baixo:
        return "👮 *Polícia de Viação e Trânsito / Bombeiros / Polícia Fiscal*\n📍 Bairro Naipalala"
    if "guarda fronteira" in texto_baixo:
        return "🛡️ *Guarda Fronteira*\n📍 Bairro Kafitu 1"
    return None

# --- COMÉRCIO ---
def handler_comercio(texto_baixo):
    if "shoprite" in texto_baixo:
        if "horário" in texto_baixo or "horario" in texto_baixo or "hora" in texto_baixo or "aberto" in texto_baixo:
            return "🛒 *Shoprite Ondjiva*\n📍 Bairro Castilhos\n🕐 Segunda a Sábado: 08h-20h\n🕐 Domingo: 08h-13h30"
        return "🛒 O *Shoprite* fica no Bairro Castilhos. Diga 'mapa Shoprite' para localização."
    if "angomarte" in texto_baixo:
        if "horário" in texto_baixo or "horario" in texto_baixo or "hora" in texto_baixo or "aberto" in texto_baixo:
            return "🛒 *AngoMarte Ondjiva*\n📍 Bairro Castilhos\n🕐 Segunda a Sábado: 08h-20h\n🕐 Domingo: 08h-13h30"
        return "🛒 O *AngoMarte* fica no Bairro Castilhos. Diga 'mapa AngoMarte' para localização."
    if "comércio" in texto_baixo or "comercio" in texto_baixo or "supermercado" in texto_baixo:
        return (
            "🛒 *Comércio em Ondjiva*\n\n"
            "• *Shoprite* - Bairro Castilhos\n"
            "• *AngoMarte* - Bairro Castilhos\n\n"
            "🕐 Horário: Segunda a Sábado 08h-20h | Domingo 08h-13h30"
        )
    return None

# --- RESPOSTAS DIRETAS ---
RESPOSTAS_DIRETAS = {
    "governadora": "A Governadora da Província do Cunene é *Gerdina Didalelwa*.",
    "quem é a governadora": "A Governadora da Província do Cunene é *Gerdina Didalelwa*.",
    "capital do cunene": "A capital da província do Cunene é *Ondjiva*.",
    "qual é a capital": "A capital da província do Cunene é *Ondjiva*.",
    "quantos municípios": "O Cunene tem *14 municípios*. Escreva 'lista completa dos municípios' se quiser os nomes e administradores.",
    "quantas províncias": "Angola tem *21 províncias* oficiais.",
    "bairros de ondjiva": "Os bairros de Ondjiva são: *Naipalala, Kafitu, Onahumba, Pioneiro Zeca, Castilhos, Kaculuvale, Ekuma, Muhongo, Bangula*.",
}

# ==========================================
# PROCESSAMENTO PRINCIPAL
# ==========================================
def processar_texto(telefone_origem, user_text):
    texto_baixo = user_text.lower().strip()
    MEMORIA_TIMESTAMPS[telefone_origem] = datetime.utcnow()

    # ==========================================
    # 0. HANDLERS BLINDADOS (FACTOS CRÍTICOS)
    # ==========================================
    
    # 0.1 Respostas diretas
    for pergunta, resposta in RESPOSTAS_DIRETAS.items():
        if pergunta in texto_baixo:
            return resposta
    
    # 0.2 Emergência directa
    if any(p in texto_baixo for p in ["emergencia", "emergência", "socorro"]):
        return "🚨 *Emergência:* Polícia 113 | Bombeiros 115. Se estiveres em perigo, abriga-se em um lugar seguro e ligue para os serviços de emergência!"
    
    # 0.3 Hospitais
    if any(p in texto_baixo for p in ["hospital", "ekuma", "simeone", "mucunde"]):
        resposta = handler_hospitais(texto_baixo)
        if resposta:
            return resposta
    
    # 0.4 Escolas e faculdades
    if any(p in texto_baixo for p in ["escola", "colégio", "colegio", "liceu", "instituto", "curso", "estudar", "aula", "ensino"]):
        resposta = handler_escolas(texto_baixo)
        if resposta:
            return resposta
        resposta = handler_faculdades(texto_baixo)
        if resposta:
            return resposta
    
    # 0.5 Administração pública
    if any(p in texto_baixo for p in ["governo", "tribunal", "agt", "administração", "mediateca", "aeroporto", "comando", "sic", "viação", "bombeiros", "fiscal", "guarda", "fronteira"]):
        resposta = handler_administracao(texto_baixo)
        if resposta:
            return resposta
    
    # 0.6 Comércio
    if any(p in texto_baixo for p in ["shoprite", "angomarte", "comércio", "comercio", "supermercado"]):
        resposta = handler_comercio(texto_baixo)
        if resposta:
            return resposta
    
    # 0.7 Mercados e Praças
    if any(p in texto_baixo for p in ["mercado", "praça", "praca", "feira", "lemanha", "xomucuio", "preço", "preco", "preços", "precos", "fuba", "milho"]):
        resposta = handler_mercados(texto_baixo)
        if resposta:
            return resposta
    
    # 0.8 Cheias e Alertas
    if any(p in texto_baixo for p in ["cheia", "cheias", "inundação", "inundacao", "alagamento", "alerta", "chuva", "chuvosa", "temporal", "tempestade", "meteorologia", "clima", "seca", "seco"]):
        resposta = handler_cheias_alertas(texto_baixo)
        if resposta:
            return resposta
    
    # 0.9 Municípios
    if any(p in texto_baixo for p in ["município", "municipio", "municípios", "municipios", "comuna", "comunas", "cahama", "cuanhama", "curoca", "cuvelai", "namacunde", "ombadja", "chiéde", "nehone", "humbe", "mupa", "naulila", "chitado", "cafima", "chissuata"]):
        resposta = handler_municipios(texto_baixo)
        if resposta:
            return resposta

    # ==========================================
    # 1. FALLBACK PARA SUB-MENU
    # ==========================================
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
                "Escolas públicas: ISO (saúde), Oulondelo, IMPO (pedagogia), CESMO, ITAS, Eiffel, várias primárias.\n"
                "Colégios (privados): Pitágoras, Ednas, Popiene, Marc Leandres, Bulet Salú 1/2, Abcunene.\n"
                "Posso detalhar cursos de uma escola específica. Qual te interessa?"
            )
        elif opcao == "D":
            return "Bancos Seg‑Sex 08h‑15h. BAI, BFA, BIC no Centro; BCI, BPC, Sol, Económico em Bangula; BPC2 e Atlântico em Naipalala."
        elif opcao == "E":
            return "Shoprite e AngoMarte (Castilhos) abertos Seg-Sáb 08h‑20h, Dom 08h-13h30. Campo Provincial e da Centralidade para desporto."
        elif opcao == "F":
            return (
                "A província do Cunene é formada por *14 municípios*:\n"
                "Cahama, Cuanhama, Curoca, Cuvelai, Namacunde, Ombadja, Chiéde, Nehone, Humbe, Mupa, Naulila, Chitado, Cafima, Chissuata.\n\n"
                "Se quiseres a lista completa com comunas e administradores, escreve: *lista completa dos municípios*."
            )

    # ==========================================
    # 2. NAVEGAÇÃO (MENU)
    # ==========================================
    if telefone_origem in ESTADO_NAVEGACAO:
        estado = ESTADO_NAVEGACAO[telefone_origem]
        nivel = estado.get("nivel", "menu")

        if nivel == "menu":
            if texto_baixo in ["1", "2", "3", "4", "5", "6"]:
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
                elif opcao == "5":
                    ESTADO_NAVEGACAO.pop(telefone_origem)
                    return (
                        "🛒 *Mercados e Praças de Ondjiva*\n\n"
                        "1. *Praça da Lemanha* - Bairro Kaculuvale\n"
                        "2. *Praça do Xomucuio*\n\n"
                        "📦 Produtos: Fuba, milho, arroz, massa, frango, peixe, tomate, cebola e muito mais.\n"
                        "💰 Para preços atualizados, visite a praça.\n\n"
                        "Digite o nome da praça para mais detalhes ou 'preços'."
                    )
                elif opcao == "6":
                    ESTADO_NAVEGACAO.pop(telefone_origem)
                    return (
                        "⚠️ *Cheias e Clima — Província do Cunene*\n\n"
                        f"🌍 Clima: Árido a semi-árido\n\n"
                        f"☀️ *Estação seca:* Março a Outubro (até 30°C)\n"
                        f"🌧️ *Estação chuvosa:* Novembro a Fevereiro (20°C a 25°C)\n\n"
                        "⚠️ As cheias do Rio Cunene são recorrentes na estação chuvosa.\n\n"
                        "📋 Pode consultar:\n"
                        "• Diga 'áreas de risco'\n"
                        "• Diga 'recomendações cheias'\n"
                        "• Diga 'temperaturas'\n"
                        "• Diga 'rio Cunene'\n\n"
                        "🆘 Emergência: Bombeiros 115 | Polícia 113"
                    )
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
                        "Escolas públicas: ISO (saúde), Oulondelo, IMPO (pedagogia), CESMO, ITAS, Eiffel, várias primárias.\n"
                        "Colégios (privados): Pitágoras, Ednas, Popiene, Marc Leandres, Bulet Salú 1/2, Abcunene.\n"
                        "Posso detalhar cursos de uma escola específica. Qual te interessa?"
                    )
                elif opcao == "D":
                    return "Bancos Seg‑Sex 08h‑15h. BAI, BFA, BIC no Centro da cidade; BCI, BPC, Sol, Económico em Bangula; BPC2 e Atlântico em Naipalala."
                elif opcao == "E":
                    return "Shoprite e AngoMarte (Castilhos) abertos Seg-Sáb 08h‑20h, Dom 08h-13h30. Campo Provincial 11 de novembro e da Campo da Centralidade para desporto."
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

    # ==========================================
    # 3. ACTIVAÇÃO DO MENU
    # ==========================================
    if texto_baixo in ["menu", "ajuda", "help", "guia", "opções", "opcoes", "início", "inicio"] or "como usar" in texto_baixo:
        ESTADO_NAVEGACAO[telefone_origem] = {"nivel": "menu"}
        return (
            "📋 *Menu Principal — Bot Cunene*\n\n"
            "Escolhe o número:\n"
            "1️⃣ Reportar um problema\n"
            "2️⃣ Localização de locais\n"
            "3️⃣ Informações oficiais\n"
            "4️⃣ Emergências\n"
            "5️⃣ Mercado\n"
            "6️⃣ Cheias e alertas\n\n"
            "Responde apenas com o número.\n"
            "Ou faz uma pergunta directa. ✨"
        )

    # ==========================================
    # 4. REPORTAGEM
    # ==========================================
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

    # Máquina de estados da reportagem
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

    # ==========================================
    # 5. ROTA DINÂMICA
    # ==========================================
    for chave, dados in COORDENADAS_ONDJIVA.items():
        if chave in texto_baixo and any(p in texto_baixo for p in ["como chegar", "rota", "caminho", "trajeto"]):
            ESTADO_ROTA[telefone_origem] = dados
            return f"🗺️ Queres ir para *{dados['nome']}*.\n\n📍 Por favor, partilha a tua *Localização Atual* aqui no WhatsApp (clica no 📎 > Localização) para eu gerar a tua rota exata."

    # ==========================================
    # 6. LOCALIZAÇÃO DIRECTA (PIN ESTÁTICO)
    # ==========================================
    for chave, dados in COORDENADAS_ONDJIVA.items():
        if chave in texto_baixo and any(p in texto_baixo for p in ["localização", "localizacao", "onde fica", "onde esta", "mapa"]):
            enviar_localizacao_whatsapp(telefone_origem, dados["lat"], dados["lon"], dados["nome"], dados["endereco"])
            return (f"📍 *{dados['nome']}*\n"
                    f"{dados['endereco']}\n\n"
                    f"💡 *Dica:* Clica no Pin da localização acima e depois no botão *'Como chegar'* no teu telemóvel para veres a rota exata a partir de onde estás.")

    # ==========================================
    # 7. IA (FALLBACK)
    # ==========================================
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
            return ""
        return resposta_ia

    except Exception as e:
        print(f"Erro IA: {e}")
        return "Peço desculpa, estou com uma dificuldade técnica. Tenta mais tarde. Se for urgente, liga 113 ou 115."

# ==========================================
# PROCESSAR LOCALIZAÇÃO
# ==========================================
def processar_localizacao(telefone_origem, lat_origem, lon_origem):
    if telefone_origem in ESTADO_ROTA:
        destino = ESTADO_ROTA[telefone_origem]
        lat_dest = destino["lat"]
        lon_dest = destino["lon"]
        nome_dest = destino["nome"]
        link_rota = f"https://www.google.com/maps/dir/?api=1&origin={lat_origem},{lon_origem}&destination={lat_dest},{lon_dest}&travelmode=driving"
        ESTADO_ROTA.pop(telefone_origem, None)
        return f"🚗 *Rota Calculada para {nome_dest}*\n\nAqui tens o caminho exato a partir de onde estás! Clica no link abaixo para abrir o GPS:\n👉 {link_rota}"
    return "Recebi a tua localização! 📍 Se precisares da rota para algum lugar de Ondjiva, escreve 'Como chegar a [nome do local]'."

# ==========================================
# ROTAS DO FLASK
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
    if body and body.get("object"):
        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                if "messages" in value:
                    msg = value["messages"][0]
                    tel = msg["from"]
                    if msg["type"] == "text":
                        texto = msg["text"]["body"]
                        resposta = processar_texto(tel, texto)
                        if resposta:
                            enviar_mensagem_whatsapp(tel, resposta)
                    elif msg["type"] == "location":
                        lat = msg["location"]["latitude"]
                        lon = msg["location"]["longitude"]
                        resposta = processar_localizacao(tel, lat, lon)
                        if resposta:
                            enviar_mensagem_whatsapp(tel, resposta)
    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
