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
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY")

client = None
if GROQ_API_KEY:
    base_url = os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    client = OpenAI(api_key=GROQ_API_KEY, base_url=base_url)

app = Flask(__name__)

MEMORIA_CONVERSAS = {}
MEMORIA_TIMESTAMPS = {}
ESTADO_REPORTAGEM = {}
ESTADO_NAVEGACAO = {}
ESTADO_ROTA = {}
ESTADO_LISTA = {}
ULTIMA_MENSAGEM_BOT = {}
MENSAGENS_PROCESSADAS = {}
ULTIMA_ATIVIDADE = datetime.utcnow()
CACHE_TEMPO = {"dados": None, "timestamp": None}
CACHE_CAMBIO = {"dados": None, "timestamp": None}
CACHE_NOTICIAS = {"dados": None, "timestamp": None}

# ==========================================
# COORDENADAS DE ONDJIVA (19 LOCAIS)
# ==========================================
COORDENADAS_ONDJIVA = {
    "shoprite": {"lat": -17.06568, "lon": 15.72992, "nome": "Shoprite Ondjiva", "endereco": "Bairro Castilhos, Ondjiva"},
    "angomarte": {"lat": -17.06482, "lon": 15.72898, "nome": "AngoMarte", "endereco": "Bairro Castilhos, Ondjiva"},
    "governo provincial": {"lat": -17.06658, "lon": 15.72728, "nome": "Governo Provincial do Cunene", "endereco": "Bairro Bangula, Ondjiva"},
    "tribunal": {"lat": -17.06699, "lon": 15.72536, "nome": "Tribunal Provincial", "endereco": "Bairro Bangula, Ondjiva"},
    "agt": {"lat": -17.06763, "lon": 15.72551, "nome": "AGT", "endereco": "Bairro Bangula, Ondjiva"},
    "aeroporto": {"lat": -17.04766, "lon": 15.68880, "nome": "Aeroporto Provincial 11 de Novembro", "endereco": "Bairro Kaculuvale, Ondjiva"},
    "mediateca": {"lat": -17.06604, "lon": 15.70646, "nome": "Mediateca Lucas Damba", "endereco": "Bairro Kaculuvale, Ondjiva"},
    "administração provincial": {"lat": -17.06510, "lon": 15.70547, "nome": "Administração Provincial", "endereco": "Bairro Kaculuvale, Ondjiva"},
    "hospital provincial ekuma": {"lat": -17.03817, "lon": 15.73281, "nome": "Hospital Provincial Ekuma", "endereco": "Bairro Ekuma, Ondjiva"},
    "hospital central simeone mucunde": {"lat": -17.09499, "lon": 15.74985, "nome": "Hospital Central Simeone Mucunde", "endereco": "Bairro Naipalala, Ondjiva"},
    "hospital municipal de ondjiva": {"lat": -17.06815, "lon": 15.72368, "nome": "Hospital Municipal de Ondjiva", "endereco": "Bairro Bangula, Ondjiva"},
    "comando provincial da polícia": {"lat": -17.06797, "lon": 15.72263, "nome": "Comando Provincial da Polícia Nacional", "endereco": "Bairro Bangula, Ondjiva"},
    "colégio pitágoras": {"lat": -17.08893, "lon": 15.74526, "nome": "Colégio Pitágoras", "endereco": "Bairro Naipalala, Ondjiva"},
    "oulondelo": {"lat": -17.09357, "lon": 15.74791, "nome": "Complexo Escolar Oulondelo", "endereco": "Bairro Naipalala, Ondjiva"},
    "itas": {"lat": -17.08755, "lon": 15.74177, "nome": "Instituto Técnico de Administração e Serviços (ITAS)", "endereco": "Bairro Naipalala, Ondjiva"},
    "praça da lemanha": {"lat": -17.07664, "lon": 15.70469, "nome": "Praça da Lemanha", "endereco": "Bairro Kaculuvale, Ondjiva"},
    "praça do xomucuio": {"lat": -17.03899, "lon": 15.75077, "nome": "Praça do Xomucuio", "endereco": "Ondjiva"},
    "centralidade do ekuma": {"lat": -17.04533, "lon": 15.74135, "nome": "Centralidade do Ekuma", "endereco": "Bairro Ekuma, Ondjiva"},
    "jardim provincial": {"lat": -17.06622, "lon": 15.72806, "nome": "Jardim Provincial", "endereco": "Bairro Bangula, Ondjiva"},
}

# ==========================================
# BASE DE DADOS - HOSPITAIS (3)
# ==========================================
HOSPITAIS_ONDJIVA = {
    "hospital provincial ekuma": {
        "nome": "Hospital Provincial Ekuma", "bairro": "Ekuma", "tipo": "Provincial",
        "urgencias": "24 horas", "consultas": "Segunda a Sexta, 08h às 15h"
    },
    "hospital central simeone mucunde": {
        "nome": "Hospital Central Simeone Mucunde", "bairro": "Naipalala", "tipo": "Central",
        "urgencias": "24 horas", "consultas": "Segunda a Sexta, 08h às 15h"
    },
    "hospital municipal de ondjiva": {
        "nome": "Hospital Municipal de Ondjiva", "bairro": "Bangula", "tipo": "Municipal",
        "urgencias": "24 horas", "consultas": "Segunda a Sexta, 08h às 15h"
    }
}

ALCUNHAS_HOSPITAIS = {
    "hospital ekuma": "hospital provincial ekuma", "ekuma": "hospital provincial ekuma",
    "simeone mucunde": "hospital central simeone mucunde", "hospital central": "hospital central simeone mucunde",
    "hospital municipal": "hospital municipal de ondjiva",
}

# ==========================================
# BASE DE DADOS - ESCOLAS PÚBLICAS (6)
# ==========================================
ESCOLAS_PUBLICAS = {
    "instituto de saúde de ondjiva": {
        "nome": "Instituto Técnico de Saúde de Ondjiva (ITSO)", "tipo": "Pública", "bairro": "Ekuma",
        "nivel": "Médio Técnico",
        "cursos": ["Enfermagem Geral", "Fisioterapia", "Análises Clínicas"],
        "turnos": ["Manhã: 07h-12h30", "Tarde: 13h-18h05", "Noite: 18h-22h30"]
    },
    "eiffel": {
        "nome": "Colégio Eiffel", "tipo": "Pública", "bairro": "Naipalala", "nivel": "Médio",
        "cursos": ["Ciências Físicas e Biológicas"],
        "turnos": ["Manhã: 07h-12h30", "Tarde: 13h-18h05"]
    },
    "complexo escolar oulondelo": {
        "nome": "Complexo Escolar Oulondelo", "tipo": "Pública", "bairro": "Naipalala", "nivel": "Médio + 1º Ciclo",
        "cursos": ["Ciências Físicas e Biológicas", "Ciências Económicas e Jurídicas"],
        "turnos": ["Manhã: 07h-12h30", "Tarde: 13h-18h05"]
    },
    "instituto médio de pedagogia de ondjiva": {
        "nome": "Instituto Médio de Pedagogia de Ondjiva (IMPO)", "tipo": "Pública", "bairro": "Naipalala",
        "nivel": "Médio Técnico",
        "cursos": ["Matemática e Física", "Ensino Primário", "Educação Moral e Cívica", "Língua Portuguesa", "Bio-Química"],
        "turnos": ["Manhã: 07h-12h30", "Tarde: 13h-18h05", "Noite: 18h-22h30"]
    },
    "complexo escolar cesmo": {
        "nome": "Complexo Escolar CESMO", "tipo": "Pública", "bairro": "Kaculuvale", "nivel": "Médio",
        "cursos": ["Ciências Físicas e Biológicas", "Ciências Económicas e Jurídicas"],
        "turnos": ["Manhã: 07h-12h30", "Tarde: 13h-18h05"]
    },
    "itas": {
        "nome": "Instituto Técnico de Administração e Serviços (ITAS)", "tipo": "Pública", "bairro": "Naipalala",
        "nivel": "Médio Técnico",
        "cursos": ["Finanças", "Secretariado", "Contabilidade", "Gestão Empresarial", "Recursos Humanos"],
        "turnos": ["Manhã: 07h-12h30", "Tarde: 13h-18h05", "Noite: 18h-22h30"]
    },
}

# ==========================================
# BASE DE DADOS - ESCOLAS PRIVADAS (8)
# ==========================================
ESCOLAS_PRIVADAS = {
    "colégio pitágoras": {
        "nome": "Colégio Pitágoras", "tipo": "Privada", "bairro": "Naipalala", "nivel": "Primário + 1º Ciclo + Médio",
        "cursos": ["Farmácia", "Informática", "Eletricidade", "Ciências Físicas e Biológicas", "Enfermagem Geral", "Análises Clínicas"],
        "turnos": ["Manhã: 07h-12h30", "Tarde: 13h-18h05"]
    },
    "colégio ednas": {
        "nome": "Colégio Ednas", "tipo": "Privada", "bairro": "Kaculuvale", "nivel": "Primário + 1º Ciclo + Médio",
        "cursos": ["Ciências Físicas e Biológicas", "Ciências Económicas e Jurídicas"],
        "turnos": ["Manhã: 07h-12h30", "Tarde: 13h-18h05"]
    },
    "colégio popiene": {
        "nome": "Colégio Popiene", "tipo": "Privada", "bairro": "Kaculuvale", "nivel": "Primário",
        "cursos": [], "turnos": ["Manhã: 07h-12h30", "Tarde: 13h-18h05"]
    },
    "colégio arcanjo": {
        "nome": "Colégio Arcanjo", "tipo": "Privada", "bairro": "Naipalala", "nivel": "Primário + 1º Ciclo + Médio",
        "cursos": ["Enfermagem Geral", "Análises Clínicas", "Ciências Físicas e Biológicas"],
        "turnos": ["Manhã: 07h-12h30", "Tarde: 13h-18h05"]
    },
    "colégio marc leandres": {
        "nome": "Colégio Marc Leandres", "tipo": "Privada", "bairro": "Kaculuvale", "nivel": "Primário + 1º Ciclo",
        "cursos": [], "turnos": ["Manhã: 07h-12h30", "Tarde: 13h-18h05"]
    },
    "colégio bulet salú 1": {
        "nome": "Colégio Bulet Salú 1", "tipo": "Privada", "bairro": "Naipalala", "nivel": "Primário + 1º Ciclo + Médio",
        "cursos": ["Ciências Físicas e Biológicas", "Ciências Económicas e Jurídicas", "Ciências Humanas", "Eletricidade"],
        "turnos": ["Manhã: 07h-12h30", "Tarde: 13h-18h05"]
    },
    "colégio bulet salú 2": {
        "nome": "Colégio Bulet Salú 2", "tipo": "Privada", "bairro": "Zeca", "nivel": "Primário + 1º Ciclo + Médio",
        "cursos": ["Ciências Físicas e Biológicas", "Ciências Económicas e Jurídicas", "Ciências Humanas", "Eletricidade"],
        "turnos": ["Manhã: 07h-12h30", "Tarde: 13h-18h05"]
    },
    "colégio abcunene": {
        "nome": "Colégio Abcunene", "tipo": "Privada", "bairro": "Caxila 3", "nivel": "Primário + 1º Ciclo + Médio",
        "cursos": ["Enfermagem Geral", "Análises Clínicas"],
        "turnos": ["Manhã: 07h-12h30", "Tarde: 13h-18h05"]
    },
}

ESCOLAS_ONDJIVA = {**ESCOLAS_PUBLICAS, **ESCOLAS_PRIVADAS}

ALCUNHAS_ESCOLAS = {
    "itso": "instituto de saúde de ondjiva", "iso": "instituto de saúde de ondjiva",
    "eiffel": "eiffel", "oulondelo": "complexo escolar oulondelo",
    "impo": "instituto médio de pedagogia de ondjiva", "cesmo": "complexo escolar cesmo",
    "itas": "itas", "pitágoras": "colégio pitágoras", "pitagoras": "colégio pitágoras",
    "ednas": "colégio ednas", "popiene": "colégio popiene", "arcanjo": "colégio arcanjo",
    "marc leandres": "colégio marc leandres", "bulet": "colégio bulet salú 1",
    "abcunene": "colégio abcunene", "abc": "colégio abcunene",
}

# ==========================================
# MERCADOS, CHEIAS, MUNICÍPIOS, HISTÓRIA, AGRICULTURA, DOENÇAS
# ==========================================
MERCADOS_ONDJIVA = {
    "praça da lemanha": {"nome": "Praça da Lemanha", "bairro": "Kaculuvale", "produtos": ["Fuba", "Milho", "Arroz", "Massa", "Frango", "Peixe", "Tomate", "Cebola", "Alho", "Batata", "Feijão", "Óleo", "Sal", "Açúcar"], "horario": "Todos os dias, das primeiras horas da manhã até ao final da tarde"},
    "praça do xomucuio": {"nome": "Praça do Xomucuio", "bairro": "Ondjiva", "produtos": ["Fuba", "Milho", "Arroz", "Massa", "Frango", "Peixe", "Tomate", "Cebola", "Alho", "Batata", "Feijão", "Óleo", "Sal", "Açúcar"], "horario": "Todos os dias, das primeiras horas da manhã até ao final da tarde"}
}

CHEIAS_ALERTAS = {
    "estacao_seca": {"periodo": "Março a Outubro", "descricao": "Clima seco e quente.", "temperatura": "Média diária até 30°C"},
    "estacao_chuvosa": {"periodo": "Novembro a Fevereiro", "descricao": "Chuvas mais frequentes. Cheias do Rio Cunene recorrentes.", "temperatura": "Média diária entre 20°C e 25°C"},
    "areas_risco": [
        {"zona": "Bairro Kafitu", "risco": "Alto - Zona baixa, propensa a inundações"},
        {"zona": "Bairro Onahumba", "risco": "Médio - Algumas áreas alagadiças"},
        {"zona": "Margens do Rio Cunene", "risco": "Alto - Cheias durante a estação chuvosa"},
        {"zona": "Bairro Castilhos", "risco": "Baixo - Área relativamente elevada"},
    ],
    "contactos_emergencia": {"bombeiros": "115", "policia": "113"},
    "recomendacoes": ["Esteja atento às previsões", "Siga instruções da Protecção Civil", "Evite zonas baixas", "Tenha plano de evacuação"]
}

CLIMA_CUNENE = {"tipo": "Árido a semi-árido", "estacoes": "Duas estações distintas"}

MUNICIPIOS_CUNENE = [
    {"numero": 1, "nome": "Cahama", "comunas": ["Cahama", "Otchinjau"], "administrador": "José Mário Katiti"},
    {"numero": 2, "nome": "Cuanhama", "comunas": ["Ondjiva", "Môngua"], "administrador": "José Felisberto Kalomo"},
    {"numero": 3, "nome": "Curoca", "comunas": ["Oncócua", "Chitado"], "administrador": "António Dos Santos Luepo"},
    {"numero": 4, "nome": "Cuvelai", "comunas": ["Mupa", "Mukolongodjo", "Calonga", "Cubati"], "administrador": "Germano Baptista Nambalo"},
    {"numero": 5, "nome": "Namacunde", "comunas": ["Namacunde", "Chiede"], "administrador": "Cristuiana Nameomunu"},
    {"numero": 6, "nome": "Ombadja", "comunas": ["Humpe", "Mucope", "Naulila", "Ombala yo Mungu", "Xangongo"], "administrador": "Hilario Sikalepo"},
    {"numero": 7, "nome": "Chiéde", "comunas": [], "administrador": None},
    {"numero": 8, "nome": "Nehone", "comunas": ["Nehone", "Evale"], "administrador": None},
    {"numero": 9, "nome": "Humbe", "comunas": ["Mucope", "Humbe"], "administrador": None},
    {"numero": 10, "nome": "Mupa", "comunas": [], "administrador": None},
    {"numero": 11, "nome": "Naulila", "comunas": [], "administrador": None},
    {"numero": 12, "nome": "Chitado", "comunas": [], "administrador": None},
    {"numero": 13, "nome": "Cafima", "comunas": [], "administrador": None},
    {"numero": 14, "nome": "Chissuata", "comunas": [], "administrador": None},
]

HISTORIA_CUNENE = """🏛️ *História do Cunene*
🗿 Povos: Nyaneka-Humbe e Ovambo (Cuanhama).
👑 Rei Mandume ya Ndemufayo: Resistência anticolonial.
🐄 Pastorícia: Base da economia tradicional.
🍽️ Gastronomia: Funge, Maiavi, Chacota.
🏛️ Capital: Ondjiva. 21 províncias em Angola."""

CULTURA_CUNENE = """🎭 *Cultura do Cunene*
🗣️ Línguas: Cuanhama e Português.
👥 Povos: Nyaneka-Humbe e Ovambo.
🐄 Pastorícia: Gado representa riqueza.
🍽️ Pratos: Funge, Maiavi, Chacota."""

AGRICULTURA_INFO = """🌱 *Agricultura no Cunene*
🌾 Culturas: Milho, massango, massambala, trigo, feijão, algodão, cana-de-açúcar.
📊 51.650 lavras familiares, 77.475 hectares (43% cultivado)."""

PECUARIA_INFO = """🐄 *Pecuária no Cunene*
🐂 1.000.000+ cabeças de gado bovino.
🐑 Ovinos Caracul e caprinos.
📋 Regime extensivo com pastagens naturais."""

PESCA_INFO = """🎣 *Pesca Artesanal*
🐟 Praticada no Rio Cunene.
⚠️ Baixos índices de captura por falta de artefatos."""

MINERAIS_INFO = """⛏️ *Recursos Minerais*
💎 Ferro, Cobre, Ouro e Mica."""

SOLO_VEGETACAO_INFO = """🌍 *Solo e Vegetação*
🏜️ Clima tropical seco (20°C).
🌿 Savana: 46% florestal, 23% árida, 20% gramíneas."""

MALARIA_INFO = """🦟 *Malária — Prevenção*
• Mosquiteiros impregnados
• Repelente na pele
• Pulverização intra-domiciliar
• Eliminar águas paradas
• Antimaláricos para grávidas"""

DDA_INFO = """💧 *Doenças Diarreicas — Prevenção*
• Água fervida ou tratada
• Lavar mãos com sabão
• Alimentos bem cozinhados
• Proteger comida de moscas"""

DRACUNCULOSE_INFO = """🪱 *Dracunculose — Prevenção*
• Filtrar água com pano fino
• Proteger fontes de água potável"""

DRA_INFO = """🫁 *Doenças Respiratórias — Prevenção*
• Evitar fumo de lenha em espaços fechados
• Ambientes arejados
• Cobrir boca ao tossir/espirrar
• Vacinação em dia"""

MALNUTRICAO_INFO = """🍽️ *Malnutrição — Prevenção*
• Aleitamento materno até 6 meses
• Papas enriquecidas com produtos locais
• Consultas de vigilância do crescimento"""

VIH_INFO = """❤️ *VIH/Sida — Prevenção*
• Usar preservativo
• Testagem regular
• Tratamento antirretroviral
• Acompanhamento de grávidas seropositivas"""

BILHETE_INFO = """🪪 *Bilhete de Identidade*

📍 *Onde fazer:* Justiça (Conservatória do Registo Civil)
🕐 *Atendimento:* Segunda a Sexta, das 08h às 13h

📋 *Documentos e valores:*

*Primeiro Bilhete:*
• Cédula de nascimento

*Renovação:*
• Bilhete original antigo
• Valor: 455 Kz

*Segunda via (perda ou extravio):*
• Cópia do bilhete ou cédula de nascimento
• Valor: 4.000 Kz"""

# ==========================================
# CONTEXTO PARA IA (COM TODOS OS DADOS OFICIAIS)
# ==========================================
CONTEXTO_ONDJIVA = """
Tu és o Bot_Cunene, assistente digital oficial da província do Cunene, Angola. Falas Português de Angola, de forma calorosa, direta e útil.

## REGRAS DE OURO:
1. NUNCA inventes factos, números, datas, temperaturas ou dados oficiais.
2. Usa *apenas um asterisco* para negrito no WhatsApp.
3. Mantém as respostas diretas e organizadas.
4. Se não tiveres informação sobre algo, admite honestamente.
5. Para perguntas completamente fora do contexto de Angola/Cunene (futebol, Android, iPhone, Messi, Ronaldo, etc.), responde: "Sou o Bot Cunene, assistente da província do Cunene. Posso ajudar com informações sobre saúde, educação, agricultura, meteorologia, serviços administrativos e outros temas da região. Em que posso ajudar?"

## DADOS OFICIAIS DO CUNENE:

### GEOGRAFIA E CLIMA:
- Cunene: Província no SUL de Angola. Capital: Ondjiva. 21 províncias.
- Clima: Árido a semi-árido. Estação seca: Março a Outubro (até 30°C). Estação chuvosa: Novembro a Fevereiro (20°C a 25°C).
- 14 municípios: Cahama, Cuanhama, Curoca, Cuvelai, Namacunde, Ombadja, Chiéde, Nehone, Humbe, Mupa, Naulila, Chitado, Cafima, Chissuata.
- Bairros: Naipalala, Kafitu, Onahumba, Pioneiro Zeca, Castilhos, Kaculuvale, Ekuma, Muhongo, Bangula.
- Governadora: Gerdina Didalelwa.
- Cheias do Rio Cunene recorrentes na estação chuvosa.
- Áreas de risco: Kafitu (Alto), Onahumba (Médio), Margens do Rio Cunene (Alto), Castilhos (Baixo).

### SAÚDE:
- Hospital Provincial Ekuma (Bairro Ekuma)
- Hospital Central Simeone Mucunde (Bairro Naipalala)
- Hospital Municipal de Ondjiva (Bairro Bangula)
- Todos os bairros têm posto médico.
- Urgências: 24h. Consultas: Seg-Sex 08h-15h.
- Não há campanhas de vacinação ativas.

### DOENÇAS E PREVENÇÃO:
- Malária: Mosquiteiros, repelente, eliminar águas paradas, antimaláricos para grávidas.
- Doenças Diarreicas: Água tratada, lavar mãos, alimentos cozinhados.
- Dracunculose: Filtrar água com pano fino.
- Doenças Respiratórias: Evitar fumo de lenha, vacinação.
- Malnutrição: Aleitamento materno, papas enriquecidas.
- VIH/Sida: Preservativo, testagem, antirretrovirais.

### EDUCAÇÃO:
Escolas Públicas: ITSO (Ekuma) - Enfermagem, Fisioterapia, Análises Clínicas; IMPO (Naipalala) - Pedagogia; ITAS (Naipalala) - Finanças, Contabilidade, Gestão; Oulondelo (Naipalala) - CFB, CEJ; Eiffel (Naipalala) - CFB; CESMO (Kaculuvale) - CFB, CEJ.
Colégios Privados: Pitágoras (Farmácia, Informática, Enfermagem); Ednas, Popiene (só primário), Arcanjo, Marc Leandres, Bulet Salú, Abcunene (Enfermagem, Análises Clínicas - NÃO tem Informática).
Turnos: Manhã 07h-12h30, Tarde 13h-18h05, Noite 18h-22h30.
Matrículas: Julho/Agosto.
Documentos: Iniciação/Primário: Bilhete + 2 fotos; 1º Ciclo: Bilhete + 2 fotos + Certificado primário; Ensino Médio: Bilhete + 2 fotos + Certificado 1º ciclo.

### SERVIÇOS ADMINISTRATIVOS:
- Bilhete de Identidade: Justiça (Conservatória do Registo Civil), Seg-Sex 08h-13h.
  Primeiro BI: Cédula de nascimento.
  Renovação: BI antigo + 455 Kz.
  Segunda via: Cópia do BI ou cédula + 4.000 Kz.

### CULTURA E HISTÓRIA:
- Povos: Nyaneka-Humbe e Ovambo.
- Rei Mandume: Resistência anticolonial.
- Gastronomia: Funge, Maiavi, Chacota.
- Pastorícia: 1 milhão+ cabeças de gado.

### AGRICULTURA E PECUÁRIA:
- Culturas: Milho, massango, massambala, trigo, feijão, algodão, cana-de-açúcar.
- 51.650 lavras, 77.475 hectares.
- Pecuária: 1M+ bovinos, ovinos Caracul, caprinos.
- Pesca artesanal no Rio Cunene.
- Minerais: Ferro, Cobre, Ouro, Mica.

### ADMINISTRAÇÃO PÚBLICA:
- Horário: Seg-Qui 08h-15h30, Sex 08h-15h.
- Bangula: Governo Provincial, Tribunal, AGT.
- Kaculuvale: Administração Provincial, Mediateca, Aeroporto.
- Castilhos: Comando Municipal, SIC.
- Naipalala: Viação, Bombeiros, Polícia Fiscal.

### COMÉRCIO E MERCADOS:
- Shoprite e AngoMarte (Castilhos): Seg-Sáb 08h-20h, Dom 08h-13h30.
- Praça da Lemanha (Kaculuvale), Praça do Xomucuio.
- Produtos: Fuba, milho, arroz, massa, frango, peixe, tomate, cebola, etc.

### EMERGÊNCIAS:
- Polícia: 113
- Bombeiros: 115
"""

# ==========================================
# FUNÇÕES DE ENVIO WHATSAPP
# ==========================================
def enviar_mensagem_whatsapp(telefone_destino, texto):
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID: return
    texto = texto.replace("**", "*")
    ULTIMA_MENSAGEM_BOT[telefone_destino] = texto
    if len(texto) > 3800: enviar_mensagens_partidas(telefone_destino, texto); return
    url = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": telefone_destino, "type": "text", "text": {"body": texto}}
    try: requests.post(url, headers=headers, json=payload, timeout=10)
    except Exception as e: print(f"Erro WhatsApp: {e}")

def enviar_mensagens_partidas(telefone_destino, texto):
    while len(texto) > 3800:
        corte = texto.rfind(' ', 0, 3800)
        if corte == -1: corte = 3800
        enviar_mensagem_whatsapp(telefone_destino, texto[:corte].strip())
        texto = texto[corte:].strip()
        time.sleep(0.5)
    if texto: enviar_mensagem_whatsapp(telefone_destino, texto)

def enviar_localizacao_whatsapp(telefone_destino, latitude, longitude, nome_local, endereco):
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID: return
    url = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": telefone_destino, "type": "location", "location": {"latitude": latitude, "longitude": longitude, "name": nome_local, "address": endereco}}
    try: requests.post(url, headers=headers, json=payload, timeout=10)
    except Exception as e: print(f"Erro localização: {e}")

def guardar_reportagem_bd(telefone, relato):
    if not DATABASE_URL: return False
    try:
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE TABLE IF NOT EXISTS reportagens (id SERIAL PRIMARY KEY, telefone VARCHAR(50), relato TEXT, data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
                cur.execute("INSERT INTO reportagens (telefone, relato) VALUES (%s, %s)", (telefone, relato))
                conn.commit()
        return True
    except Exception as e: print(f"Erro BD: {e}"); return False

def limpar_memoria_antiga():
    global MENSAGENS_PROCESSADAS
    while True:
        time.sleep(600)
        agora = datetime.utcnow()
        for tel in list(MEMORIA_TIMESTAMPS.keys()):
            if (agora - MEMORIA_TIMESTAMPS[tel]).total_seconds() > 3600:
                MEMORIA_CONVERSAS.pop(tel, None); MEMORIA_TIMESTAMPS.pop(tel, None)
                ESTADO_REPORTAGEM.pop(tel, None); ESTADO_NAVEGACAO.pop(tel, None)
                ESTADO_ROTA.pop(tel, None); ESTADO_LISTA.pop(tel, None)
                ULTIMA_MENSAGEM_BOT.pop(tel, None)
        if len(MENSAGENS_PROCESSADAS) > 500: MENSAGENS_PROCESSADAS.clear()

threading.Thread(target=limpar_memoria_antiga, daemon=True).start()

# ==========================================
# API DE METEOROLOGIA
# ==========================================
def obter_tempo_ondjiva():
    global CACHE_TEMPO
    if not OPENWEATHER_API_KEY: return None
    if CACHE_TEMPO["dados"] and CACHE_TEMPO["timestamp"]:
        if (datetime.utcnow() - CACHE_TEMPO["timestamp"]).total_seconds() < 1800: return CACHE_TEMPO["dados"]
    try:
        lat, lon = -17.065, 15.730
        url_atual = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric&lang=pt"
        url_previsao = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric&lang=pt&cnt=16"
        r1 = requests.get(url_atual, timeout=10); r2 = requests.get(url_previsao, timeout=10)
        if r1.status_code == 200 and r2.status_code == 200:
            dados = {"atual": r1.json(), "previsao": r2.json()}
            CACHE_TEMPO["dados"] = dados; CACHE_TEMPO["timestamp"] = datetime.utcnow()
            return dados
    except Exception as e: print(f"Erro meteorologia: {e}")
    return None

def formatar_tempo_atual(dados):
    atual = dados["atual"]
    temp = atual["main"]["temp"]; sensacao = atual["main"]["feels_like"]
    humidade = atual["main"]["humidity"]; descricao = atual["weather"][0]["description"].capitalize()
    vento = atual["wind"]["speed"] * 3.6
    emojis = {"Clear": "☀️", "Clouds": "⛅", "Rain": "🌧️", "Drizzle": "🌦️", "Thunderstorm": "⛈️"}
    emoji = emojis.get(atual["weather"][0]["main"], "🌤️")
    chuva = atual.get("rain", {}).get("1h", 0)
    alerta_chuva = f"\n🌧️ Chuva na última hora: {chuva}mm" if chuva > 0 else ""
    nascer = datetime.fromtimestamp(atual["sys"]["sunrise"]).strftime("%H:%M")
    por = datetime.fromtimestamp(atual["sys"]["sunset"]).strftime("%H:%M")
    agora = datetime.utcnow() + timedelta(hours=1)
    hora_por = int(por.split(":")[0])
    texto_por = f"🌇 Pôr do sol (amanhã): {por}" if agora.hour >= hora_por else f"🌇 Pôr do sol (hoje): {por}"
    return (f"{emoji} *Tempo em Ondjiva - Cunene*\n\n"
            f"🌡️ Temperatura: {temp:.0f}°C (sensação: {sensacao:.0f}°C)\n"
            f"💧 Humidade: {humidade}%\n"
            f"☁️ Condição: {descricao}\n"
            f"🌬️ Vento: {vento:.0f} km/h{alerta_chuva}\n"
            f"🌅 Nascer do sol: {nascer}\n"
            f"{texto_por}\n\n"
            f"Diga 'previsão' para ver os próximos dias.")

def formatar_previsao(dados):
    previsao = dados["previsao"]; lista = previsao["list"]
    resposta = "📅 *Previsão para os próximos dias - Ondjiva*\n\n"
    dias = {}
    for item in lista:
        data = datetime.fromtimestamp(item["dt"]); dia_str = data.strftime("%d/%m")
        if dia_str not in dias: dias[dia_str] = []
        dias[dia_str].append(item)
    emojis = {"Clear": "☀️", "Clouds": "⛅", "Rain": "🌧️", "Drizzle": "🌦️", "Thunderstorm": "⛈️"}
    for dia_str, items in list(dias.items())[:4]:
        temps = [item["main"]["temp"] for item in items]; temp_max = max(temps); temp_min = min(temps)
        condicoes = [item["weather"][0]["main"] for item in items]; condicao = max(set(condicoes), key=condicoes.count)
        emoji = emojis.get(condicao, "🌤️"); prob_chuva = max([item.get("pop", 0) for item in items]) * 100
        resposta += f"{emoji} *{dia_str}:* {temp_max:.0f}°C / {temp_min:.0f}°C"
        if prob_chuva > 20: resposta += f" | 🌧️ {prob_chuva:.0f}%"
        resposta += "\n"
    agora = datetime.utcnow() + timedelta(hours=1)
    resposta += "\n☀️ *Estação seca:* Mantenha-se hidratado." if 3 <= agora.month <= 10 else "\n🌧️ *Estação chuvosa:* Atenção às cheias do Rio Cunene."
    return resposta

def handler_meteorologia(texto_baixo):
    expressoes_tempo = ["tempo", "como está o tempo", "tempo hoje", "tempo amanhã", "tempo em ondjiva", "previsão", "previsao", "previsões", "previsoes", "previsão do tempo", "vai chover", "meteorologia", "temperatura", "quantos graus", "clima hoje"]
    expressoes_bloqueio = ["perder tempo", "perdendo tempo", "muito tempo", "no tempo", "meu tempo", "seu tempo"]
    if any(p in texto_baixo for p in expressoes_bloqueio): return None
    if not any(p in texto_baixo for p in expressoes_tempo): return None
    if not OPENWEATHER_API_KEY: return "⚠️ Serviço de meteorologia temporariamente indisponível."
    dados = obter_tempo_ondjiva()
    if not dados: return f"⚠️ Não foi possível obter dados meteorológicos.\n\n📋 *Clima do Cunene:*\n🌍 {CLIMA_CUNENE['tipo']}\n☀️ Estação seca: Março a Outubro (até 30°C)\n🌧️ Estação chuvosa: Novembro a Fevereiro (20°C a 25°C)"
    if any(p in texto_baixo for p in ["previsão", "previsao", "previsões", "previsoes", "próximos", "dias", "semana"]): return formatar_previsao(dados)
    if any(p in texto_baixo for p in ["chuva", "chover", "vai chover"]):
        chuva = dados["atual"].get("rain", {}).get("1h", 0)
        return f"🌧️ Sim, está a chover em Ondjiva! Precipitação: {chuva}mm.\n\n{formatar_tempo_atual(dados)}" if chuva > 0 else f"☀️ Não está a chover.\n\n{formatar_tempo_atual(dados)}"
    return formatar_tempo_atual(dados)

# ==========================================
# API DE CÂMBIO
# ==========================================
def obter_cambio():
    global CACHE_CAMBIO
    if CACHE_CAMBIO["dados"] and CACHE_CAMBIO["timestamp"]:
        if (datetime.utcnow() - CACHE_CAMBIO["timestamp"]).total_seconds() < 3600: return CACHE_CAMBIO["dados"]
    try:
        response = requests.get("https://api.exchangerate-api.com/v4/latest/AOA", timeout=10)
        if response.status_code == 200:
            dados = response.json(); CACHE_CAMBIO["dados"] = dados; CACHE_CAMBIO["timestamp"] = datetime.utcnow()
            return dados
    except Exception as e: print(f"Erro câmbio: {e}")
    return None

def handler_cambio(texto_baixo):
    if not any(p in texto_baixo for p in ["câmbio", "cambio", "dólar", "dolar", "euro", "rand", "zar", "kwanza", "moeda", "conversão", "equivale", "quantos"]): return None
    dados = obter_cambio()
    if not dados: return "💱 Serviço de câmbio temporariamente indisponível."
    taxas = dados.get("rates", {})
    import re
    moedas = {"usd": "USD", "dólar": "USD", "dolar": "USD", "eur": "EUR", "euro": "EUR", "zar": "ZAR", "rand": "ZAR", "kwanza": "AOA"}
    moeda_enc = None
    for chave, codigo in moedas.items():
        if chave in texto_baixo: moeda_enc = codigo; break
    numeros = re.findall(r'\d+[\.,]?\d*', texto_baixo)
    if numeros and moeda_enc:
        aoa_para_moeda = taxas.get(moeda_enc, 0)
        if aoa_para_moeda > 0:
            resultado = float(numeros[0].replace(',', '.')) * (1 / aoa_para_moeda)
            nomes = {"USD": "Dólares", "EUR": "Euros", "ZAR": "Rand", "AOA": "Kwanzas"}
            return f"💱 *Conversão de Moeda*\n\n{numeros[0]} {nomes.get(moeda_enc, moeda_enc)} = *{resultado:,.0f} AOA* (Kwanzas)\n\nFonte: Taxas de referência."
    usd = 1/taxas.get("USD", 0.001) if taxas.get("USD", 0) > 0 else 0
    eur = 1/taxas.get("EUR", 0.001) if taxas.get("EUR", 0) > 0 else 0
    zar = 1/taxas.get("ZAR", 0.001) if taxas.get("ZAR", 0) > 0 else 0
    return f"💱 *Câmbio Atual*\n\n🇺🇸 1 USD = {usd:,.0f} AOA\n🇪🇺 1 EUR = {eur:,.0f} AOA\n🇿🇦 1 ZAR = {zar:,.0f} AOA (Rand)\n\nPara converter: '100 ZAR para Kwanzas'.\n\nFonte: Taxas de referência do Banco Nacional de Angola."

# ==========================================
# API DE NOTÍCIAS
# ==========================================
def obter_noticias_cunene():
    global CACHE_NOTICIAS
    if not NEWS_API_KEY: return None
    if CACHE_NOTICIAS["dados"] and CACHE_NOTICIAS["timestamp"]:
        if (datetime.utcnow() - CACHE_NOTICIAS["timestamp"]).total_seconds() < 3600: return CACHE_NOTICIAS["dados"]
    try:
        response = requests.get(f"https://newsapi.org/v2/everything?q=Cunene+Angola&apiKey={NEWS_API_KEY}&language=pt&pageSize=5&sortBy=publishedAt", timeout=10)
        if response.status_code == 200:
            dados = response.json(); CACHE_NOTICIAS["dados"] = dados; CACHE_NOTICIAS["timestamp"] = datetime.utcnow()
            return dados
    except Exception as e: print(f"Erro notícias: {e}")
    return None

def handler_noticias(texto_baixo):
    if not any(p in texto_baixo for p in ["notícia", "noticia", "notícias", "noticias", "novidades", "jornal"]): return None
    if not NEWS_API_KEY: return "📰 Serviço de notícias indisponível."
    dados = obter_noticias_cunene()
    if not dados or not dados.get("articles"): return "📰 Não encontrei notícias recentes sobre o Cunene."
    resposta = "📰 *Últimas notícias — Cunene e Angola*\n\n"
    for i, artigo in enumerate(dados["articles"][:5], 1):
        resposta += f"{i}. *{artigo.get('title', 'Sem título')}*\n   📰 Fonte: {artigo.get('source', {}).get('name', 'Desconhecido')}\n\n"
    return resposta

# ==========================================
# HANDLERS
# ==========================================
def handler_cuanhama(texto_baixo):
    if texto_baixo in ["wa aluka", "wa aluka po", "aluka"]:
        agora = datetime.utcnow() + timedelta(hours=1)
        if 5 <= agora.hour < 12: return "Wa aluka! ☀️ *Bot Cunene* ove li po. (Bom dia! Escreve *menu*.)"
        elif 12 <= agora.hour < 18: return "Wa aluka! 🌤️ *Bot Cunene* ove li po. (Boa tarde! Escreve *menu*.)"
        else: return "Wa aluka! 🌙 *Bot Cunene* ove li po. (Boa noite! Escreve *menu*.)"
    if "ame ove" in texto_baixo or "ou li tutu" in texto_baixo: return "Ondei! 😊 *Tangi* (Estou bem! Escreve *menu*.)"
    if texto_baixo in ["tangi", "nda pandula"]: return "Ka li na shilwe! 🙏 (De nada! Escreve *menu*.)"
    if texto_baixo in ["eeno", "eyo"]: return "Eeno! 😊 Escreve *menu*."
    if texto_baixo in ["ahawe", "kawe"]: return "Ahawe, tudo bem! Escreve *menu*."
    if texto_baixo in ["ka kala po nawa", "shilwe"]: return "Ka kala po nawa! 👋"
    return None

def handler_conversa_casual(texto_baixo):
    if texto_baixo in ["oi", "olá", "ola", "oie", "hey", "ei"]:
        agora = datetime.utcnow() + timedelta(hours=1)
        if 5 <= agora.hour < 12: saudacao = "Bom dia"
        elif 12 <= agora.hour < 18: saudacao = "Boa tarde"
        else: saudacao = "Boa noite"
        return f"{saudacao}! 👋 Sou o *Bot Cunene*. Escreve *menu* para veres as opções."
    if texto_baixo in ["bom dia", "boa tarde", "boa noite"]: return f"{texto_baixo.capitalize()}! 👋 Sou o *Bot Cunene*. Escreve *menu*."
    if any(p in texto_baixo for p in ["como estás", "como estas", "tudo bem", "como vai"]): return "Estou bem, obrigado! 😊 Escreve *menu*."
    if any(p in texto_baixo for p in ["obrigado", "obrigada", "valeu", "brigado"]): return "De nada! 😊 Escreve *menu* se precisares."
    if texto_baixo in ["sim", "s", "yes", "y", "sim e você", "sim e voce"]: return "😊 Em que posso ajudar? Escreve *menu*."
    if texto_baixo in ["não", "nao", "n", "no"]: return "Tudo bem! Escreve *menu* se mudares de ideias."
    return None

def handler_matricula(texto_baixo):
    if any(p in texto_baixo for p in ["matrícula", "matricula", "matricular", "documentos necessários", "documentos para", "preciso para matricular", "documentos exigidos", "como matricular", "quero matricular"]):
        return ("📝 *Matrículas — Ano Letivo*\n\n📅 *Período:* Julho/Agosto.\n\n📋 *Documentos Necessários:*\n\n*Iniciação e Ensino Primário:*\n• Bilhete de identidade ou cédula de nascimento\n• Duas fotos tipo passe\n\n*1º Ciclo:*\n• Cópia do bilhete de identidade\n• Duas fotos tipo passe\n• Certificado de conclusão do ensino primário\n\n*Ensino Médio:*\n• Cópia do bilhete de identidade\n• Duas fotos tipo passe\n• Certificado de conclusão do 1º ciclo\n\n📍 Dirija-se à escola mais próxima para efetuar a matrícula.")
    return None

def handler_bilhete(texto_baixo):
    if any(p in texto_baixo for p in ["bilhete de identidade", "bilhete", "bi", "registo civil", "justiça", "segunda via", "renovar bilhete"]):
        return BILHETE_INFO
    return None

def handler_historia_cultura(texto_baixo):
    if any(p in texto_baixo for p in ["história", "historia", "origem", "passado", "colonial"]):
        return "👑 *Rei Mandume ya Ndemufayo*\n\nGrande líder do povo Cuanhama, símbolo da resistência anticolonial no Cunene." if ("mandume" in texto_baixo or "rei" in texto_baixo) else HISTORIA_CUNENE
    if any(p in texto_baixo for p in ["cultura", "tradição", "costume"]): return CULTURA_CUNENE
    if any(p in texto_baixo for p in ["gastronomia", "comida", "funge", "maiavi", "chacota"]): return "🍽️ *Gastronomia do Cunene*\n\n• *Funge:* Massa de massango ou milho.\n• *Maiavi:* Leite azedo.\n• *Chacota:* Carne seca ao sol."
    if "mandume" in texto_baixo: return "👑 *Rei Mandume ya Ndemufayo*\n\nGrande líder do povo Cuanhama, símbolo da resistência anticolonial."
    if any(p in texto_baixo for p in ["gado", "boi", "pastor"]): return "🐄 *Pastorícia no Cunene*\n\nA criação de gado bovino é a base da economia tradicional."
    return None

def handler_doencas(texto_baixo):
    if "malária" in texto_baixo or "malaria" in texto_baixo: return MALARIA_INFO
    if "diarreica" in texto_baixo or "diarreia" in texto_baixo or "tifóide" in texto_baixo: return DDA_INFO
    if "dracunculose" in texto_baixo or "verme" in texto_baixo or "guiné" in texto_baixo: return DRACUNCULOSE_INFO
    if "respiratória" in texto_baixo or "respiratoria" in texto_baixo or "tosse" in texto_baixo or "pneumonia" in texto_baixo: return DRA_INFO
    if "malnutrição" in texto_baixo or "desnutrição" in texto_baixo: return MALNUTRICAO_INFO
    if "vih" in texto_baixo or "sida" in texto_baixo or "hiv" in texto_baixo or "preservativo" in texto_baixo: return VIH_INFO
    if "doença" in texto_baixo or "doenca" in texto_baixo or "prevenção" in texto_baixo: return "🩺 *Doenças e Prevenção no Cunene*\n\n• Malária\n• Doenças Diarreicas e Febre Tifóide\n• Dracunculose\n• Doenças Respiratórias\n• Malnutrição\n• VIH/Sida\n\nDigite o nome da doença."
    return None

def pesquisar_hospital(texto):
    for chave, dados in HOSPITAIS_ONDJIVA.items():
        if chave in texto: return dados
    for alcunha, chave_oficial in ALCUNHAS_HOSPITAIS.items():
        if alcunha in texto: return HOSPITAIS_ONDJIVA[chave_oficial]
    if "hospital" in texto:
        if "ekuma" in texto: return HOSPITAIS_ONDJIVA["hospital provincial ekuma"]
        elif "simeone" in texto or "mucunde" in texto or "central" in texto: return HOSPITAIS_ONDJIVA["hospital central simeone mucunde"]
        elif "municipal" in texto or "bangula" in texto: return HOSPITAIS_ONDJIVA["hospital municipal de ondjiva"]
    return None

def formatar_resposta_hospital(d): return f"🏥 *{d['nome']}*\n📍 Bairro: {d['bairro']}\n🕐 Urgências: {d['urgencias']}\n🕐 Consultas externas: {d['consultas']}\n\nPara localização, diga 'onde fica {d['nome']}'."

def listar_todos_hospitais():
    r = "🏥 *Hospitais em Ondjiva*\n\n"
    for i, (chave, dados) in enumerate(HOSPITAIS_ONDJIVA.items(), 1): r += f"{i}. *{dados['nome']}*\n   📍 Bairro: {dados['bairro']}\n   🕐 Consultas: {dados['consultas']}\n\n"
    return r + "Responda com o número ou nome do hospital."

def handler_hospitais(texto_baixo, telefone=None):
    if any(p in texto_baixo for p in ["todos", "lista", "quais"]):
        if telefone: ESTADO_LISTA[telefone] = {"tipo": "hospitais", "dados": list(HOSPITAIS_ONDJIVA.keys())}
        return listar_todos_hospitais()
    h = pesquisar_hospital(texto_baixo)
    if h: return formatar_resposta_hospital(h)
    if "hospital" in texto_baixo:
        if telefone: ESTADO_LISTA[telefone] = {"tipo": "hospitais", "dados": list(HOSPITAIS_ONDJIVA.keys())}
        return listar_todos_hospitais()
    return None

def pesquisar_escola(texto):
    for chave, dados in ESCOLAS_ONDJIVA.items():
        if chave in texto: return dados
    for alcunha, chave_oficial in ALCUNHAS_ESCOLAS.items():
        if alcunha in texto: return ESCOLAS_ONDJIVA[chave_oficial]
    return None

def formatar_resposta_escola(d):
    """Resposta SEMPRE completa com todos os cursos e turnos"""
    emoji = "🏫" if d['tipo'] == "Pública" else "🎓"
    if d['cursos']:
        cursos_str = "\n".join([f"  • {c}" for c in d['cursos']])
    else:
        cursos_str = "  • Ensino Primário" if d['nivel'] == "Primário" else "  • Ensino Primário e 1º Ciclo"
    turnos_str = "\n".join([f"  • {t}" for t in d['turnos']])
    return f"{emoji} *{d['nome']}*\n📚 {d['tipo']} | {d['nivel']}\n📍 Bairro: {d['bairro']}\n\n📖 *Cursos:*\n{cursos_str}\n\n🕐 *Turnos:*\n{turnos_str}"

def listar_escolas_por_tipo(tipo=None):
    escolas = ESCOLAS_PUBLICAS if tipo == "Pública" else ESCOLAS_PRIVADAS if tipo else ESCOLAS_ONDJIVA
    titulo = "🏫 Escolas Públicas" if tipo == "Pública" else "🎓 Colégios Privados" if tipo else "📚 Escolas em Ondjiva"
    r = f"{titulo}\n\n"
    for i, (chave, dados) in enumerate(escolas.items(), 1):
        cursos = ", ".join(dados['cursos'][:3]) + ("..." if len(dados['cursos'])>3 else "") if dados['cursos'] else ("Ensino Primário" if dados['nivel']=="Primário" else "Ensino Primário e 1º Ciclo")
        r += f"{i}. *{dados['nome']}*\n   📍 {dados['bairro']}\n   📖 {cursos}\n\n"
    return r + "Responda com o número ou nome da escola."

def handler_escolas(texto_baixo, telefone=None):
    if any(p in texto_baixo for p in ["o que é", "o que e", "defina", "conceito"]): return None
    if any(p in texto_baixo for p in ["pública", "publica", "públicas"]):
        if telefone: ESTADO_LISTA[telefone] = {"tipo": "escolas", "dados": list(ESCOLAS_PUBLICAS.keys())}
        return listar_escolas_por_tipo(tipo="Pública")
    if any(p in texto_baixo for p in ["privada", "privadas", "privado", "particular"]):
        if telefone: ESTADO_LISTA[telefone] = {"tipo": "escolas", "dados": list(ESCOLAS_PRIVADAS.keys())}
        return listar_escolas_por_tipo(tipo="Privada")
    if "enfermagem" in texto_baixo: return "📖 *Escolas com Enfermagem Geral:*\n🏫 ITSO (Pública - Ekuma)\n🎓 Colégio Pitágoras (Privada - Naipalala)\n🎓 Colégio Arcanjo (Privada - Naipalala)\n🎓 Colégio Abcunene (Privada - Caxila 3)"
    if "informática" in texto_baixo or "informatica" in texto_baixo: return "📖 *Escolas com Informática:*\n🎓 Colégio Pitágoras (Privada - Naipalala)"
    if "contabilidade" in texto_baixo or "finanças" in texto_baixo: return "📖 *Escola com Finanças/Contabilidade:*\n🏫 ITAS (Pública - Naipalala)"
    escola = pesquisar_escola(texto_baixo)
    if escola: return formatar_resposta_escola(escola)
    if any(p in texto_baixo for p in ["escola", "colégio", "colegio", "liceu", "instituto"]): return "📚 *Escolas em Ondjiva*\n\n🏫 *Públicas:* ITSO, Eiffel, Oulondelo, IMPO, CESMO, ITAS\n🎓 *Privadas:* Pitágoras, Ednas, Popiene, Arcanjo, Marc Leandres, Bulet Salú, Abcunene\n\nDiga 'escolas públicas', 'colégios privados' ou o nome da escola."
    return None

def handler_mercados(texto_baixo, telefone=None):
    if any(p in texto_baixo for p in ["preço", "preco", "preços", "custa", "custo", "valor"]):
        for chave, dados in MERCADOS_ONDJIVA.items():
            if chave in texto_baixo: return f"🛒 *{dados['nome']}*\n\n💰 Os preços variam conforme a época.\n📌 Visite a praça.\n📍 Bairro: {dados['bairro']}\n🕐 {dados['horario']}"
        return "💰 Os preços variam conforme a época.\n📌 Visite as praças:\n• Praça da Lemanha (Kaculuvale)\n• Praça do Xomucuio"
    if "lemanha" in texto_baixo: m = MERCADOS_ONDJIVA["praça da lemanha"]; return f"🛒 *{m['nome']}*\n📍 {m['bairro']}\n🕐 {m['horario']}\n📦 Produtos: {', '.join(m['produtos'])}"
    if "xomucuio" in texto_baixo or "xamucuio" in texto_baixo: m = MERCADOS_ONDJIVA["praça do xomucuio"]; return f"🛒 *{m['nome']}*\n📍 {m['bairro']}\n🕐 {m['horario']}\n📦 Produtos: {', '.join(m['produtos'])}"
    if any(p in texto_baixo for p in ["mercado", "praça", "praca", "feira"]):
        if telefone: ESTADO_LISTA[telefone] = {"tipo": "mercados", "dados": list(MERCADOS_ONDJIVA.keys())}
        return "🛒 *Mercados e Praças*\n\n1. Praça da Lemanha (Kaculuvale)\n2. Praça do Xomucuio\n\n📦 Produtos: Fuba, milho, arroz, massa, frango, peixe, tomate, cebola e muito mais.\n\nResponda com o número (1 ou 2)."
    return None

def handler_cheias_alertas(texto_baixo):
    if any(p in texto_baixo for p in ["clima", "climático"]): return f"🌍 *Clima do Cunene*\n\n📋 Tipo: {CLIMA_CUNENE['tipo']}\n☀️ Estação seca: Março a Outubro (até 30°C)\n🌧️ Estação chuvosa: Novembro a Fevereiro (20°C a 25°C)"
    if "seca" in texto_baixo or "seco" in texto_baixo: return f"☀️ *Estação Seca*\n📅 Período: {CHEIAS_ALERTAS['estacao_seca']['periodo']}\n🌡️ Temperatura: {CHEIAS_ALERTAS['estacao_seca']['temperatura']}"
    if "chuvosa" in texto_baixo or "chuva" in texto_baixo or "inverno" in texto_baixo: return f"🌧️ *Estação Chuvosa*\n📅 Período: {CHEIAS_ALERTAS['estacao_chuvosa']['periodo']}\n🌡️ Temperatura: {CHEIAS_ALERTAS['estacao_chuvosa']['temperatura']}"
    if "temperatura" in texto_baixo: return f"🌡️ *Temperaturas no Cunene*\n☀️ Estação seca: até 30°C\n🌧️ Estação chuvosa: 20°C a 25°C"
    if any(p in texto_baixo for p in ["área", "area", "zona", "risco", "alaga"]):
        r = "⚠️ *Áreas de Risco - Cheias em Ondjiva*\n\n"
        for a in CHEIAS_ALERTAS['areas_risco']: r += f"📍 *{a['zona']}*\n   Risco: {a['risco']}\n\n"
        return r
    if any(p in texto_baixo for p in ["contacto", "telefone", "emergência", "socorro"]): return "🆘 *Contactos de Emergência*\n🚒 Bombeiros: 115\n👮 Polícia: 113"
    if "recomenda" in texto_baixo or "dica" in texto_baixo: return "🛡️ *Recomendações*\n\n" + "\n".join([f"  ✓ {r}" for r in CHEIAS_ALERTAS['recomendacoes']])
    if "rio cunene" in texto_baixo: return "🌊 *Rio Cunene*\n⚠️ Cheias recorrentes na estação chuvosa (Novembro-Fevereiro)."
    if any(p in texto_baixo for p in ["cheia", "cheias", "inundação", "alerta", "alagamento"]): return f"⚠️ *Cheias e Clima — Cunene*\n🌍 Clima: {CLIMA_CUNENE['tipo']}\n☀️ Seca: Março a Outubro\n🌧️ Chuvosa: Novembro a Fevereiro\n🆘 Emergência: 115 | 113"
    return None

def handler_municipios(texto_baixo):
    if "lista completa" in texto_baixo or "completo" in texto_baixo:
        r = "🏛️ *14 Municípios da Província do Cunene*\n\n"
        for m in MUNICIPIOS_CUNENE: r += f"{m['numero']}. *{m['nome']}*\n   📍 Comunas: {', '.join(m['comunas']) if m['comunas'] else 'Sem comunas'}\n   👤 Administrador: {m['administrador'] if m['administrador'] else 'Sem administrador'}\n\n"
        return r
    if any(p in texto_baixo for p in ["quais", "quantos", "municípios do cunene"]):
        nomes = [m["nome"] for m in MUNICIPIOS_CUNENE]; return f"A província do Cunene tem *14 municípios*:\n\n{', '.join(nomes)}.\n\nPara lista completa: *lista completa dos municípios*."
    if "administrador" in texto_baixo:
        for m in MUNICIPIOS_CUNENE:
            if m["nome"].lower() in texto_baixo: return f"👤 O administrador de *{m['nome']}* é *{m['administrador']}*." if m["administrador"] else f"O município de *{m['nome']}* ainda não tem administrador nomeado."
    for m in MUNICIPIOS_CUNENE:
        if m["nome"].lower() in texto_baixo: return f"🏛️ *Município de {m['nome']}*\n🔢 Nº {m['numero']} de 14\n📍 Comunas: {', '.join(m['comunas']) if m['comunas'] else 'Sem comunas'}\n👤 Administrador: {m['administrador'] if m['administrador'] else 'Sem administrador nomeado'}"
    return None

def handler_administracao(texto_baixo):
    if any(p in texto_baixo for p in ["governo provincial", "tribunal", "agt"]):
        locais = {"governo provincial": "Governo Provincial", "tribunal": "Tribunal Provincial", "agt": "AGT"}
        for chave, nome in locais.items():
            if chave in texto_baixo: return f"🏛️ *{nome}*\n📍 Bairro Bangula\n🕐 Seg-Qui 08h-15h30 | Sex 08h-15h"
    if "administração provincial" in texto_baixo or "mediateca" in texto_baixo or "aeroporto" in texto_baixo:
        locais = {"administração provincial": "Administração Provincial", "mediateca": "Mediateca Lucas Damba", "aeroporto": "Aeroporto 11 de Novembro"}
        for chave, nome in locais.items():
            if chave in texto_baixo: return f"🏛️ *{nome}*\n📍 Bairro Kaculuvale\n🕐 Seg-Qui 08h-15h30 | Sex 08h-15h"
    if "comando municipal" in texto_baixo or "sic" in texto_baixo: return "👮 *Comando Municipal / SIC*\n📍 Bairro Castilhos"
    if "viação" in texto_baixo or "bombeiros" in texto_baixo or "polícia fiscal" in texto_baixo: return "👮 *Viação e Trânsito / Bombeiros / Polícia Fiscal*\n📍 Bairro Naipalala"
    if "guarda fronteira" in texto_baixo: return "🛡️ *Guarda Fronteira*\n📍 Bairro Kafitu 1"
    return None

def handler_comercio(texto_baixo):
    if "shoprite" in texto_baixo:
        if "horário" in texto_baixo or "aberto" in texto_baixo: return "🛒 *Shoprite Ondjiva*\n📍 Bairro Castilhos\n🕐 Seg-Sáb 08h-20h | Dom 08h-13h30"
        return "🛒 O *Shoprite* fica no Bairro Castilhos."
    if "angomarte" in texto_baixo:
        if "horário" in texto_baixo or "aberto" in texto_baixo: return "🛒 *AngoMarte Ondjiva*\n📍 Bairro Castilhos\n🕐 Seg-Sáb 08h-20h | Dom 08h-13h30"
        return "🛒 O *AngoMarte* fica no Bairro Castilhos."
    return None

RESPOSTAS_DIRETAS = {
    "governadora": "A Governadora da Província do Cunene é *Gerdina Didalelwa*.",
    "capital do cunene": "A capital da província do Cunene é *Ondjiva*.",
    "bairros de ondjiva": "Os bairros de Ondjiva são: *Naipalala, Kafitu, Onahumba, Pioneiro Zeca, Castilhos, Kaculuvale, Ekuma, Muhongo, Bangula*.",
}

# ==========================================
# PROCESSAMENTO PRINCIPAL
# ==========================================
def processar_texto(telefone_origem, user_text):
    texto_baixo = user_text.lower().strip()
    MEMORIA_TIMESTAMPS[telefone_origem] = datetime.utcnow()

    # LISTAS NUMERADAS
    if texto_baixo.isdigit() and telefone_origem in ESTADO_LISTA:
        numero = int(texto_baixo); ctx = ESTADO_LISTA[telefone_origem]
        if ctx["tipo"] == "escolas" and 1 <= numero <= len(ctx["dados"]):
            ESTADO_LISTA.pop(telefone_origem); return formatar_resposta_escola(ESCOLAS_ONDJIVA[ctx["dados"][numero-1]])
        elif ctx["tipo"] == "hospitais" and 1 <= numero <= len(ctx["dados"]):
            ESTADO_LISTA.pop(telefone_origem); return formatar_resposta_hospital(HOSPITAIS_ONDJIVA[ctx["dados"][numero-1]])
        elif ctx["tipo"] == "mercados" and 1 <= numero <= len(ctx["dados"]):
            m = MERCADOS_ONDJIVA[ctx["dados"][numero-1]]; ESTADO_LISTA.pop(telefone_origem)
            return f"🛒 *{m['nome']}*\n📍 {m['bairro']}\n🕐 {m['horario']}\n📦 Produtos: {', '.join(m['produtos'])}"
        ESTADO_LISTA.pop(telefone_origem); return "❌ Número inválido. Escreve *menu*."

    # RESPOSTAS DIRETAS
    for pergunta, resposta in RESPOSTAS_DIRETAS.items():
        if pergunta in texto_baixo: return resposta

    # EMERGÊNCIA
    if any(p in texto_baixo for p in ["emergencia", "emergência", "socorro"]): return "🚨 *Emergência:* Polícia 113 | Bombeiros 115."

    # CUANHAMA
    resposta = handler_cuanhama(texto_baixo)
    if resposta: return resposta

    # CONVERSA CASUAL
    resposta = handler_conversa_casual(texto_baixo)
    if resposta: return resposta

    # MATRÍCULA (ANTES DO FORA DO CONTEXTO)
    resposta = handler_matricula(texto_baixo)
    if resposta: return resposta

    # BILHETE DE IDENTIDADE
    resposta = handler_bilhete(texto_baixo)
    if resposta: return resposta

    # METEOROLOGIA
    resposta = handler_meteorologia(texto_baixo)
    if resposta: return resposta

    # CÂMBIO
    resposta = handler_cambio(texto_baixo)
    if resposta: return resposta

    # NOTÍCIAS
    resposta = handler_noticias(texto_baixo)
    if resposta: return resposta

    # NAVEGAÇÃO (MENU)
    if telefone_origem in ESTADO_NAVEGACAO:
        estado = ESTADO_NAVEGACAO[telefone_origem]; nivel = estado.get("nivel", "menu")
        if nivel == "menu":
            if texto_baixo in ["1", "2", "3", "4", "5", "6", "7", "8"]:
                opcao = texto_baixo
                if opcao == "1":
                    ESTADO_NAVEGACAO.pop(telefone_origem); ESTADO_REPORTAGEM[telefone_origem] = {'passo': 1, 'problema': '', 'tempo': '', 'causa': '', 'inicio': datetime.utcnow()}
                    return "📝 *Reportagem de Problema*\n\nDescreve o problema que queres reportar."
                elif opcao == "2": ESTADO_NAVEGACAO[telefone_origem]["nivel"] = "localizacao_pedido"; return "📍 Diz-me o nome do local que queres localizar."
                elif opcao == "3": ESTADO_NAVEGACAO[telefone_origem]["nivel"] = "info_submenu"; return "📋 *Informações oficiais:*\nA - Administração Pública\nB - Saúde\nC - Ensino\nD - Bancos\nE - Comércio e Lazer\nF - Divisão Administrativa"
                elif opcao == "4": ESTADO_NAVEGACAO.pop(telefone_origem); return "🚨 *Emergências:* Polícia 113, Bombeiros 115."
                elif opcao == "5":
                    ESTADO_NAVEGACAO.pop(telefone_origem); ESTADO_LISTA[telefone_origem] = {"tipo": "mercados", "dados": list(MERCADOS_ONDJIVA.keys())}
                    return "🛒 *Mercados e Praças*\n\n1. Praça da Lemanha (Kaculuvale)\n2. Praça do Xomucuio\n\nResponda com o número (1 ou 2)."
                elif opcao == "6": ESTADO_NAVEGACAO.pop(telefone_origem); return "⚠️ *Cheias e Clima — Cunene*\n\n🌍 Clima: Árido a semi-árido\n☀️ Seca: Março a Outubro\n🌧️ Chuvosa: Novembro a Fevereiro\n\nDiga 'tempo' para meteorologia."
                elif opcao == "7": ESTADO_NAVEGACAO[telefone_origem]["nivel"] = "agricultura_submenu"; return "🌾 *Agricultura e Pecuária — Cunene*\n\nA - Agricultura\nB - Pecuária\nC - Pesca Artesanal\nD - Recursos Minerais\nE - Solo e Vegetação\n\nResponde com a letra."
                elif opcao == "8": ESTADO_NAVEGACAO.pop(telefone_origem); return "🏛️ *Serviços Administrativos*\n\nA - Bilhete de Identidade\n\nResponde com a letra."
            else: ESTADO_NAVEGACAO.pop(telefone_origem)
        elif nivel == "agricultura_submenu":
            opcao = texto_baixo.upper().strip(); ESTADO_NAVEGACAO.pop(telefone_origem)
            if opcao == "A": return AGRICULTURA_INFO
            elif opcao == "B": return PECUARIA_INFO
            elif opcao == "C": return PESCA_INFO
            elif opcao == "D": return MINERAIS_INFO
            elif opcao == "E": return SOLO_VEGETACAO_INFO
        elif nivel == "info_submenu":
            opcao = texto_baixo.upper().strip()
            if opcao in ["A", "B", "C", "D", "E", "F"]:
                if opcao == "A": ESTADO_NAVEGACAO.pop(telefone_origem); return "🏛️ *Administração Pública*\n\n🕐 Seg-Qui 08h-15h30 | Sex 08h-15h\n\n📍 Bangula: Governo Provincial, Tribunal, AGT\n📍 Kaculuvale: Administração Provincial, Mediateca, Aeroporto\n📍 Castilhos: Comando Municipal, SIC\n📍 Naipalala: Viação, Bombeiros, Polícia Fiscal"
                elif opcao == "B": ESTADO_NAVEGACAO[telefone_origem]["nivel"] = "saude_submenu"; return "🏥 *Saúde — Escolhe a opção:*\n\nA - Hospitais\nB - Horários de Atendimento\nC - Campanhas de Vacinação\nD - Doenças e Prevenção\n\nResponde com a letra."
                elif opcao == "C": ESTADO_NAVEGACAO[telefone_origem]["nivel"] = "ensino_submenu"; return "📚 *Ensino — Escolhe a opção:*\n\nA - Escolas\nB - Matrícula\n\nResponde com a letra."
                elif opcao == "D": ESTADO_NAVEGACAO.pop(telefone_origem); return "Bancos Seg-Sex 08h-15h. BAI, BFA, BIC, BCI, BPC, Sol, Económico (Bangula); BPC2, Atlântico (Naipalala)."
                elif opcao == "E": ESTADO_NAVEGACAO.pop(telefone_origem); return "Shoprite e AngoMarte (Castilhos) abertos Seg-Sáb 08h-20h, Dom 08h-13h30."
                elif opcao == "F": ESTADO_NAVEGACAO.pop(telefone_origem); nomes = [m["nome"] for m in MUNICIPIOS_CUNENE]; return f"A província do Cunene tem *14 municípios*:\n{', '.join(nomes)}.\n\nPara lista completa: *lista completa dos municípios*."
            else: ESTADO_NAVEGACAO.pop(telefone_origem)
        elif nivel == "saude_submenu":
            opcao = texto_baixo.upper().strip()
            if opcao == "A": ESTADO_NAVEGACAO.pop(telefone_origem); ESTADO_LISTA[telefone_origem] = {"tipo": "hospitais", "dados": list(HOSPITAIS_ONDJIVA.keys())}; return listar_todos_hospitais()
            elif opcao == "B": ESTADO_NAVEGACAO.pop(telefone_origem); return "🕐 *Horários de Atendimento*\n\n🚨 Urgências: 24h\n🏥 Consultas: Seg-Sex 08h-15h\n🏪 Postos médicos em todos os bairros."
            elif opcao == "C": ESTADO_NAVEGACAO.pop(telefone_origem); return "💉 *Campanhas de Vacinação*\n\nAtualmente não há campanhas ativas. Qualquer novidade, informarei aqui. 😊"
            elif opcao == "D": ESTADO_NAVEGACAO[telefone_origem]["nivel"] = "doencas_submenu"; return "🩺 *Doenças e Prevenção*\n\nA - Malária\nB - Doenças Diarreicas/Febre Tifóide\nC - Dracunculose\nD - Doenças Respiratórias\nE - Malnutrição\nF - VIH/Sida\n\nResponde com a letra."
            else: ESTADO_NAVEGACAO.pop(telefone_origem)
        elif nivel == "doencas_submenu":
            opcao = texto_baixo.upper().strip(); ESTADO_NAVEGACAO.pop(telefone_origem)
            if opcao == "A": return MALARIA_INFO
            elif opcao == "B": return DDA_INFO
            elif opcao == "C": return DRACUNCULOSE_INFO
            elif opcao == "D": return DRA_INFO
            elif opcao == "E": return MALNUTRICAO_INFO
            elif opcao == "F": return VIH_INFO
        elif nivel == "ensino_submenu":
            opcao = texto_baixo.upper().strip(); ESTADO_NAVEGACAO.pop(telefone_origem)
            if opcao == "A": return "📚 *Escolas em Ondjiva*\n\n🏫 *Públicas:* ITSO, Eiffel, Oulondelo, IMPO, CESMO, ITAS\n🎓 *Privadas:* Pitágoras, Ednas, Popiene, Arcanjo, Marc Leandres, Bulet Salú, Abcunene"
            elif opcao == "B": return handler_matricula("matricula")
        elif nivel == "localizacao_pedido":
            local_desejado = texto_baixo; ESTADO_NAVEGACAO.pop(telefone_origem)
            for chave, dados in COORDENADAS_ONDJIVA.items():
                if chave in local_desejado: enviar_localizacao_whatsapp(telefone_origem, dados["lat"], dados["lon"], dados["nome"], dados["endereco"]); return f"📍 *{dados['nome']}*\n{dados['endereco']}\n\n💡 Clica no Pin e depois em *'Como chegar'*."
            return "❌ Ainda não tenho a localização exata desse local. Tenta perguntar pelo nome completo."

    # LOCALIZAÇÃO
    if any(p in texto_baixo for p in ["onde fica", "localização de", "localizacao de", "localização do"]):
        for chave, dados in COORDENADAS_ONDJIVA.items():
            if chave in texto_baixo: enviar_localizacao_whatsapp(telefone_origem, dados["lat"], dados["lon"], dados["nome"], dados["endereco"]); return f"📍 *{dados['nome']}*\n{dados['endereco']}\n\n💡 Clica no Pin e depois em *'Como chegar'*."
        return "❌ Ainda não tenho a localização exata desse local."

    # ROTA
    if any(p in texto_baixo for p in ["como chegar", "rota", "caminho", "trajeto"]):
        for chave, dados in COORDENADAS_ONDJIVA.items():
            if chave in texto_baixo: ESTADO_ROTA[telefone_origem] = dados; return f"🗺️ *{dados['nome']}*\n\n📍 Partilha a tua localização para eu gerar a rota."

    # HANDLERS BLINDADOS
    if any(p in texto_baixo for p in ["história", "historia", "cultura", "tradição", "gastronomia", "mandume", "gado", "pastor", "funge", "maiavi", "chacota"]):
        resposta = handler_historia_cultura(texto_baixo)
        if resposta: return resposta
    if any(p in texto_baixo for p in ["doença", "doenca", "malária", "malaria", "diarreia", "tifóide", "dracunculose", "verme", "respiratória", "pneumonia", "malnutrição", "vih", "sida", "hiv"]):
        resposta = handler_doencas(texto_baixo)
        if resposta: return resposta
    if "hospital" in texto_baixo or "ekuma" in texto_baixo or "simeone" in texto_baixo or "mucunde" in texto_baixo:
        resposta = handler_hospitais(texto_baixo, telefone_origem)
        if resposta: return resposta
    if any(p in texto_baixo for p in ["escola", "colégio", "colegio", "liceu", "instituto", "curso", "itso", "impo", "itas", "eiffel", "cesmo", "oulondelo"]):
        resposta = handler_escolas(texto_baixo, telefone_origem)
        if resposta: return resposta
    if any(p in texto_baixo for p in ["governo", "tribunal", "agt", "administração", "mediateca", "aeroporto", "comando", "sic", "viação", "bombeiros", "fiscal", "guarda"]):
        resposta = handler_administracao(texto_baixo)
        if resposta: return resposta
    if any(p in texto_baixo for p in ["shoprite", "angomarte", "comércio", "comercio", "supermercado"]):
        resposta = handler_comercio(texto_baixo)
        if resposta: return resposta
    if any(p in texto_baixo for p in ["mercado", "praça", "praca", "feira", "lemanha", "xomucuio", "xamucuio", "preço", "preco", "fuba"]):
        resposta = handler_mercados(texto_baixo, telefone_origem)
        if resposta: return resposta
    if any(p in texto_baixo for p in ["cheia", "cheias", "inundação", "alagamento", "alerta", "chuva", "chuvosa", "clima", "seca"]):
        resposta = handler_cheias_alertas(texto_baixo)
        if resposta: return resposta
    palavras_municipios = ["município", "municipio", "comuna", "cahama", "cuanhama", "curoca", "cuvelai", "namacunde", "ombadja", "chiéde", "nehone", "humbe", "mupa", "naulila", "chitado", "cafima", "chissuata", "administrador"]
    palavras_lingua = ["língua", "lingua", "falar", "dizer", "olá", "idioma", "dialeto", "aprender", "traduzir"]
    if any(p in texto_baixo for p in palavras_municipios) and not any(p in texto_baixo for p in palavras_lingua):
        resposta = handler_municipios(texto_baixo)
        if resposta: return resposta

    # MENU
    if texto_baixo in ["menu", "ajuda", "help", "guia", "opções", "opcoes", "início", "inicio"]:
        ESTADO_NAVEGACAO[telefone_origem] = {"nivel": "menu"}; ESTADO_LISTA.pop(telefone_origem, None)
        return "📋 *Menu Principal — Bot Cunene*\n\n1️⃣ Reportar problema\n2️⃣ Localização de locais\n3️⃣ Informações oficiais\n4️⃣ Emergências\n5️⃣ Mercado\n6️⃣ Cheias e alertas\n7️⃣ Agricultura e Pecuária\n8️⃣ Serviços Administrativos\n\nResponde com o número ou faz uma pergunta directa. ✨"

    # REPORTAGEM
    if texto_baixo.startswith("reportagem") or any(p in texto_baixo for p in ["quero reportar", "reportar um problema"]):
        if not texto_baixo.startswith("reportagem"): ESTADO_REPORTAGEM[telefone_origem] = {'passo': 1, 'problema': '', 'tempo': '', 'causa': '', 'inicio': datetime.utcnow()}; return "📝 *Reportagem*\n\nDescreve o problema."
        problema = user_text.strip()[10:].strip()
        if not problema: return "Escreve *Reportagem* seguido do problema."
        ESTADO_REPORTAGEM[telefone_origem] = {'passo': 1, 'problema': problema, 'tempo': '', 'causa': '', 'inicio': datetime.utcnow()}
        return f"📝 *Ocorrência:* {problema}\nHá quanto tempo?"
    if telefone_origem in ESTADO_REPORTAGEM:
        dados = ESTADO_REPORTAGEM[telefone_origem]
        if (datetime.utcnow() - dados['inicio']).total_seconds() > 900: ESTADO_REPORTAGEM.pop(telefone_origem); return "⏳ Reportagem cancelada."
        if dados['passo'] == 1: dados['tempo'] = user_text.strip(); dados['passo'] = 2; return "Obrigado. *O que causou essa situação?*"
        elif dados['passo'] == 2:
            dados['causa'] = user_text.strip(); relato = f"PROBLEMA: {dados['problema']} | DURAÇÃO: {dados['tempo']} | CAUSA: {dados['causa']}"
            guardar_reportagem_bd(telefone_origem, relato); ESTADO_REPORTAGEM.pop(telefone_origem)
            return f"✅ *Ocorrência enviada!*\n• {dados['problema']}\n• Duração: {dados['tempo']}\n• Causa: {dados['causa']}\n\nEscreve *menu*."

    # FORA DO CONTEXTO
    if any(p in texto_baixo for p in ["android", "iphone", "messi", "ronaldo", "neymar", "futebol", "biologia", "física", "química", "matemática", "filme", "música", "guerra", "presidente", "carro", "avião", "receita", "significado"]):
        return "Sou o *Bot Cunene*, assistente da província do Cunene. 🇦🇴\n\nPara informações sobre o Cunene, diga *menu* ou faça a sua pergunta diretamente."

    # IA (FALLBACK)
    try:
        if not client: return "Serviço temporariamente indisponível."
        if telefone_origem not in MEMORIA_CONVERSAS: MEMORIA_CONVERSAS[telefone_origem] = []
        MEMORIA_CONVERSAS[telefone_origem].append({"role": "user", "content": user_text})
        if len(MEMORIA_CONVERSAS[telefone_origem]) > 16: MEMORIA_CONVERSAS[telefone_origem] = MEMORIA_CONVERSAS[telefone_origem][-16:]
        agora = datetime.utcnow() + timedelta(hours=1)
        saudacao = "Bom dia" if 5 <= agora.hour < 12 else "Boa tarde" if 12 <= agora.hour < 18 else "Boa noite"
        regra_relogio = f"\n\nHoje: {agora.strftime('%d/%m/%Y')}, {agora.strftime('%H:%M')}.\n"
        if len(MEMORIA_CONVERSAS[telefone_origem]) <= 2: regra_relogio += f"Podes usar '{saudacao}'."
        else: regra_relogio += "Responde diretamente."
        contexto = CONTEXTO_ONDJIVA + regra_relogio
        mensagens_ia = [{"role": "system", "content": contexto}] + MEMORIA_CONVERSAS[telefone_origem]
        response = client.chat.completions.create(model="llama-3.1-8b-instant", temperature=0.0, messages=mensagens_ia)
        resposta_ia = response.choices[0].message.content.strip()
        MEMORIA_CONVERSAS[telefone_origem].append({"role": "assistant", "content": resposta_ia})
        if len(resposta_ia) > 3800: enviar_mensagens_partidas(telefone_origem, resposta_ia); return ""
        return resposta_ia
    except Exception as e: print(f"Erro IA: {e}"); return "Peço desculpa, estou com uma dificuldade técnica. Se for urgente, liga 113 ou 115."

def processar_localizacao(telefone_origem, lat_origem, lon_origem):
    if telefone_origem in ESTADO_ROTA:
        destino = ESTADO_ROTA[telefone_origem]; link = f"https://www.google.com/maps/dir/?api=1&origin={lat_origem},{lon_origem}&destination={destino['lat']},{destino['lon']}&travelmode=driving"
        ESTADO_ROTA.pop(telefone_origem, None); return f"🚗 *Rota para {destino['nome']}*\n\n👉 {link}"
    return "📍 Recebi a tua localização! Para calcular rota, escreve 'Como chegar a [local]'."

# ==========================================
# FLASK
# ==========================================
@app.route('/')
def home(): return "Bot Cunene operacional.", 200

@app.route('/health')
def health(): return "OK", 200

@app.route('/webhook', methods=['GET'])
def verificar():
    mode = request.args.get("hub.mode"); token = request.args.get("hub.verify_token"); challenge = request.args.get("hub.challenge")
    if mode and token and mode == "subscribe" and token == VERIFY_TOKEN: return challenge, 200
    return "Falha na verificação", 403

@app.route('/webhook', methods=['POST'])
def webhook():
    global ULTIMA_ATIVIDADE, MENSAGENS_PROCESSADAS
    agora = datetime.utcnow()
    if (agora - ULTIMA_ATIVIDADE).total_seconds() > 30: time.sleep(2); ULTIMA_ATIVIDADE = datetime.utcnow()
    body = request.get_json()
    if body and body.get("object"):
        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                if "messages" in value:
                    for msg in value["messages"]:
                        msg_id = msg.get("id", ""); timestamp = msg.get("timestamp", ""); chave_unica = f"{msg_id}_{timestamp}"
                        agora = datetime.utcnow()
                        if chave_unica in MENSAGENS_PROCESSADAS and (agora - MENSAGENS_PROCESSADAS[chave_unica]).total_seconds() < 30: continue
                        MENSAGENS_PROCESSADAS[chave_unica] = agora
                        for k in [k for k, v in MENSAGENS_PROCESSADAS.items() if (agora - v).total_seconds() > 300]: del MENSAGENS_PROCESSADAS[k]
                        ULTIMA_ATIVIDADE = agora; tel = msg["from"]
                        if msg["type"] == "text":
                            resposta = processar_texto(tel, msg["text"]["body"])
                            if resposta: enviar_mensagem_whatsapp(tel, resposta)
                        elif msg["type"] == "location":
                            resposta = processar_localizacao(tel, msg["location"]["latitude"], msg["location"]["longitude"])
                            if resposta: enviar_mensagem_whatsapp(tel, resposta)
    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
