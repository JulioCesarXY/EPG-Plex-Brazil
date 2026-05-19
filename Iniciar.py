import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

# ==============================================================================
# CONFIGURAÇÕES
# ==============================================================================
# O script tenta ler de forma segura do GitHub Actions, ou usa o seu token como fallback
PLEX_TOKEN = os.environ.get("PLEX_TOKEN", "rwyekjwc6k439C_JV2HW")
LANGUAGE = "pt-BR"                  # Força a localização para Português do Brasil
ARQUIVO_XML = "plex_br_epg.xml"     # Nome do arquivo final que será gerado
# ==============================================================================

def buscar_epg_plex():
    """Faz a requisição dos dados de EPG na API do Plex forçando localização em PT."""
    agora = datetime.now(timezone.utc)
    begins_at = int(agora.timestamp())
    ends_at = int((agora + timedelta(hours=24)).timestamp())

    url = "https://epg.provider.plex.tv/grid"

    params = {
        "beginsAt": begins_at,
        "endsAt": ends_at,
        "vhs": "1",
        "X-Plex-Language": LANGUAGE  # Passando pt-BR na query
    }

    # Adicionado "Accept-Language" e reforçado o "X-Plex-Language" nos cabeçalhos
    headers = {
        "X-Plex-Token": PLEX_TOKEN,
        "X-Plex-Language": LANGUAGE,
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)",
        "Origin": "https://app.plex.tv",
        "Referer": "https://app.plex.tv/"
    }

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Conectando à API do Plex Grid (Idioma: {LANGUAGE})...")
    
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
    """Processa a estrutura fornecida pelo Plex e gera o XMLTV em PT."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Mapeando canais e horários...")
    
    root = ET.Element("tv", generator_info_name="Plex Live TV EPG Extractor")
    canais_salvos = {}
    programas_xml = []

    metadata_list = dados_json.get("MediaContainer", {}).get("Metadata", [])

    for item in metadata_list:
        grandparent_title = item.get("grandparentTitle", "")
        titulo_item = item.get("title", "Sem título")
        
        if grandparent_title and grandparent_title != titulo_item:
            titulo_programa = f"{grandparent_title} - {titulo_item}"
        else:
            titulo_programa = titulo_item

        resumo_programa = item.get("summary", "")

        media_list = item.get("Media", [])
        for media in media_list:
            ts_inicio = media.get("beginsAt")
            ts_fim = media.get("endsAt")
            
            if not ts_inicio or not ts_fim:
                continue

            start_formatted = datetime.fromtimestamp(int(ts_inicio), tz=timezone.utc).strftime('%Y%m%d%H%M%S +0000')
            end_formatted = datetime.fromtimestamp(int(ts_fim), tz=timezone.utc).strftime('%Y%m%d%H%M%S +0000')

            id_bruto = media.get("channelIdentifier", "unknown")
            id_limpo = str(id_bruto).replace("/library/metadata/", "")

            if id_limpo == "unknown":
                continue

            nome_canal = media.get("channelTitle", media.get("channelShortTitle", grandparent_title if grandparent_title else "Plex TV"))

            if id_limpo not in canais_salvos:
                logo_canal = media.get("channelThumb", media.get("channelArt", ""))
                canais_salvos[id_limpo] = {
                    "name": nome_canal,
                    "logo": logo_canal
                }

            prog_tag = ET.Element("programme", start=start_formatted, stop=end_formatted, channel=id_limpo)
            # Definindo a tag lang explicitamente para pt-BR no XML final
            ET.SubElement(prog_tag, "title", lang="pt").text = titulo_programa
            
            if resumo_programa:
                ET.SubElement(prog_tag, "desc", lang="pt").text = resumo_programa
                
            programas_xml.append(prog_tag)

    # Monta o XML
    for cid, cinfo in canais_salvos.items():
        channel_tag = ET.SubElement(root, "channel", id=cid)
        ET.SubElement(channel_tag, "display-name").text = cinfo["name"]
        if cinfo["logo"]:
            ET.SubElement(channel_tag, "icon", src=cinfo["logo"])

    for p_tag in programas_xml:
        root.append(p_tag)

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ", level=0)
    tree.write(nome_arquivo_xml, encoding="utf-8", xml_declaration=True)
    
    print(f"[+] Sucesso! Arquivo '{nome_arquivo_xml}' gerado.")
    print(f"    -> Canais mapeados: {len(canais_salvos)}")
    print(f"    -> Programas/Horários processados: {len(programas_xml)}")


if __name__ == "__main__":
    dados_epg = buscar_epg_plex()
    if dados_epg:
        converter_para_xmltv(dados_epg, ARQUIVO_XML)
        
