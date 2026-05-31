import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

# ==============================================================================
# CONFIGURAÇÕES - USANDO SEUS DADOS REAIS
# ==============================================================================
PLEX_TOKEN = os.environ.get("PLEX_TOKEN", "rwyekjwc6k439C_JV2HW")
LANGUAGE = "pt-BR"                      
ARQUIVO_XML = "plex_epg_brasil.xml"      
# ==============================================================================

def buscar_epg_plex():
    """Faz a requisição dos dados de EPG corrigindo o cálculo de tempo para evitar Erro 400."""
    agora = datetime.now(timezone.utc)
    
    # CORREÇÃO DO ERRO 400: Arredonda o timestamp atual para o início da hora cheia.
    # Algumas APIs do Plex rejeitam segundos quebrados no meio do "Grid".
    hora_arredondada = agora.replace(minute=0, second=0, microsecond=0)
    
    begins_at = int(hora_arredondada.timestamp())
    # Puxa apenas as próximas 12 horas (reduzir o bloco evita sobrecarga e Erro 400)
    ends_at = int((hora_arredondada + timedelta(hours=12)).timestamp())

    url = "https://epg.provider.plex.tv/grid"

    params = {
        "beginsAt": begins_at,
        "endsAt": ends_at,
        "vhs": "1",
        "X-Plex-Language": LANGUAGE
    }

    headers = {
        "X-Plex-Token": PLEX_TOKEN,
        "X-Plex-Language": LANGUAGE,
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Origin": "https://app.plex.tv",
        "Referer": "https://app.plex.tv/"
    }

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Conectando à API do Plex Grid...")
    print(f"[*] Período solicitado: {hora_arredondada.strftime('%H:%M')} até {(hora_arredondada + timedelta(hours=12)).strftime('%H:%M')} UTC")
    
    try:
        response = requests.get(url, params=params, headers=headers)
        if response.status_code == 200:
            print("[+] Dados brutos recebidos com sucesso!")
            return response.json()
        else:
            print(f"[!] Erro na requisição. Status Code: {response.status_code}")
            print(f"[*] Resposta do servidor: {response.text[:200]}") # Mostra o motivo do erro 400 se houver
            return None
    except Exception as e:
        print(f"[!] Erro de conexão: {e}")
        return None


def converter_para_xmltv(dados_json, nome_arquivo_xml):
    """Processa a lista profunda extraída do JSON e monta o formato XMLTV."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Gerando árvore XML...")
    
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
            
            if id_limpo == "unknown" or id_limpo.startswith("unsupported"):
                continue

            nome_canal = media.get("channelTitle", media.get("channelShortTitle", "Plex TV"))

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


if __name__ == "__main__":
    dados_epg = buscar_epg_plex()
    if dados_epg:
        converter_para_xmltv(dados_epg, ARQUIVO_XML)
