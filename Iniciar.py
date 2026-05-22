import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from deep_translator import GoogleTranslator

# ==============================================================================
# CONFIGURAÇÕES
# ==============================================================================
PLEX_TOKEN = os.environ.get("PLEX_TOKEN", "rwyekjwc6k439C_JV2HW")
LANGUAGE = "pt-BR"                  
ARQUIVO_XML = "epg_brasil.xml" 
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
        "X-Plex-Language": LANGUAGE,
        "Accept-Language": "pt-BR,pt;q=0.9",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    try:
        response = requests.get(url, params=params, headers=headers)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"[!] Erro de conexão: {e}")
        return None

def traduzir_texto(texto):
    """Traduz textos automaticamente para o português."""
    if not texto or texto.strip() == "":
        return ""
    try:
        return GoogleTranslator(source='auto', target='pt').translate(texto)
    except Exception:
        return texto

def converter_para_xmltv(dados_json, nome_arquivo_xml):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Corrigindo estrutura de Títulos e Descrições...")
    
    root = ET.Element("tv", generator_info_name="Plex Live TV EPG Extractor")
    canais_salvos = {}
    programas_xml = []

    metadata_list = dados_json.get("MediaContainer", {}).get("Metadata", [])

    for item in metadata_list:
        # Extração das chaves do Plex tirando espaços vazios
        grandparent_title = item.get("grandparentTitle", "").strip() # Ex: "MasterChef Brasil", "FIFA+"
        title_original = item.get("title", "").strip()               # Ex: "Episódio 1", "História de um Assassinato"
        summary_original = item.get("summary", "").strip()           # Sinopse/Descrição real

        # --- NOVA LÓGICA DE DETECÇÃO DE TÍTULO ---
        # Se o título for genérico ("Episódio X") e tivermos o nome do show/canal (grandparent_title)
        if "Episódio" in title_original or "Episode" in title_original:
            if grandparent_title:
                # Se houver uma sinopse detalhada, o título fica "Nome do Show - Episódio X"
                if summary_original and not summary_original.startswith("Episódio"):
                    titulo_programa_bruto = f"{grandparent_title} - {title_original}"
                    resumo_programa_bruto = summary_original
                else:
                    # Se não houver sinopse, pegamos o texto do summary (onde o Plex costuma guardar "Brasil x Itália")
                    # e jogamos como título principal para não ficar apenas "Episódio 1"
                    titulo_programa_bruto = f"{grandparent_title} - {summary_original}" if summary_original else f"{grandparent_title} - {title_original}"
                    resumo_programa_bruto = title_original
            else:
                titulo_programa_bruto = title_original
                resumo_programa_bruto = summary_original
        else:
            # Caso padrão (Filmes e programas jornalísticos que já vem com título correto)
            titulo_programa_bruto = title_original if title_original else grandparent_title
            resumo_programa_bruto = summary_original

        # Tradução final dos campos tratados
        titulo_programa = traduzir_texto(titulo_programa_bruto)
        resumo_programa = traduzir_texto(resumo_programa_bruto)

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
            
            # Garante a inserção das tags estruturadas
            ET.SubElement(prog_tag, "title", lang="pt").text = titulo_programa
            
            if resumo_programa:
                ET.SubElement(prog_tag, "desc", lang="pt").text = resumo_programa
                
            programas_xml.append(prog_tag)

    # Monta o arquivo XMLTV
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
    
    print(f"[+] Sucesso! Arquivo '{nome_arquivo_xml}' atualizado com títulos corrigidos.")

if __name__ == "__main__":
    dados_epg = buscar_epg_plex()
    if dados_epg:
        converter_para_xmltv(dados_epg, ARQUIVO_XML)
