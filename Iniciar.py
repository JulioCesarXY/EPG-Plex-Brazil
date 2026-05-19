import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

# ==============================================================================
# CONFIGURAÇÕES
# ==============================================================================
# O script agora tentará ler o Token de forma segura do GitHub Actions.
# Se rodar localmente e não encontrar, você pode colocar o token como fallback:
PLEX_TOKEN = os.environ.get("PLEX_TOKEN", "")
LANGUAGE = "pt"                     
ARQUIVO_XML = "plex_br_epg.xml"     
# ==============================================================================

def buscar_epg_plex():
    """Faz a requisição dos dados de EPG na API do Plex."""
    agora = datetime.now(timezone.utc)
    begins_at = int(agora.timestamp())
    ends_at = int((agora + timedelta(hours=24)).timestamp())

    url = "https://epg.provider.plex.tv/grid"

    params = {
        "beginsAt": begins_at,
        "endsAt": ends_at,
        "vhs": "1",
        "X-Plex-Language": LANGUAGE
    }

    headers = {
        "X-Plex-Token": PLEX_TOKEN,
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)",
        "Origin": "https://app.plex.tv",
        "Referer": "https://app.plex.tv/"
    }

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Conectando à API do Plex Grid...")
    
    try:
        response = requests.get(url, params=params, headers=headers)
        if response.status_code == 200:
            print("[+] Dados brutos recebidos com sucesso!")
            return response.json()
        else:
            print(f"[!] Erro na requisição. Status Code: {response.status_code}")
            return None
    except Exception as e:
        print(f"[!] Erro de conexão: {e}")
        return None


def converter_para_xmltv(dados_json, nome_arquivo_xml):
    """Processa a estrutura exata fornecida pelo dump do Plex."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Mapeando canais e horários da estrutura 'Media'...")
    
    root = ET.Element("tv", generator_info_name="Plex Live TV EPG Extractor")
    canais_salvos = {}
    programas_xml = []

    # Acessa o nó principal baseado no seu print: MediaContainer -> Metadata
    metadata_list = dados_json.get("MediaContainer", {}).get("Metadata", [])

    for item in metadata_list:
        # Título e resumo do que está passando (ex: "Episódio 7")
        # Se for um show/série, podemos usar o nome principal (ex: "MasterChef Brasil - Episódio 7")
        grandparent_title = item.get("grandparentTitle", "")
        titulo_item = item.get("title", "Sem título")
        
        if grandparent_title and grandparent_title != titulo_item:
            titulo_programa = f"{grandparent_title} - {titulo_item}"
        else:
            titulo_programa = titulo_item

        resumo_programa = item.get("summary", "")

        # Varre a lista interna 'Media' onde ficam guardados os canais e horários reais
        media_list = item.get("Media", [])
        for media in media_list:
            ts_inicio = media.get("beginsAt")
            ts_fim = media.get("endsAt")
            
            # Se não houver horário válido neste bloco de mídia, ignora
            if not ts_inicio or not ts_fim:
                continue

            start_formatted = datetime.fromtimestamp(int(ts_inicio), tz=timezone.utc).strftime('%Y%m%d%H%M%S +0000')
            end_formatted = datetime.fromtimestamp(int(ts_fim), tz=timezone.utc).strftime('%Y%m%d%H%M%S +0000')

            # Captura e limpa o ID do Canal (usando strict channelIdentifier)
            id_bruto = media.get("channelIdentifier", "unknown")
            id_limpo = str(id_bruto).replace("/library/metadata/", "")

            if id_limpo == "unknown":
                continue

            # Captura o nome amigável do Canal (ex: "MasterChef Brasil" em vez do número)
            nome_canal = media.get("channelTitle", media.get("channelShortTitle", grandparent_title if grandparent_title else "Plex TV"))

            # Se o canal ainda não foi indexado, adiciona ele no dicionário global
            if id_limpo not in canais_salvos:
                logo_canal = media.get("channelThumb", media.get("channelArt", ""))
                canais_salvos[id_limpo] = {
                    "name": nome_canal,
                    "logo": logo_canal
                }

            # Monta a tag de programação atrelada ao canal correto
            prog_tag = ET.Element("programme", start=start_formatted, stop=end_formatted, channel=id_limpo)
            ET.SubElement(prog_tag, "title", lang=LANGUAGE).text = titulo_programa
            
            if resumo_programa:
                ET.SubElement(prog_tag, "desc", lang=LANGUAGE).text = resumo_programa
                
            programas_xml.append(prog_tag)

    # Constrói o XML final respeitando a ordem de validação do XMLTV
    # 1. Tags <channel> primeiro
    for cid, cinfo in canais_salvos.items():
        channel_tag = ET.SubElement(root, "channel", id=cid)
        ET.SubElement(channel_tag, "display-name").text = cinfo["name"]
        if cinfo["logo"]:
            ET.SubElement(channel_tag, "icon", src=cinfo["logo"])

    # 2. Tags <programme> depois
    for p_tag in programas_xml:
        root.append(p_tag)

    # Grava no armazenamento local
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ", level=0)
    tree.write(nome_arquivo_xml, encoding="utf-8", xml_declaration=True)
    
    print(f"[+] Sucesso! Arquivo '{nome_arquivo_xml}' gerado.")
    print(f"    -> Canais mapeados de forma única: {len(canais_salvos)}")
    print(f"    -> Programas/Horários processados: {len(programas_xml)}")


if __name__ == "__main__":
    dados_epg = buscar_epg_plex()
    if dados_epg:
        converter_para_xmltv(dados_epg, ARQUIVO_XML)
