import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

# ==============================================================================
# CREDENCIAIS EXTRAÍDAS DA SUA CONTA REAL (LIGADO)
# ==============================================================================
PLEX_TOKEN = "sNqzhzKzgfC6omzZUrhw"
CLIENT_ID = "7c9fe305-85d0-4ef2-8fb9-e1a77b797190"
LANGUAGE = "pt-BR"                      
ARQUIVO_XML = "epg_brasil.xml"      
# ==============================================================================

def buscar_epg_grade_oficial():
    """Busca a grade de 12h usando a autenticação real da sua conta."""
    agora = datetime.now(timezone.utc)
    hora_arredondada = agora.replace(minute=0, second=0, microsecond=0)
    
    begins_at = int(hora_arredondada.timestamp())
    ends_at = int((hora_arredondada + timedelta(hours=12)).timestamp())

    # Endpoint oficial da grade com os parâmetros validados
    url = "https://epg.provider.plex.tv/grid"
    
    params = {
        "channelGridKey": "default",
        "beginsAt": str(begins_at),
        "endsAt": str(ends_at),
        "vhs": "1"
    }

    # Espelhamento exato do ambiente Windows capturado no seu F12
    headers = {
        "Host": "epg.provider.plex.tv",
        "Connection": "keep-alive",
        "Accept": "application/json",
        "X-Plex-Language": LANGUAGE,
        "X-Plex-Client-Identifier": CLIENT_ID,
        "X-Plex-Token": PLEX_TOKEN,
        "X-Plex-Device": "Windows",
        "X-Plex-Platform": "Chrome",
        "X-Plex-Platform-Version": "149.0.0.0",
        "X-Plex-Product": "Plex Mediaverse",
        "X-Plex-Provider-Version": "7.6.0",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
        "Origin": "https://watch.plex.tv",
        "Referer": "https://watch.plex.tv/",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
    }

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Conectando à API Grid usando credenciais de Conta Real...")
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=20)
        
        if response.status_code == 200:
            print("[+] Sucesso! Grade de programação autenticada e descarregada.")
            return response.json()
        else:
            print(f"[!] Falha na validação. Status: {response.status_code}")
            print(f"[*] Detalhes do servidor: {response.text[:200]}")
            return None
    except Exception as e:
        print(f"[!] Erro de rede ou comunicação: {e}")
        return None

def converter_para_xmltv(dados_json, nome_arquivo_xml):
    """Mapeia os nós do MediaContainer do Plex e converte no formato XMLTV."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Estruturando árvore XMLTV...")
    
    root = ET.Element("tv", generator_info_name="Plex Account Grid Extractor")
    canais_salvos = {}
    programas_xml = []

    # Extrai a lista do contêiner de mídia do Grid oficial do Plex
    metadata_list = dados_json.get("MediaContainer", {}).get("Metadata", [])

    for item in metadata_list:
        grandparent_title = item.get("grandparentTitle", "").strip()
        titulo_item = item.get("title", "").strip()
        
        if grandparent_title and grandparent_title != titulo_item:
            titulo_programa = f"{grandparent_title} - {titulo_item}"
        else:
            titulo_programa = titulo_item if titulo_item else "Programação Plex"

        resumo_programa = item.get("summary", "").strip()

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
            
            if id_limpo == "unknown" or id_limpo.startswith("unsupported"):
                continue

            nome_canal = media.get("channelTitle", media.get("channelShortTitle", "Plex TV")).strip()

            if id_limpo not in canais_salvos:
                logo_canal = media.get("channelThumb", media.get("channelArt", ""))
                canais_salvos[id_limpo] = {
                    "name": nome_canal,
                    "logo": logo_canal
                }

            prog_tag = ET.Element("programme", start=start_formatted, stop=end_formatted, channel=id_limpo)
            ET.SubElement(prog_tag, "title", lang="pt").text = titulo_programa
            
            if resumo_programa:
                ET.SubElement(prog_tag, "desc", lang="pt").text = resumo_programa
                
            programas_xml.append(prog_tag)

    # Escreve as tags dos canais (<channel>)
    for cid, cinfo in canais_salvos.items():
        channel_tag = ET.SubElement(root, "channel", id=cid)
        ET.SubElement(channel_tag, "display-name").text = cinfo["name"]
        if cinfo["logo"]:
            ET.SubElement(channel_tag, "icon", src=cinfo["logo"])

    # Anexa todos os blocos de programação (<programme>)
    for p_tag in programas_xml:
        root.append(p_tag)

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ", level=0)
    tree.write(nome_arquivo_xml, encoding="utf-8", xml_declaration=True)
    
    print(f"[+] Concluído! O arquivo '{nome_arquivo_xml}' foi gerado com {len(programas_xml)} inserções de programação.")

if __name__ == "__main__":
    dados_grade = buscar_epg_grade_oficial()
    if dados_grade:
        converter_para_xmltv(dados_grade, ARQUIVO_XML)
