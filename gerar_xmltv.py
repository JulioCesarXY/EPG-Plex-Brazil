import requests
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from xml.dom import minidom

# Configurações do Plex
TOKEN = "GV_7BchByQgdyfKiziH2"
URL = "https://epg.provider.plex.tv/grid"

# Simulando um IP público do Brasil (Claro/Embratel São Paulo)
# Isso engana o sistema de GeoIP do Plex que roda no GitHub Actions
IP_BRASIL = "200.100.20.30"

headers = {
    "Accept": "application/json",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "X-Plex-Token": TOKEN,
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    
    # Injeção forçada de IP e Região nos cabeçalhos HTTP
    "X-Forwarded-For": IP_BRASIL,
    "X-Real-IP": IP_BRASIL,
    "CF-IPCountry": "BR"
}

# Configuração do tempo (Plex exige arredondamento para blocos de 30 minutos)
agora_unix = int(time.time())
start_arredondado = agora_unix - (agora_unix % 1800)
end_arredondado = start_arredondado + (12 * 3600)  # 12 horas de programação

params = {
    "lineup": "plex",
    "type": "4",
    "start": str(start_arredondado),
    "end": str(end_arredondado),
    "country": "br",             # Força o catálogo do Brasil na URL
    "language": "pt-BR",          # Exige os textos em português brasileiro
    "X-Plex-Language": "pt-BR"   # Força a tradução na sessão interna do Plex
}

def conter_palavras_ingles(texto):
    if not texto:
        return False
    palavras_usa = [" the ", " and ", " with ", " season ", " episode "]
    return any(p in texto.lower() for p in palavras_usa)

def formatar_data_xmltv(timestamp):
    if not timestamp:
        return ""
    # O padrão XMLTV exige o formato: YYYYMMDDHHMMSS +HHMM
    dt = datetime.fromtimestamp(int(timestamp), tz=timezone.utc).astimezone()
    return dt.strftime('%Y%m%d%H%M%S %z')

def gerar_xmltv():
    print(f"Iniciando requisição tunelada para o Brasil (IP simulado: {IP_BRASIL})...")
    try:
        response = requests.get(URL, headers=headers, params=params)
        
        if response.status_code != 200:
            print(f"Erro na API do Plex: {response.status_code}")
            return

        data = response.json()
        itens_grid = data.get("MediaContainer", {}).get("Metadata", [])

        if not itens_grid:
            print("Nenhum dado retornado da API.")
            return

        print(f"Filtros aplicados. Processando {len(itens_grid)} transmissões recebidas...")

        # Elemento Raiz do padrão XMLTV
        root = ET.Element("tv")
        root.set("generator-info-name", "Plex to XMLTV Generator BR Cloud")

        canais_adicionados = set()
        programas_lista = []

        for item in itens_grid:
            midias = item.get("Media", [])
            if not midias:
                continue
                
            midia_info = midias[0]
            nome_canal = midia_info.get("channelTitle", "Canal")
            id_canal = midia_info.get("channelIdentifier", "N/A")
            
            titulo_programa = item.get("title", "")
            sinopse = item.get("summary", "")
            
            # FILTRO BRASIL: Se mesmo com o IP o Plex mandar lixo americano, nós limpamos aqui
            if conter_palavras_ingles(sinopse) or conter_palavras_ingles(titulo_programa):
                continue

            if id_canal not in canais_adicionados:
                channel_elem = ET.SubElement(root, "channel", id=id_canal)
                display_name = ET.SubElement(channel_elem, "display-name")
                display_name.text = nome_canal
                
                thumb = item.get("thumb")
                if thumb:
                    ET.SubElement(channel_elem, "icon", src=thumb)
                    
                canais_adicionados.add(id_canal)

            programas_lista.append({
                "channel_id": id_canal,
                "start": formatar_data_xmltv(midia_info.get("beginsAt")),
                "stop": formatar_data_xmltv(midia_info.get("endsAt")),
                "title": titulo_programa,
                "sub_title": item.get("grandparentTitle", ""),
                "desc": sinopse
            })

        for prog in programas_lista:
            prog_elem = ET.SubElement(root, "programme", start=prog["start"], stop=prog["stop"], channel=prog["channel_id"])
            
            title_elem = ET.SubElement(prog_elem, "title", lang="pt")
            title_elem.text = prog["title"]
            
            if prog["sub_title"]:
                sub_elem = ET.SubElement(prog_elem, "sub-title", lang="pt")
                sub_elem.text = prog["sub_title"]
                
            if prog["desc"] and prog["desc"] != "Sem descrição.":
                desc_elem = ET.SubElement(prog_elem, "desc", lang="pt")
                desc_elem.text = prog["desc"]

        # Formata o XML
        xml_string = ET.tostring(root, encoding="utf-8")
        parsed_xml = minidom.parseString(xml_string)
        xml_bonito = parsed_xml.toprettyxml(indent="  ", encoding="utf-8")

        # Salva o arquivo XML
        nome_arquivo = "plex_epg_brasil.xml"
        with open(nome_arquivo, "wb") as f:
            f.write(xml_bonito)

        print(f"\n🎉 Sucesso! Arquivo gerado em ambiente de nuvem.")
        print(f"📺 Canais brasileiros isolados no GitHub: {len(canais_adicionados)}")
        print(f"🎬 Programas salvos: {len(programas_lista)}")

    except Exception as e:
        print(f"Erro ao gerar o arquivo XMLTV: {e}")

if __name__ == "__main__":
    gerar_xmltv()
