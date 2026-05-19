import requests
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from xml.dom import minidom

# Configurações do Plex
TOKEN = "GV_7BchByQgdyfKiziH2"
URL = "https://epg.provider.plex.tv/grid"

headers = {
    "Accept": "application/json",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "X-Plex-Token": TOKEN,
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# Configuração do tempo (Plex exige arredondamento para blocos de 30 minutos)
agora_unix = int(time.time())
start_arredondado = agora_unix - (agora_unix % 1800)
end_arredondado = start_arredondado + (12 * 3600)  # Puxando 12 horas de programação para o XML

params = {
    "lineup": "plex",
    "type": "4",
    "start": str(start_arredondado),
    "end": str(end_arredondado),
    "language": "pt-BR"
}

def conter_palavras_ingles(texto):
    if not texto:
        return False
    palavras_usa = [" the ", " and ", " with ", " season ", " episode "]
    return any(p in texto.lower() for p in palavras_usa)

def formatar_data_xmltv(timestamp):
    if not timestamp:
        return ""
    # O padrão XMLTV exige o formato: YYYYMMDDHHMMSS +HHMM (com fuso horário local)
    dt = datetime.fromtimestamp(int(timestamp), tz=timezone.utc).astimezone()
    return dt.strftime('%Y%m%d%H%M%S %z')

def gerar_xmltv():
    print("Baixando dados do Plex para conversão em XMLTV...")
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

        print(f"Processando {len(itens_grid)} blocos para estruturar os canais e programas...")

        # Elemento Raiz do padrão XMLTV
        root = ET.Element("tv")
        root.set("generator-info-name", "Plex to XMLTV Generator BR")

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
            
            # FILTRO BRASIL: Remove se o programa for nitidamente do catálogo em inglês
            if conter_palavras_ingles(sinopse) or conter_palavras_ingles(titulo_programa):
                continue

            # O padrão XMLTV exige que TODOS os <channel> fiquem declarados antes dos <programme>
            if id_canal not in canais_adicionados:
                channel_elem = ET.SubElement(root, "channel", id=id_canal)
                display_name = ET.SubElement(channel_elem, "display-name")
                display_name.text = nome_canal
                
                # Injeta a logo/ícone oficial do canal fornecido pela Plex
                thumb = item.get("thumb")
                if thumb:
                    ET.SubElement(channel_elem, "icon", src=thumb)
                    
                canais_adicionados.add(id_canal)

            # Armazena temporariamente os programas para injetar na ordem correta abaixo
            programas_lista.append({
                "channel_id": id_canal,
                "start": formatar_data_xmltv(midia_info.get("beginsAt")),
                "stop": formatar_data_xmltv(midia_info.get("endsAt")),
                "title": titulo_programa,
                "sub_title": item.get("grandparentTitle", ""),
                "desc": sinopse
            })

        # Adiciona os blocos de programas no final do XML (<programme>)
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

        # Formata o XML bruto com endentação limpa (Pretty Print)
        xml_string = ET.tostring(root, encoding="utf-8")
        parsed_xml = minidom.parseString(xml_string)
        xml_bonito = parsed_xml.toprettyxml(indent="  ", encoding="utf-8")

        # Salva o arquivo XML final
        nome_arquivo = "plex_epg_brasil.xml"
        with open(nome_arquivo, "wb") as f:
            f.write(xml_bonito)

        print(f"\n🎉 Sucesso absoluto! O arquivo XMLTV foi gerado.")
        print(f"📌 Arquivo salvo como: {nome_arquivo}")
        print(f"📺 Total de canais brasileiros mapeados: {len(canais_adicionados)}")
        print(f"🎬 Total de programas indexados na grade: {len(programas_lista)}")

    except Exception as e:
        print(f"Erro ao gerar o arquivo XMLTV: {e}")

if __name__ == "__main__":
    gerar_xmltv()
