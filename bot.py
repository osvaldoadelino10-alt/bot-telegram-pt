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
ESTADO_LISTA = {}
ULTIMA_MENSAGEM_BOT = {}

# Controlo de mensagens duplicadas e cold start
MENSAGENS_PROCESSADAS = {}
ULTIMA_ATIVIDADE = datetime.utcnow()

# ==========================================
# COORDENADAS DE ONDJIVA
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
# BASE DE DADOS - HOSPITAIS
# ==========================================
HOSPITAIS_ONDJIVA = {
    "hospital provincial ekuma": {
        "nome": "Hospital Provincial Ekuma",
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
    "hospital ekuma": "hospital provincial ekuma",
    "hospital provincial da ekuma": "hospital provincial ekuma",
    "hospital provincial do ekuma": "hospital provincial ekuma",
    "ekuma": "hospital provincial ekuma",
    "hospital do ekuma": "hospital provincial ekuma",
    "simeone mucunde": "hospital central simeone mucunde",
    "hospital central": "hospital central simeone mucunde",
    "hospital municipal": "hospital municipal de ondjiva",
    "hospital do bangula": "hospital municipal de ondjiva",
    "hospital de ondjiva": "hospital municipal de ondjiva",
}

# ==========================================
# BASE DE DADOS - ESCOLAS PÚBLICAS
# ==========================================
ESCOLAS_PUBLICAS = {
    "instituto de saúde de ondjiva": {
        "nome": "Instituto Técnico de Saúde de Ondjiva (ITSO)",
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
    "itso": "instituto de saúde de ondjiva",
    "iso": "instituto de saúde de ondjiva",
    "instituto de saúde": "instituto de saúde de ondjiva",
    "instituto técnico de saúde": "instituto de saúde de ondjiva",
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
        "horario": "Todos os dias, das primeiras horas da manhã até ao final da tarde"
    },
    "praça do xomucuio": {
        "nome": "Praça do Xomucuio",
        "bairro": "Ondjiva",
        "tipo": "Mercado/Praça",
        "produtos": ["Fuba", "Milho", "Arroz", "Massa", "Frango", "Peixe", "Tomate", "Cebola", "Alho", "Batata", "Feijão", "Óleo", "Sal", "Açúcar"],
        "horario": "Todos os dias, das primeiras horas da manhã até ao final da tarde"
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
        "descricao": "Chuvas mais frequentes e intensas. As cheias do Rio Cunene são recorrentes nesta época.",
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

# ==========================================
# BASE DE DADOS - HISTÓRIA E CULTURA
# ==========================================
HISTORIA_CUNENE = """
🏛️ *História da Província do Cunene*

🗿 *Raízes:* A região é historicamente habitada pelos povos Nyaneka-Humbe e Ovambo (Cuanhama).

👑 *Rei Mandume ya Ndemufayo:* Figura central da resistência anticolonial do povo Cuanhama. Lutou contra a ocupação colonial portuguesa no início do século XX. É um símbolo de coragem e resistência para todo o Cunene.

🐄 *Pastorícia:* A criação de gado bovino é a base da economia tradicional e símbolo de prestígio social.

🍽️ *Gastronomia típica:*
• Funge - massa de massango ou milho
• Maiavi - leite azedo
• Chacota - carne seca

🏛️ *Capital:* Ondjiva, município de Cuanhama.

📜 *Província:* O Cunene é uma das 21 províncias de Angola, situada no extremo SUL do país, fazendo fronteira com a Namíbia.
"""

CULTURA_CUNENE = """
🎭 *Cultura do Cunene*

🗣️ *Línguas:* O Cuanhama (dialeto Ovambo) é a língua nacional predominante, além do Português.

👥 *Povos:* Nyaneka-Humbe e Ovambo (Cuanhama).

🐄 *Pastorícia:* Atividade central na cultura local. O gado representa riqueza e status social.

🍽️ *Pratos típicos:*
• Funge de massango/milho
• Maiavi (leite azedo)
• Chacota (carne seca)
"""

# ==========================================
# BASE DE DADOS - AGRICULTURA E PECUÁRIA
# ==========================================
AGRICULTURA_INFO = """
🌱 *Agricultura no Cunene*

🌾 *Principais culturas:* Milho, massango, massambala, trigo, feijão, algodão, cana-de-açúcar, citrinos, videira, tabaco e horticultura.

📊 *Produção:* A agricultura é do tipo sequeiro, baseada nas culturas de massango e massambala. Existem 51.650 lavras familiares com uma superfície de 77.475 hectares, dos quais 43% são cultivados anualmente, ficando o restante em pousio.

💡 A atividade agrícola ainda é pouco desenvolvida devido aos solos pouco propícios e ao clima tropical seco.
"""

PECUARIA_INFO = """
🐄 *Pecuária no Cunene*

🐂 *Principal atividade económica:* O Cunene possui mais de 1.000.000 de cabeças de gado bovino, sendo a maior atividade produtiva da província.

🐑 *Outros animais:* Ovinos Caracul e caprinos.

📋 *Regime:* A maior parte do gado está nas mãos de criadores tradicionais, mantido em regime extensivo com aproveitamento de pastagens naturais. A disponibilidade de água e a carga de pastos condicionam a deslocação das manadas para zonas de transumância.
"""

PESCA_INFO = """
🎣 *Pesca Artesanal no Cunene*

🐟 A pesca artesanal é praticada principalmente no Rio Cunene, desempenhando um papel importante no fornecimento de peixe às populações rurais e na melhoria da dieta alimentar das comunidades.

⚠️ Os índices de captura são baixos devido ao fraco apoio em artefatos de pesca (linhas, anzóis, boias, chumbos, redes, etc.).
"""

MINERAIS_INFO = """
⛏️ *Recursos Minerais do Cunene*

💎 *Minerais predominantes:* Ferro, Cobre, Ouro e Mica.

📋 A exploração da madeira é a única indústria digna de realce, além da infraestrutura relacionada com a pecuária.
"""

SOLO_VEGETACAO_INFO = """
🌍 *Solo e Vegetação do Cunene*

🏜️ *Clima:* Tropical seco, com temperatura média de 20°C.

🌿 *Vegetação:* Savana, com a seguinte distribuição:
• 46% - Floresta seca com árvores, arbustos e gemineis
• 23% - Zona árida de solo argiloso com árvores e gramíneas
• 20% - Gramíneas de fraco valor nutritivo com árvores espinhosas

🪨 *Solo:* Natureza sedimentar com afloramentos pré-câmbricos na parte ocidental. 11% da superfície coberta por rochas corruptivas e metamórficas.
"""

# ==========================================
# BASE DE DADOS - DOENÇAS E PREVENÇÃO
# ==========================================
MALARIA_INFO = """🦟 *Malária — Prevenção*

• Dormir sempre com mosquiteiros impregnados com inseticida de longa duração.
• Aplicar repelente na pele exposta.
• Permitir a pulverização intra-domiciliar (paredes de casa) pelas equipas de saúde.
• Eliminar águas paradas ao redor de casa (pneus, latas, poças) que servem de criatórios para larvas do mosquito.
• Grávidas devem receber antimaláricos preventivos nas consultas pré-natais."""

DDA_INFO = """💧 *Doenças Diarreicas Agudas e Febre Tifóide — Prevenção*

• Beber apenas água fervida ou tratada com lixívia/cloro ou pastilhas de purificação.
• Lavar rigorosamente as mãos com água segura e sabão após usar o quarto de banho, antes de cozinhar e antes de comer.
• Lavar muito bem as frutas e legumes.
• Consumir alimentos bem cozinhados e manter a comida protegida de moscas."""

DRACUNCULOSE_INFO = """🪱 *Dracunculose (Verme da Guiné) — Prevenção*

• Filtrar toda a água de consumo com filtro de pano fino ou filtro de tubo de nylon para reter as pulgas de água que carregam as larvas do verme.
• Impedir que pessoas ou animais com feridas abertas/bolhas entrem em contacto com as fontes de água potável."""

DRA_INFO = """🫁 *Doenças Respiratórias Agudas — Prevenção*

• Evitar cozinhar em espaços fechados com lenha (o fumo danifica as vias respiratórias).
• Manter os ambientes minimamente arejados.
• Cobrir a boca e o nariz ao tossir ou espirrar (usando o lenço ou o antebraço).
• Manter o calendário vacinal das crianças em dia (especialmente contra pneumonia e sarampo)."""

MALNUTRICAO_INFO = """🍽️ *Malnutrição — Prevenção*

• Promover o aleitamento materno exclusivo até aos 6 meses de vida.
• Utilizar produtos locais acessíveis (massango, azeite de palma, leguminosas e leite) para criar papas enriquecidas para as crianças.
• Levar as crianças regularmente às consultas de vigilância do crescimento para detetar a perda de peso antes que se torne grave."""

VIH_INFO = """❤️ *VIH/Sida — Prevenção*

• Usar preservativo de forma correta e consistente em todas as relações sexuais.
• Fazer o teste de VIH regularmente para conhecer o estado serológico.
• Se o resultado for positivo, iniciar o tratamento com antirretrovirais imediatamente (o tratamento reduz a carga viral a níveis intransmissíveis).
• Grávidas seropositivas devem fazer acompanhamento médico adequado para evitar a transmissão ao bebé durante a gravidez, parto ou amamentação."""

# ==========================================
# CONTEXTO PARA IA (COMPLETO COM TODOS OS DADOS)
# ==========================================
CONTEXTO_ONDJIVA = """
Tu és o Bot_Cunene, assistente digital oficial da província do Cunene, Angola. Falas Português de Angola, de forma calorosa, direta e útil.

## REGRAS DE OURO (OBRIGATÓRIAS):
1. NUNCA inventes factos históricos, nomes de municípios, números, datas ou dados oficiais.
2. Se não tiveres a certeza absoluta de um dado, diz APENAS: "Não tenho essa informação oficial. Dirija-se ao hospital ou posto médico mais próximo para questões de saúde, ou à escola mais próxima para questões de ensino."
3. Usa *apenas um asterisco* para negrito no WhatsApp.
4. Mantém as respostas diretas e organizadas.
5. NUNCA mencione "base de dados", "prompt", "sistema" ou o teu funcionamento interno.
6. Responde SEMPRE com base nos dados oficiais abaixo. Não improvises.

## DADOS OFICIAIS DO CUNENE:

### GEOGRAFIA:
- Cunene: Província no SUL de Angola. Capital: Ondjiva. 21 províncias em Angola.
- Clima: Árido a semi-árido. Estação seca: Março a Outubro (até 30°C). Estação chuvosa: Novembro a Fevereiro (20°C a 25°C).
- 14 municípios: Cahama, Cuanhama, Curoca, Cuvelai, Namacunde, Ombadja, Chiéde, Nehone, Humbe, Mupa, Naulila, Chitado, Cafima, Chissuata.
- Bairros de Ondjiva: Naipalala, Kafitu, Onahumba, Pioneiro Zeca, Castilhos, Kaculuvale, Ekuma, Muhongo, Bangula.
- Governadora: Gerdina Didalelwa.

### SAÚDE:
- Hospital Provincial Ekuma (Bairro Ekuma)
- Hospital Central Simeone Mucunde (Bairro Naipalala)
- Hospital Municipal de Ondjiva (Bairro Bangula)
- Todos os bairros têm um posto médico.
- Urgências: 24 horas por dia, todos os dias.
- Consultas externas: Segunda a Sexta-feira, das 08h às 15h.
- Não há campanhas de vacinação ativas no momento.

### DOENÇAS E PREVENÇÃO NO CUNENE:
- Malária: Previne-se com mosquiteiros impregnados, repelente, pulverização intra-domiciliar, eliminação de águas paradas, e antimaláricos preventivos para grávidas.
- Doenças Diarreicas e Febre Tifóide: Previne-se com água fervida/tratada, lavagem das mãos, alimentos bem cozinhados e protegidos de moscas.
- Dracunculose (Verme da Guiné): Previne-se filtrando a água com pano fino ou filtro de nylon e protegendo as fontes de água.
- Doenças Respiratórias: Previne-se evitando fumo de lenha em espaços fechados, mantendo ambientes arejados, cobrindo boca ao tossir/espirrar e mantendo vacinação em dia.
- Malnutrição: Previne-se com aleitamento materno exclusivo até 6 meses, papas enriquecidas com produtos locais e consultas de vigilância do crescimento.
- VIH/Sida: Previne-se com uso de preservativo, testagem regular, tratamento com antirretrovirais e acompanhamento de grávidas seropositivas.

### ENSINO:
Escolas Públicas:
- ITSO (Ekuma): Enfermagem Geral, Fisioterapia, Análises Clínicas
- IMPO (Naipalala): Matemática e Física, Ensino Primário, EMC, Língua Portuguesa, Bio-Química
- ITAS (Naipalala): Finanças, Secretariado, Contabilidade, Gestão Empresarial, RH
- Oulondelo (Naipalala): Ciências Físicas e Biológicas, Ciências Económicas e Jurídicas
- Eiffel (Naipalala): Ciências Físicas e Biológicas
- CESMO (Kaculuvale): Ciências Físicas e Biológicas, Ciências Económicas e Jurídicas

Colégios Privados:
- Pitágoras (Naipalala): Farmácia, Informática, Eletricidade, Enfermagem, Análises Clínicas
- Ednas (Kaculuvale): Ciências Físicas/Biológicas, Económicas/Jurídicas
- Popiene (Kaculuvale): Só ensino primário
- Arcanjo (Naipalala): Enfermagem Geral, Análises Clínicas
- Marc Leandres (Kaculuvale): Só primário e 1º ciclo
- Bulet Salú 1 (Naipalala) e 2 (Zeca): Ciências Humanas, Eletricidade
- Abcunene (Caxila 3): Enfermagem Geral, Análises Clínicas, Informática

Turnos: Manhã 07h-12h30, Tarde 13h-18h05, Noite 18h-22h30.

MATRÍCULAS:
- Período: Julho/Agosto.
- Iniciação e Ensino Primário: Bilhete ou cédula de nascimento + Duas fotos tipo passe.
- 1º Ciclo: Cópia do bilhete + Duas fotos + Certificado de conclusão do ensino primário.
- Ensino Médio: Cópia do bilhete + Duas fotos + Certificado de conclusão do 1º ciclo.

### CULTURA:
- Povos: Nyaneka-Humbe e Ovambo (Cuanhama).
- Rei Mandume ya Ndemufayo: Líder da resistência anticolonial.
- Gastronomia: Funge (massa de massango/milho), Maiavi (leite azedo), Chacota (carne seca).
- Pastorícia: Base da economia tradicional. Mais de 1 milhão de cabeças de gado bovino.

### AGRICULTURA E PECUÁRIA:
- Culturas: Milho, massango, massambala, trigo, feijão, algodão, cana-de-açúcar, citrinos, videira, tabaco.
- 51.650 lavras familiares, 77.475 hectares.
- Pecuária: 1.000.000+ cabeças de gado bovino, ovinos Caracul, caprinos.
- Pesca artesanal no Rio Cunene.
- Minerais: Ferro, Cobre, Ouro, Mica.
- Vegetação: Savana (46% florestal, 23% árida, 20% gramíneas).

### ADMINISTRAÇÃO PÚBLICA:
- Horário: Seg-Qui 08h-15h30, Sex 08h-15h.
- Bangula: Governo Provincial, Tribunal, AGT.
- Kaculuvale: Administração Provincial, Mediateca, Aeroporto.
- Castilhos: Comando Municipal, SIC.
- Naipalala: Viação e Trânsito, Bombeiros, Polícia Fiscal.

### COMÉRCIO:
- Shoprite (Castilhos): Seg-Sáb 08h-20h, Dom 08h-13h30.
- AngoMarte (Castilhos): Seg-Sáb 08h-20h, Dom 08h-13h30.

### MERCADOS:
- Praça da Lemanha (Kaculuvale)
- Praça do Xomucuio
- Produtos: Fuba, milho, arroz, massa, frango, peixe, tomate, cebola, alho, batata, feijão, óleo, sal, açúcar.
- Preços variam conforme a época.

### BANCOS:
- Horário: Seg-Sex 08h-15h.
- BAI, BFA, BIC, BCI, BPC, Sol, Económico (Bangula); BPC2, Atlântico (Naipalala).

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
    global MENSAGENS_PROCESSADAS
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
            ESTADO_LISTA.pop(tel, None)
            ULTIMA_MENSAGEM_BOT.pop(tel, None)
        if len(MENSAGENS_PROCESSADAS) > 500:
            MENSAGENS_PROCESSADAS.clear()

threading.Thread(target=limpar_memoria_antiga, daemon=True).start()

# ==========================================
# HANDLERS
# ==========================================

def handler_cuanhama(texto_baixo):
    if texto_baixo in ["wa aluka", "wa aluka po", "aluka"]:
        agora = datetime.utcnow() + timedelta(hours=1)
        hora = agora.hour
        if 5 <= hora < 12:
            return "Wa aluka! ☀️ *Bot Cunene* ove li po. (Bom dia! Escreve *menu* para veres as opções.)"
        elif 12 <= hora < 18:
            return "Wa aluka! 🌤️ *Bot Cunene* ove li po. (Boa tarde! Escreve *menu* para veres as opções.)"
        else:
            return "Wa aluka! 🌙 *Bot Cunene* ove li po. (Boa noite! Escreve *menu* para veres as opções.)"
    if "ame ove" in texto_baixo or "ou li tutu" in texto_baixo:
        return "Ondei! 😊 *Tangi* (Estou bem! Obrigado. Escreve *menu*.)"
    if texto_baixo in ["tangi", "nda pandula"]:
        return "Ka li na shilwe! 🙏 (De nada! Escreve *menu* se precisares.)"
    if texto_baixo in ["eeno", "eyo"]:
        return "Eeno! 😊 Como posso ajudar? Escreve *menu*."
    if texto_baixo in ["ahawe", "kawe"]:
        return "Ahawe, tudo bem! Escreve *menu* se precisares."
    if texto_baixo in ["ka kala po nawa", "shilwe"]:
        return "Ka kala po nawa! 👋 (Adeus! Volta sempre.)"
    return None

def handler_conversa_casual(texto_baixo):
    if texto_baixo in ["oi", "olá", "ola", "oie", "hey", "ei"]:
        agora = datetime.utcnow() + timedelta(hours=1)
        hora = agora.hour
        if 5 <= hora < 12:
            saudacao = "Bom dia"
        elif 12 <= hora < 18:
            saudacao = "Boa tarde"
        else:
            saudacao = "Boa noite"
        return f"{saudacao}! 👋 Sou o *Bot Cunene*, assistente digital de Ondjiva. Escreve *menu* para veres as opções."
    if texto_baixo in ["bom dia", "boa tarde", "boa noite"]:
        return f"{texto_baixo.capitalize()}! 👋 Sou o *Bot Cunene*. Escreve *menu* para veres as opções disponíveis."
    if any(p in texto_baixo for p in ["como estás", "como estas", "tudo bem", "como vai", "tudo bom"]):
        return "Estou bem, obrigado! 😊 Escreve *menu* para veres o que posso fazer por ti."
    if any(p in texto_baixo for p in ["obrigado", "obrigada", "valeu", "brigado", "obg"]):
        return "De nada! 😊 Se precisares de mais alguma coisa, escreve *menu*."
    if texto_baixo in ["sim", "s", "yes", "y"]:
        return "Sim! 😊 Como posso ajudar? Escreve *menu*."
    if texto_baixo in ["não", "nao", "n", "no"]:
        return "Tudo bem! Se mudares de ideias, escreve *menu*."
    return None

def handler_historia_cultura(texto_baixo):
    if any(p in texto_baixo for p in ["história", "historia", "origem", "passado", "antigamente", "colonial"]):
        if "mandume" in texto_baixo or "rei" in texto_baixo:
            return "👑 *Rei Mandume ya Ndemufayo*\n\nGrande líder do povo Cuanhama, símbolo da resistência anticolonial no Cunene. Lutou contra a ocupação colonial portuguesa no início do século XX."
        return HISTORIA_CUNENE
    if any(p in texto_baixo for p in ["cultura", "tradição", "tradicao", "costume", "hábito", "habito"]):
        return CULTURA_CUNENE
    if any(p in texto_baixo for p in ["gastronomia", "comida", "prato", "alimentação", "alimentacao", "funge", "maiavi", "chacota"]):
        return "🍽️ *Gastronomia do Cunene*\n\n• *Funge:* Massa de massango ou milho.\n• *Maiavi:* Leite azedo tradicional.\n• *Chacota:* Carne seca ao sol.\n\nPratos típicos dos povos Nyaneka-Humbe e Ovambo."
    if "mandume" in texto_baixo:
        return "👑 *Rei Mandume ya Ndemufayo*\n\nGrande líder do povo Cuanhama, símbolo da resistência anticolonial no Cunene."
    if any(p in texto_baixo for p in ["gado", "boi", "pastorícia", "pastoricia", "pastor"]):
        return "🐄 *Pastorícia no Cunene*\n\nA criação de gado bovino é a base da economia tradicional e símbolo de prestígio social dos povos Nyaneka-Humbe e Ovambo."
    return None

def handler_doencas(texto_baixo):
    if "malária" in texto_baixo or "malaria" in texto_baixo:
        return MALARIA_INFO
    if "diarreica" in texto_baixo or "diarreia" in texto_baixo or "tifóide" in texto_baixo or "tifoide" in texto_baixo:
        return DDA_INFO
    if "dracunculose" in texto_baixo or "verme" in texto_baixo or "guiné" in texto_baixo or "guine" in texto_baixo:
        return DRACUNCULOSE_INFO
    if "respiratória" in texto_baixo or "respiratoria" in texto_baixo or "tosse" in texto_baixo or "pneumonia" in texto_baixo:
        return DRA_INFO
    if "malnutrição" in texto_baixo or "malnutricao" in texto_baixo or "desnutrição" in texto_baixo or "desnutricao" in texto_baixo or "fome" in texto_baixo:
        return MALNUTRICAO_INFO
    if "vih" in texto_baixo or "sida" in texto_baixo or "hiv" in texto_baixo or "preservativo" in texto_baixo:
        return VIH_INFO
    if "doença" in texto_baixo or "doenca" in texto_baixo or "prevenção" in texto_baixo or "prevencao" in texto_baixo:
        return "🩺 *Doenças e Prevenção no Cunene*\n\nEscolhe a doença:\n• Malária\n• Doenças Diarreicas e Febre Tifóide\n• Dracunculose (Verme da Guiné)\n• Doenças Respiratórias\n• Malnutrição\n• VIH/Sida\n\nDigite o nome da doença para mais informações."
    return None

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
            return HOSPITAIS_ONDJIVA["hospital provincial ekuma"]
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
        f"Para localização, diga 'onde fica {dados_hospital['nome']}'."
    )

def listar_todos_hospitais():
    resposta = "🏥 *Hospitais em Ondjiva*\n\n"
    chaves = list(HOSPITAIS_ONDJIVA.keys())
    for i, chave in enumerate(chaves, 1):
        dados = HOSPITAIS_ONDJIVA[chave]
        resposta += (
            f"{i}. *{dados['nome']}*\n"
            f"   📍 Bairro: {dados['bairro']}\n"
            f"   🕐 Consultas: {dados['consultas']}\n\n"
        )
    resposta += "Responda com o número ou nome do hospital para mais detalhes."
    return resposta

def handler_hospitais(texto_baixo, telefone=None):
    if any(p in texto_baixo for p in ["todos", "lista", "quais", "quantos"]):
        chaves = list(HOSPITAIS_ONDJIVA.keys())
        if telefone:
            ESTADO_LISTA[telefone] = {"tipo": "hospitais", "dados": chaves}
        return listar_todos_hospitais()
    if "especialidade" in texto_baixo:
        hospital = pesquisar_hospital(texto_baixo)
        if hospital:
            return f"🏥 *{hospital['nome']}*\nNão tenho a lista exata de especialidades. Sugiro contactar diretamente o hospital."
    hospital = pesquisar_hospital(texto_baixo)
    if hospital:
        return formatar_resposta_hospital(hospital)
    if "hospital" in texto_baixo:
        chaves = list(HOSPITAIS_ONDJIVA.keys())
        if telefone:
            ESTADO_LISTA[telefone] = {"tipo": "hospitais", "dados": chaves}
        return listar_todos_hospitais()
    return None

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
            f"Para detalhes completos, diga 'detalhes {dados_escola['nome']}'."
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
            f"Para localização, diga 'onde fica {dados_escola['nome']}'."
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
    chaves_ordenadas = list(escolas_filtradas.keys())
    for i, chave in enumerate(chaves_ordenadas, 1):
        dados = escolas_filtradas[chave]
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

def handler_escolas(texto_baixo, telefone=None):
    if any(p in texto_baixo for p in ["pública", "publica", "públicas", "publicas"]):
        chaves = list(ESCOLAS_PUBLICAS.keys())
        if telefone:
            ESTADO_LISTA[telefone] = {"tipo": "escolas", "dados": chaves}
        return listar_escolas_por_tipo(tipo="Pública")
    if any(p in texto_baixo for p in ["privada", "privadas", "privado", "privados", "particular", "particulares"]):
        chaves = list(ESCOLAS_PRIVADAS.keys())
        if telefone:
            ESTADO_LISTA[telefone] = {"tipo": "escolas", "dados": chaves}
        return listar_escolas_por_tipo(tipo="Privada")
    bairros_ondjiva = ["ekuma", "naipalala", "kaculuvale", "castilhos", "caxila", "zeca", "muhongo", "bangula", "kafitu", "onahumba", "pioneiro zeca"]
    for bairro in bairros_ondjiva:
        if bairro in texto_baixo:
            return listar_escolas_por_tipo(bairro=bairro.capitalize())
    if "enfermagem" in texto_baixo:
        return "📖 *Escolas com Enfermagem Geral:*\n🏫 ITSO (Pública - Ekuma)\n🎓 Colégio Pitágoras (Privada - Naipalala)\n🎓 Colégio Arcanjo (Privada - Naipalala)\n🎓 Colégio Abcunene (Privada - Caxila 3)"
    if "informática" in texto_baixo or "informatica" in texto_baixo:
        return "📖 *Escolas com Informática:*\n🎓 Colégio Pitágoras (Privada - Naipalala)\n🎓 Colégio Abcunene (Privada - Caxila 3)"
    if "contabilidade" in texto_baixo or "finanças" in texto_baixo or "financas" in texto_baixo:
        return "📖 *Escola com Finanças/Contabilidade:*\n🏫 ITAS (Pública - Naipalala)"
    escola = pesquisar_escola(texto_baixo)
    if escola:
        if any(p in texto_baixo for p in ["completo", "detalhes", "todos", "tudo"]):
            return formatar_resposta_escola(escola, completo=True)
        return formatar_resposta_escola(escola)
    if any(p in texto_baixo for p in ["escola", "colégio", "colegio", "liceu", "instituto"]):
        return "📚 *Escolas em Ondjiva*\n\n🏫 *Públicas:* ITSO, Eiffel, Oulondelo, IMPO, CESMO, ITAS\n🎓 *Privadas:* Pitágoras, Ednas, Popiene, Arcanjo, Marc Leandres, Bulet Salú, Abcunene\n\nDiga 'escolas públicas', 'colégios privados' ou o nome da escola para detalhes."
    return None

def handler_faculdades(texto_baixo):
    if "faculdade" in texto_baixo or "universidade" in texto_baixo or "superior" in texto_baixo:
        if "rei luhuna" in texto_baixo or "muhongo" in texto_baixo:
            return "🏛️ *Faculdade Rei Luhuna*\n📍 Bairro Muhongo\nPara mais informações sobre cursos, contacte diretamente a instituição."
        if "mandume" in texto_baixo or "naipalala" in texto_baixo:
            return "🏛️ *Faculdade Mandume*\n📍 Bairro Naipalala\nPara mais informações sobre cursos, contacte diretamente a instituição."
        return "🏛️ *Faculdades em Ondjiva:*\n• Faculdade Rei Luhuna (Bairro Muhongo)\n• Faculdade Mandume (Bairro Naipalala)\n\nPara mais detalhes sobre cursos, contacte diretamente as instituições."
    return None

def handler_mercados(texto_baixo, telefone=None):
    if any(p in texto_baixo for p in ["preço", "preco", "preços", "precos", "custa", "custo", "valor", "quanto"]):
        mercado_encontrado = None
        for chave, dados in MERCADOS_ONDJIVA.items():
            if chave in texto_baixo:
                mercado_encontrado = dados
                break
        if mercado_encontrado:
            return f"🛒 *{mercado_encontrado['nome']}*\n\n💰 Os preços variam conforme a época.\n\n📌 Para preços exatos, visite a praça pessoalmente.\n\n📍 Bairro: {mercado_encontrado['bairro']}\n🕐 {mercado_encontrado['horario']}"
        else:
            return "💰 Os preços nos mercados de Ondjiva variam conforme a época.\n\n📌 Para preços exatos, visite as praças pessoalmente:\n• Praça da Lemanha (Bairro Kaculuvale)\n• Praça do Xomucuio"
    if "lemanha" in texto_baixo:
        mercado = MERCADOS_ONDJIVA["praça da lemanha"]
        return f"🛒 *{mercado['nome']}*\n📍 Bairro: {mercado['bairro']}\n🕐 {mercado['horario']}\n\n📦 *Produtos:* {', '.join(mercado['produtos'])}\n\nPara localização, diga 'onde fica a Praça da Lemanha'.\n💰 Para preços, diga 'preços da Lemanha'."
    if "xomucuio" in texto_baixo or "xamucuio" in texto_baixo:
        mercado = MERCADOS_ONDJIVA["praça do xomucuio"]
        return f"🛒 *{mercado['nome']}*\n📍 Bairro: {mercado['bairro']}\n🕐 {mercado['horario']}\n\n📦 *Produtos:* {', '.join(mercado['produtos'])}\n\nPara localização, diga 'onde fica a Praça do Xomucuio'.\n💰 Para preços, diga 'preços do Xomucuio'."
    if "produto" in texto_baixo or "vendem" in texto_baixo or "vende" in texto_baixo:
        for chave, dados in MERCADOS_ONDJIVA.items():
            if chave in texto_baixo:
                return f"🛒 *{dados['nome']}*\n\n📦 *Produtos:* {', '.join(dados['produtos'])}\n\n💰 Para preços, visite a praça."
    if any(p in texto_baixo for p in ["todos", "lista", "quais", "quantos", "mercado", "praça", "praca", "feira"]):
        chaves = list(MERCADOS_ONDJIVA.keys())
        if telefone:
            ESTADO_LISTA[telefone] = {"tipo": "mercados", "dados": chaves}
        return "🛒 *Mercados e Praças de Ondjiva*\n\n1. *Praça da Lemanha*\n   📍 Bairro Kaculuvale\n\n2. *Praça do Xomucuio*\n   📍 Ondjiva\n\n📦 Produtos: Fuba, milho, arroz, massa, frango, peixe, tomate, cebola e muito mais.\n💰 Para preços atualizados, visite a praça.\n\nResponda com o número (1 ou 2) para detalhes."
    return None

def handler_cheias_alertas(texto_baixo):
    if any(p in texto_baixo for p in ["clima", "climático", "climatico"]):
        return f"🌍 *Clima do Cunene*\n\n📋 Tipo: {CLIMA_CUNENE['tipo']}\n📅 Estações: {CLIMA_CUNENE['estacoes']}\n\n☀️ *Estação seca:* Março a Outubro (até 30°C)\n🌧️ *Estação chuvosa:* Novembro a Fevereiro (20°C a 25°C)\n\n⚠️ As cheias do Rio Cunene são recorrentes na estação chuvosa."
    if "seca" in texto_baixo or "seco" in texto_baixo or "verão" in texto_baixo or "verao" in texto_baixo:
        return f"☀️ *Estação Seca no Cunene*\n\n📅 Período: {CHEIAS_ALERTAS['estacao_seca']['periodo']}\n🌡️ Temperatura: {CHEIAS_ALERTAS['estacao_seca']['temperatura']}\n\n📝 {CHEIAS_ALERTAS['estacao_seca']['descricao']}"
    if any(p in texto_baixo for p in ["chuvosa", "chuva", "chove", "inverno"]):
        return f"🌧️ *Estação Chuvosa no Cunene*\n\n📅 Período: {CHEIAS_ALERTAS['estacao_chuvosa']['periodo']}\n🌡️ Temperatura: {CHEIAS_ALERTAS['estacao_chuvosa']['temperatura']}\n\n📝 {CHEIAS_ALERTAS['estacao_chuvosa']['descricao']}\n\n⚠️ Cheias do Rio Cunene recorrentes.\n🛡️ Siga as instruções da Protecção Civil."
    if "temperatura" in texto_baixo or "quente" in texto_baixo or "frio" in texto_baixo or "grau" in texto_baixo:
        return f"🌡️ *Temperaturas no Cunene*\n\n☀️ Estação seca (Março-Outubro): até 30°C\n🌧️ Estação chuvosa (Novembro-Fevereiro): 20°C a 25°C"
    if any(p in texto_baixo for p in ["área", "area", "zona", "risco", "perigo", "alaga", "inunda"]):
        resposta = "⚠️ *Áreas de Risco - Cheias em Ondjiva*\n\n"
        for area in CHEIAS_ALERTAS['areas_risco']:
            resposta += f"📍 *{area['zona']}*\n   Risco: {area['risco']}\n\n"
        resposta += "🌧️ Cheias do Rio Cunene recorrentes na estação chuvosa (Novembro-Fevereiro).\n🛡️ Siga as instruções da Protecção Civil."
        return resposta
    if any(p in texto_baixo for p in ["contacto", "contato", "telefone", "ligar", "emergência", "emergencia", "socorro", "protecção", "proteção", "proteccao"]):
        return f"🆘 *Contactos de Emergência*\n\n🚒 Bombeiros: 115\n👮 Polícia: 113\n🛡️ Protecção Civil: Atender às instruções oficiais\n🏛️ Governo Provincial do Cunene - Bairro Bangula"
    if "recomenda" in texto_baixo or "dica" in texto_baixo or "conselho" in texto_baixo or "prevenir" in texto_baixo or "cuidado" in texto_baixo:
        recomendacoes_str = "\n".join([f"  ✓ {r}" for r in CHEIAS_ALERTAS['recomendacoes']])
        return f"🛡️ *Recomendações de Segurança*\n\n{recomendacoes_str}"
    if "rio cunene" in texto_baixo or "rio" in texto_baixo:
        return "🌊 *Rio Cunene*\n\n⚠️ Cheias recorrentes na estação chuvosa (Novembro-Fevereiro).\n📋 Esteja atento às previsões e siga as instruções da Protecção Civil."
    if any(p in texto_baixo for p in ["cheia", "cheias", "inundação", "inundacao", "alerta", "alagamento", "estação", "epoca", "época"]):
        return f"⚠️ *Cheias e Clima — Cunene*\n\n🌍 Clima: {CLIMA_CUNENE['tipo']}\n☀️ Seca: Março a Outubro (até 30°C)\n🌧️ Chuvosa: Novembro a Fevereiro (20°C a 25°C)\n\n⚠️ Cheias do Rio Cunene recorrentes na estação chuvosa.\n🆘 Emergência: Bombeiros 115 | Polícia 113"
    return None

def handler_municipios(texto_baixo):
    if "lista completa" in texto_baixo or "completo" in texto_baixo:
        resposta = "🏛️ *14 Municípios da Província do Cunene*\n\n"
        for m in MUNICIPIOS_CUNENE:
            comunas_str = ", ".join(m["comunas"]) if m["comunas"] else "Sem comunas"
            admin_str = m["administrador"] if m["administrador"] else "Sem administrador"
            resposta += f"{m['numero']}. *{m['nome']}*\n   📍 Comunas: {comunas_str}\n   👤 Administrador: {admin_str}\n\n"
        return resposta
    if any(p in texto_baixo for p in ["quais", "quantos", "nome", "municípios do cunene", "municipios do cunene"]):
        nomes = [m["nome"] for m in MUNICIPIOS_CUNENE]
        return f"A província do Cunene tem *14 municípios*:\n\n{', '.join(nomes)}.\n\nSe quiseres a lista completa com comunas e administradores, escreve: *lista completa dos municípios*."
    if "administrador" in texto_baixo:
        if "quem" in texto_baixo or "qual" in texto_baixo:
            for m in MUNICIPIOS_CUNENE:
                if m["nome"].lower() in texto_baixo:
                    if m["administrador"]:
                        return f"👤 O administrador do município de *{m['nome']}* é *{m['administrador']}*."
                    else:
                        return f"O município de *{m['nome']}* ainda não tem administrador nomeado."
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
            return f"🏛️ *Município de {m['nome']}*\n🔢 Nº {m['numero']} de 14\n📍 Comunas: {comunas_str}\n👤 Administrador: {admin_str}"
    for m in MUNICIPIOS_CUNENE:
        nome_sem_acento = m["nome"].lower().replace("é", "e").replace("ô", "o").replace("ã", "a").replace("í", "i")
        texto_sem_acento = texto_baixo.replace("é", "e").replace("ô", "o").replace("ã", "a").replace("í", "i")
        if nome_sem_acento in texto_sem_acento:
            comunas_str = ", ".join(m["comunas"]) if m["comunas"] else "Sem comunas"
            admin_str = m["administrador"] if m["administrador"] else "Sem administrador nomeado"
            return f"🏛️ *Município de {m['nome']}*\n🔢 Nº {m['numero']} de 14\n📍 Comunas: {comunas_str}\n👤 Administrador: {admin_str}"
    return None

def handler_administracao(texto_baixo):
    if any(p in texto_baixo for p in ["governo provincial", "tribunal", "agt", "palácio"]):
        locais = {"governo provincial": "Governo Provincial do Cunene", "tribunal": "Tribunal Provincial", "agt": "AGT", "palácio": "Palácio do Governo"}
        for chave, nome in locais.items():
            if chave in texto_baixo:
                return f"🏛️ *{nome}*\n📍 Bairro Bangula\n🕐 Segunda a Quinta: 08h-15h30 | Sexta: 08h-15h"
    if "administração provincial" in texto_baixo or "mediateca" in texto_baixo or "aeroporto" in texto_baixo:
        locais = {"administração provincial": "Administração Provincial", "mediateca": "Mediateca Lucas Damba", "aeroporto": "Aeroporto Provincial 11 de Novembro"}
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

def handler_comercio(texto_baixo):
    if "shoprite" in texto_baixo:
        if "horário" in texto_baixo or "horario" in texto_baixo or "hora" in texto_baixo or "aberto" in texto_baixo:
            return "🛒 *Shoprite Ondjiva*\n📍 Bairro Castilhos\n🕐 Segunda a Sábado: 08h-20h\n🕐 Domingo: 08h-13h30"
        return "🛒 O *Shoprite* fica no Bairro Castilhos. Diga 'onde fica o Shoprite' para localização."
    if "angomarte" in texto_baixo:
        if "horário" in texto_baixo or "horario" in texto_baixo or "hora" in texto_baixo or "aberto" in texto_baixo:
            return "🛒 *AngoMarte Ondjiva*\n📍 Bairro Castilhos\n🕐 Segunda a Sábado: 08h-20h\n🕐 Domingo: 08h-13h30"
        return "🛒 O *AngoMarte* fica no Bairro Castilhos. Diga 'onde fica o AngoMarte' para localização."
    if "comércio" in texto_baixo or "comercio" in texto_baixo or "supermercado" in texto_baixo:
        return "🛒 *Comércio em Ondjiva*\n\n• *Shoprite* - Bairro Castilhos\n• *AngoMarte* - Bairro Castilhos\n\n🕐 Segunda a Sábado 08h-20h | Domingo 08h-13h30"
    return None

RESPOSTAS_DIRETAS = {
    "governadora": "A Governadora da Província do Cunene é *Gerdina Didalelwa*.",
    "quem é a governadora": "A Governadora da Província do Cunene é *Gerdina Didalelwa*.",
    "capital do cunene": "A capital da província do Cunene é *Ondjiva*.",
    "qual é a capital": "A capital da província do Cunene é *Ondjiva*.",
    "quantas províncias": "Angola tem *21 províncias* oficiais.",
    "bairros de ondjiva": "Os bairros de Ondjiva são: *Naipalala, Kafitu, Onahumba, Pioneiro Zeca, Castilhos, Kaculuvale, Ekuma, Muhongo, Bangula*.",
}

# ==========================================
# PROCESSAMENTO PRINCIPAL
# ==========================================
def processar_texto(telefone_origem, user_text):
    texto_baixo = user_text.lower().strip()
    MEMORIA_TIMESTAMPS[telefone_origem] = datetime.utcnow()

    # 0. CAPTURAR NÚMERO QUANDO HÁ LISTA ATIVA
    if texto_baixo.isdigit() and telefone_origem in ESTADO_LISTA:
        numero = int(texto_baixo)
        ctx = ESTADO_LISTA[telefone_origem]
        if ctx["tipo"] == "escolas":
            chaves = ctx["dados"]
            if 1 <= numero <= len(chaves):
                escola = ESCOLAS_ONDJIVA[chaves[numero - 1]]
                ESTADO_LISTA.pop(telefone_origem)
                return formatar_resposta_escola(escola, completo=False)
        elif ctx["tipo"] == "hospitais":
            chaves = ctx["dados"]
            if 1 <= numero <= len(chaves):
                hospital = HOSPITAIS_ONDJIVA[chaves[numero - 1]]
                ESTADO_LISTA.pop(telefone_origem)
                return formatar_resposta_hospital(hospital)
        elif ctx["tipo"] == "mercados":
            chaves = ctx["dados"]
            if 1 <= numero <= len(chaves):
                mercado = MERCADOS_ONDJIVA[chaves[numero - 1]]
                ESTADO_LISTA.pop(telefone_origem)
                return f"🛒 *{mercado['nome']}*\n📍 Bairro: {mercado['bairro']}\n🕐 {mercado['horario']}\n\n📦 Produtos: {', '.join(mercado['produtos'])}\n\n💰 Para preços, diga 'preços da {mercado['nome'].lower()}'."
        ESTADO_LISTA.pop(telefone_origem)
        return "❌ Número inválido. Escreve *menu* para voltar ao início."

    # 0.1 RESPOSTAS DIRETAS
    for pergunta, resposta in RESPOSTAS_DIRETAS.items():
        if pergunta in texto_baixo:
            return resposta

    # 0.2 EMERGÊNCIA DIRECTA
    if any(p in texto_baixo for p in ["emergencia", "emergência", "socorro"]):
        return "🚨 *Emergência:* Polícia 113 | Bombeiros 115. Procure um local seguro e ligue para os serviços de emergência!"

    # 0.3 CUANHAMA
    resposta_cuanhama = handler_cuanhama(texto_baixo)
    if resposta_cuanhama:
        return resposta_cuanhama

    # 0.4 CONVERSA CASUAL
    resposta_casual = handler_conversa_casual(texto_baixo)
    if resposta_casual:
        return resposta_casual

    # ==========================================
    # 1. NAVEGAÇÃO (MENU)
    # ==========================================
    if telefone_origem in ESTADO_NAVEGACAO:
        estado = ESTADO_NAVEGACAO[telefone_origem]
        nivel = estado.get("nivel", "menu")

        if nivel == "menu":
            if texto_baixo in ["1", "2", "3", "4", "5", "6", "7"]:
                opcao = texto_baixo
                if opcao == "1":
                    ESTADO_NAVEGACAO.pop(telefone_origem)
                    ESTADO_REPORTAGEM[telefone_origem] = {'passo': 1, 'problema': '', 'tempo': '', 'causa': '', 'inicio': datetime.utcnow()}
                    return "📝 *Reportagem de Problema*\n\nDescreve o problema que queres reportar.\nExemplos:\n• Falta de água no Kafitu\n• Medicamentos em falta no hospital\n• Estrada esburacada em Naipalala"
                elif opcao == "2":
                    ESTADO_NAVEGACAO[telefone_origem]["nivel"] = "localizacao_pedido"
                    return "📍 Diz-me o nome do local que queres localizar (ex: Shoprite, Hospital Ekuma, Mediateca…)."
                elif opcao == "3":
                    ESTADO_NAVEGACAO[telefone_origem]["nivel"] = "info_submenu"
                    return "📋 *Informações oficiais – escolhe a categoria:*\nA - Administração Pública\nB - Saúde\nC - Ensino\nD - Bancos\nE - Comércio e Lazer\nF - Divisão Administrativa"
                elif opcao == "4":
                    ESTADO_NAVEGACAO.pop(telefone_origem)
                    return "🚨 *Emergências:* Polícia 113, Bombeiros 115. Procura um local seguro."
                elif opcao == "5":
                    ESTADO_NAVEGACAO.pop(telefone_origem)
                    chaves_mercados = list(MERCADOS_ONDJIVA.keys())
                    ESTADO_LISTA[telefone_origem] = {"tipo": "mercados", "dados": chaves_mercados}
                    return "🛒 *Mercados e Praças de Ondjiva*\n\n1. *Praça da Lemanha* - Bairro Kaculuvale\n2. *Praça do Xomucuio*\n\n📦 Produtos: Fuba, milho, arroz, massa, frango, peixe, tomate, cebola e muito mais.\n💰 Para preços atualizados, visite a praça.\n\nResponda com o número (1 ou 2) para detalhes."
                elif opcao == "6":
                    ESTADO_NAVEGACAO.pop(telefone_origem)
                    return "⚠️ *Cheias e Clima — Província do Cunene*\n\n🌍 Clima: Árido a semi-árido\n☀️ *Estação seca:* Março a Outubro (até 30°C)\n🌧️ *Estação chuvosa:* Novembro a Fevereiro (20°C a 25°C)\n\n⚠️ Cheias do Rio Cunene recorrentes na estação chuvosa.\n🆘 Emergência: Bombeiros 115 | Polícia 113"
                elif opcao == "7":
                    ESTADO_NAVEGACAO[telefone_origem]["nivel"] = "agricultura_submenu"
                    return "🌾 *Agricultura e Pecuária — Cunene*\n\nEscolhe a opção:\nA - Agricultura\nB - Pecuária\nC - Pesca Artesanal\nD - Recursos Minerais\nE - Solo e Vegetação\n\nResponde com a letra."
            else:
                ESTADO_NAVEGACAO.pop(telefone_origem)

        elif nivel == "agricultura_submenu":
            opcao = texto_baixo.upper().strip()
            ESTADO_NAVEGACAO.pop(telefone_origem)
            if opcao == "A":
                return AGRICULTURA_INFO
            elif opcao == "B":
                return PECUARIA_INFO
            elif opcao == "C":
                return PESCA_INFO
            elif opcao == "D":
                return MINERAIS_INFO
            elif opcao == "E":
                return SOLO_VEGETACAO_INFO

        elif nivel == "info_submenu":
            opcao = texto_baixo.upper().strip()
            if opcao in ["A", "B", "C", "D", "E", "F"]:
                if opcao == "A":
                    ESTADO_NAVEGACAO.pop(telefone_origem)
                    return "🏛️ *Administração Pública*\n\n🕐 Horário: Seg‑Qui 08h‑15h30 | Sex 08h‑15h\n\n📍 *Bangula:* Governo Provincial, Tribunal, AGT\n📍 *Kaculuvale:* Administração Provincial, Mediateca, Aeroporto\n📍 *Castilhos:* Comando Municipal da Polícia, SIC\n📍 *Naipalala:* Viação e Trânsito, Bombeiros, Polícia Fiscal\n\nDiga o nome da repartição para mais detalhes."
                elif opcao == "B":
                    ESTADO_NAVEGACAO[telefone_origem]["nivel"] = "saude_submenu"
                    return "🏥 *Saúde — Escolhe a opção:*\n\nA - Hospitais\nB - Horários de Atendimento\nC - Campanhas de Vacinação\nD - Doenças e Prevenção\n\nResponde com a letra."
                elif opcao == "C":
                    ESTADO_NAVEGACAO[telefone_origem]["nivel"] = "ensino_submenu"
                    return "📚 *Ensino — Escolhe a opção:*\n\nA - Escolas\nB - Matrícula\n\nResponde com a letra."
                elif opcao == "D":
                    ESTADO_NAVEGACAO.pop(telefone_origem)
                    return "Bancos Seg‑Sex 08h‑15h. BAI, BFA, BIC, BCI, BPC, Sol, Económico em Bangula; BPC2 e Atlântico em Naipalala."
                elif opcao == "E":
                    ESTADO_NAVEGACAO.pop(telefone_origem)
                    return "Shoprite e AngoMarte (Castilhos) abertos Seg-Sáb 08h‑20h, Dom 08h-13h30."
                elif opcao == "F":
                    ESTADO_NAVEGACAO.pop(telefone_origem)
                    nomes = [m["nome"] for m in MUNICIPIOS_CUNENE]
                    return f"A província do Cunene tem *14 municípios*:\n{', '.join(nomes)}.\n\nPara lista completa com comunas e administradores, escreva: *lista completa dos municípios*."
            else:
                ESTADO_NAVEGACAO.pop(telefone_origem)

        elif nivel == "saude_submenu":
            opcao = texto_baixo.upper().strip()
            if opcao == "A":
                ESTADO_NAVEGACAO.pop(telefone_origem)
                chaves = list(HOSPITAIS_ONDJIVA.keys())
                ESTADO_LISTA[telefone_origem] = {"tipo": "hospitais", "dados": chaves}
                return listar_todos_hospitais()
            elif opcao == "B":
                ESTADO_NAVEGACAO.pop(telefone_origem)
                return "🕐 *Horários de Atendimento — Hospitais de Ondjiva*\n\n🚨 *Urgências:* 24 horas por dia, todos os dias.\n\n🏥 *Consultas Externas:* Segunda a Sexta-feira, das 08h às 15h.\n\n🏪 *Postos Médicos:* Todos os bairros de Ondjiva dispõem de um posto médico para atendimento primário.\n\nPara mais informações, dirija-se ao hospital ou posto médico mais próximo."
            elif opcao == "C":
                ESTADO_NAVEGACAO.pop(telefone_origem)
                return "💉 *Campanhas de Vacinação*\n\nAtualmente, não há nenhuma campanha de vacinação ativa em Ondjiva.\n\nAssim que houver novidades, serei o primeiro a informar-te por aqui. Fica atento! 😊\n\nPara questões de saúde, dirige-te ao hospital ou posto médico mais próximo."
            elif opcao == "D":
                ESTADO_NAVEGACAO[telefone_origem]["nivel"] = "doencas_submenu"
                return "🩺 *Doenças e Prevenção no Cunene*\n\nEscolhe a doença:\nA - Malária\nB - Doenças Diarreicas e Febre Tifóide\nC - Dracunculose (Verme da Guiné)\nD - Doenças Respiratórias\nE - Malnutrição\nF - VIH/Sida\n\nResponde com a letra."
            else:
                ESTADO_NAVEGACAO.pop(telefone_origem)

        elif nivel == "doencas_submenu":
            opcao = texto_baixo.upper().strip()
            ESTADO_NAVEGACAO.pop(telefone_origem)
            if opcao == "A":
                return MALARIA_INFO
            elif opcao == "B":
                return DDA_INFO
            elif opcao == "C":
                return DRACUNCULOSE_INFO
            elif opcao == "D":
                return DRA_INFO
            elif opcao == "E":
                return MALNUTRICAO_INFO
            elif opcao == "F":
                return VIH_INFO

        elif nivel == "ensino_submenu":
            opcao = texto_baixo.upper().strip()
            ESTADO_NAVEGACAO.pop(telefone_origem)
            if opcao == "A":
                return "📚 *Escolas em Ondjiva*\n\n🏫 *Públicas:* ITSO, Eiffel, Oulondelo, IMPO, CESMO, ITAS\n🎓 *Privadas:* Pitágoras, Ednas, Popiene, Arcanjo, Marc Leandres, Bulet Salú, Abcunene\n\nDiga 'escolas públicas', 'colégios privados' ou o nome da escola para detalhes."
            elif opcao == "B":
                return (
                    "📝 *Matrículas — Ano Letivo*\n\n"
                    "📅 *Período:* As matrículas gerais começam em Julho/Agosto.\n\n"
                    "📋 *Documentos Necessários:*\n\n"
                    "*Iniciação e Ensino Primário:*\n"
                    "• Bilhete de identidade ou cédula de nascimento\n"
                    "• Duas fotos tipo passe\n\n"
                    "*1º Ciclo:*\n"
                    "• Cópia do bilhete de identidade\n"
                    "• Duas fotos tipo passe\n"
                    "• Certificado de conclusão do ensino primário\n\n"
                    "*Ensino Médio:*\n"
                    "• Cópia do bilhete de identidade\n"
                    "• Duas fotos tipo passe\n"
                    "• Certificado de conclusão do 1º ciclo\n\n"
                    "📍 Dirija-se à escola mais próxima para efetuar a matrícula."
                )

        elif nivel == "localizacao_pedido":
            local_desejado = texto_baixo
            ESTADO_NAVEGACAO.pop(telefone_origem)
            for chave, dados in COORDENADAS_ONDJIVA.items():
                if chave in local_desejado:
                    enviar_localizacao_whatsapp(telefone_origem, dados["lat"], dados["lon"], dados["nome"], dados["endereco"])
                    return f"📍 *{dados['nome']}*\n{dados['endereco']}\n\n💡 Clica no Pin acima e depois em *'Como chegar'* para veres a rota."
            for alcunha, chave_oficial in ALCUNHAS_HOSPITAIS.items():
                if alcunha in local_desejado:
                    dados = HOSPITAIS_ONDJIVA[chave_oficial]
                    for ck, cv in COORDENADAS_ONDJIVA.items():
                        if chave_oficial in ck:
                            enviar_localizacao_whatsapp(telefone_origem, cv["lat"], cv["lon"], dados["nome"], f"Bairro {dados['bairro']}, Ondjiva")
                            return f"📍 *{dados['nome']}*\nBairro {dados['bairro']}, Ondjiva\n\n💡 Clica no Pin acima e depois em *'Como chegar'* para veres a rota."
            return "❌ Não encontrei esse local. Tenta novamente com o nome correcto (ex: Shoprite, Hospital Ekuma, Mediateca)."

    # ==========================================
    # 2. PESQUISA DE LOCALIZAÇÃO
    # ==========================================
    if any(p in texto_baixo for p in ["onde fica", "localização de", "localizacao de", "localização do", "localizacao do"]):
        for chave, dados in COORDENADAS_ONDJIVA.items():
            if chave in texto_baixo:
                enviar_localizacao_whatsapp(telefone_origem, dados["lat"], dados["lon"], dados["nome"], dados["endereco"])
                return f"📍 *{dados['nome']}*\n{dados['endereco']}\n\n💡 Clica no Pin acima e depois em *'Como chegar'* para veres a rota."
        for alcunha, chave_oficial in ALCUNHAS_HOSPITAIS.items():
            if alcunha in texto_baixo:
                dados = HOSPITAIS_ONDJIVA[chave_oficial]
                for ck, cv in COORDENADAS_ONDJIVA.items():
                    if chave_oficial in ck:
                        enviar_localizacao_whatsapp(telefone_origem, cv["lat"], cv["lon"], dados["nome"], f"Bairro {dados['bairro']}, Ondjiva")
                        return f"📍 *{dados['nome']}*\nBairro {dados['bairro']}, Ondjiva\n\n💡 Clica no Pin acima e depois em *'Como chegar'* para veres a rota."
        return "❌ Não encontrei esse local. Tenta com o nome completo (ex: Hospital Provincial Ekuma, Shoprite Ondjiva)."

    # ==========================================
    # 3. ROTA
    # ==========================================
    if any(p in texto_baixo for p in ["como chegar", "rota", "caminho", "trajeto"]):
        for chave, dados in COORDENADAS_ONDJIVA.items():
            if chave in texto_baixo:
                ESTADO_ROTA[telefone_origem] = dados
                return f"🗺️ Queres ir para *{dados['nome']}*.\n\n📍 Partilha a tua *Localização Atual* aqui no WhatsApp (clica no 📎 > Localização) para eu gerar a tua rota."

    # ==========================================
    # 4. HANDLERS BLINDADOS
    # ==========================================
    if any(p in texto_baixo for p in ["história", "historia", "cultura", "tradição", "tradicao", "gastronomia", "comida", "prato", "mandume", "gado", "pastor", "funge", "maiavi", "chacota", "origem", "colonial"]):
        resposta = handler_historia_cultura(texto_baixo)
        if resposta:
            return resposta

    if any(p in texto_baixo for p in ["doença", "doenca", "doenças", "doencas", "prevenção", "prevencao", "malária", "malaria", "diarreica", "tifóide", "tifoide", "dracunculose", "verme", "guiné", "guine", "respiratória", "respiratoria", "pneumonia", "malnutrição", "malnutricao", "desnutrição", "desnutricao", "vih", "sida", "hiv", "preservativo"]):
        resposta = handler_doencas(texto_baixo)
        if resposta:
            return resposta

    if "hospital" in texto_baixo or "ekuma" in texto_baixo or "simeone" in texto_baixo or "mucunde" in texto_baixo:
        resposta = handler_hospitais(texto_baixo, telefone_origem)
        if resposta:
            return resposta

    if any(p in texto_baixo for p in ["escola", "colégio", "colegio", "liceu", "instituto", "curso", "estudar", "aula", "ensino"]):
        resposta = handler_escolas(texto_baixo, telefone_origem)
        if resposta:
            return resposta
        resposta = handler_faculdades(texto_baixo)
        if resposta:
            return resposta

    if any(p in texto_baixo for p in ["governo", "tribunal", "agt", "administração", "mediateca", "aeroporto", "comando", "sic", "viação", "bombeiros", "fiscal", "guarda", "fronteira"]):
        resposta = handler_administracao(texto_baixo)
        if resposta:
            return resposta

    if any(p in texto_baixo for p in ["shoprite", "angomarte", "comércio", "comercio", "supermercado"]):
        resposta = handler_comercio(texto_baixo)
        if resposta:
            return resposta

    if any(p in texto_baixo for p in ["mercado", "praça", "praca", "feira", "lemanha", "xomucuio", "xamucuio", "preço", "preco", "preços", "precos", "fuba", "milho"]):
        resposta = handler_mercados(texto_baixo, telefone_origem)
        if resposta:
            return resposta

    if any(p in texto_baixo for p in ["cheia", "cheias", "inundação", "inundacao", "alagamento", "alerta", "chuva", "chuvosa", "temporal", "tempestade", "meteorologia", "clima", "seca", "seco"]):
        resposta = handler_cheias_alertas(texto_baixo)
        if resposta:
            return resposta

    palavras_municipios = ["município", "municipio", "municípios", "municipios", "comuna", "comunas",
                           "cahama", "cuanhama", "curoca", "cuvelai", "namacunde", "ombadja",
                           "chiéde", "nehone", "humbe", "mupa", "naulila", "chitado", "cafima", "chissuata",
                           "administrador", "administradores"]
    palavras_lingua = ["língua", "lingua", "falar", "dizer", "olá", "ola", "idioma", "dialeto", "aprender", "traduzir", "significa"]
    
    if any(p in texto_baixo for p in palavras_municipios) and not any(p in texto_baixo for p in palavras_lingua):
        resposta = handler_municipios(texto_baixo)
        if resposta:
            return resposta

    # ==========================================
    # 5. ACTIVAÇÃO DO MENU
    # ==========================================
    if texto_baixo in ["menu", "ajuda", "help", "guia", "opções", "opcoes", "início", "inicio"] or "como usar" in texto_baixo:
        ESTADO_NAVEGACAO[telefone_origem] = {"nivel": "menu"}
        ESTADO_LISTA.pop(telefone_origem, None)
        return "📋 *Menu Principal — Bot Cunene*\n\nEscolhe o número:\n1️⃣ Reportar um problema\n2️⃣ Localização de locais\n3️⃣ Informações oficiais\n4️⃣ Emergências\n5️⃣ Mercado\n6️⃣ Cheias e alertas\n7️⃣ Agricultura e Pecuária\n\nResponde apenas com o número.\nOu faz uma pergunta directa. ✨"

    # ==========================================
    # 6. REPORTAGEM
    # ==========================================
    if texto_baixo.startswith("reportagem") or any(p in texto_baixo for p in ["quero reportar", "quero fazer uma reportagem", "reportar um problema", "fazer uma reportagem", "reportar problema"]):
        if not texto_baixo.startswith("reportagem"):
            ESTADO_REPORTAGEM[telefone_origem] = {'passo': 1, 'problema': '', 'tempo': '', 'causa': '', 'inicio': datetime.utcnow()}
            return "📝 *Reportagem de Problema*\n\nDescreve o problema que queres reportar.\nExemplos:\n• Falta de água no Kafitu\n• Medicamentos em falta no hospital\n• Estrada esburacada em Naipalala"
        problema = user_text.strip()[10:].strip()
        if not problema:
            return "Escreve *Reportagem* seguido do problema (ex: Reportagem falta de água no Kafitu)."
        ESTADO_REPORTAGEM[telefone_origem] = {'passo': 1, 'problema': problema, 'tempo': '', 'causa': '', 'inicio': datetime.utcnow()}
        return f"📝 *Ocorrência registada:* {problema}\nHá quanto tempo estão nessa situação?"

    if telefone_origem in ESTADO_REPORTAGEM:
        dados = ESTADO_REPORTAGEM[telefone_origem]
        if (datetime.utcnow() - dados['inicio']).total_seconds() > 900:
            ESTADO_REPORTAGEM.pop(telefone_origem)
            return "⏳ Reportagem cancelada por inatividade. Começa de novo com *Reportagem*."
        if dados['passo'] == 1:
            dados['tempo'] = user_text.strip()
            dados['passo'] = 2
            return "Obrigado. Agora diz-me: *O que causou essa situação?* (responde 'Não sei' se não souberes)."
        elif dados['passo'] == 2:
            dados['causa'] = user_text.strip()
            relato = f"PROBLEMA: {dados['problema']} | DURAÇÃO: {dados['tempo']} | CAUSA: {dados['causa']}"
            guardar_reportagem_bd(telefone_origem, relato)
            ESTADO_REPORTAGEM.pop(telefone_origem)
            return f"✅ *Ocorrência enviada com sucesso!*\n• {dados['problema']}\n• Duração: {dados['tempo']}\n• Causa: {dados['causa']}\n\nObrigado por ajudares Ondjiva! Escreve *menu* para outras opções."

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
            regra_relogio += f"Podes usar '{saudacao}' naturalmente se for adequado."
        else:
            regra_relogio += "Responde diretamente à pergunta, sem saudações repetidas."

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
        return f"🚗 *Rota Calculada para {nome_dest}*\n\nClica no link para abrir o GPS:\n👉 {link_rota}"
    return "Recebi a tua localização! 📍 Se precisares da rota para algum lugar, escreve 'Como chegar a [nome do local]'."

# ==========================================
# ROTAS DO FLASK
# ==========================================
@app.route('/')
def home():
    return "Bot Cunene operacional.", 200

@app.route('/health')
def health():
    return "OK", 200

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
    global ULTIMA_ATIVIDADE, MENSAGENS_PROCESSADAS
    
    agora = datetime.utcnow()
    tempo_inativo = (agora - ULTIMA_ATIVIDADE).total_seconds()
    
    if tempo_inativo > 30:
        print(f"⚠️ Possível cold start detectado ({tempo_inativo:.0f}s inativo). Aguardando 2s...")
        time.sleep(2)
        ULTIMA_ATIVIDADE = datetime.utcnow()
    
    body = request.get_json()
    if body and body.get("object"):
        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                if "messages" in value:
                    for msg in value["messages"]:
                        msg_id = msg.get("id", "")
                        timestamp = msg.get("timestamp", "")
                        
                        chave_unica = f"{msg_id}_{timestamp}"
                        
                        agora = datetime.utcnow()
                        if chave_unica in MENSAGENS_PROCESSADAS:
                            tempo_passado = (agora - MENSAGENS_PROCESSADAS[chave_unica]).total_seconds()
                            if tempo_passado < 30:
                                print(f"⏭️ Mensagem duplicada ignorada: {chave_unica}")
                                continue
                        
                        MENSAGENS_PROCESSADAS[chave_unica] = agora
                        
                        chaves_antigas = [k for k, v in MENSAGENS_PROCESSADAS.items() if (agora - v).total_seconds() > 300]
                        for k in chaves_antigas:
                            del MENSAGENS_PROCESSADAS[k]
                        
                        ULTIMA_ATIVIDADE = agora
                        
                        tel = msg["from"]
                        if msg["type"] == "text":
                            texto = msg["text"]["body"]
                            print(f"📩 Mensagem: {tel} -> {texto}")
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
