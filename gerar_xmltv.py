import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

# ==============================================================================
# CREDENCIAIS ATIVAS DA SUA CONTA
# ==============================================================================
PLEX_TOKEN = "sNqzhzKzgfC6omzZUrhw"
CLIENT_ID = "7c9fe305-85d0-4ef2-8fb9-e1a77b797190"
LANGUAGE = "pt-BR"                      
ARQUIVO_XML = "epg_brasil.xml"      
# ==============================================================================

def descobrir_channel_grid_key():
    """Busca o ID do lineup ativo na sua conta para substituir o 'default' quebrado."""
    url = "https://epg.provider.plex.tv/lineups"
    
    headers = {
        "Host": "epg.provider.plex.tv",
        "Accept": "application/json",
        "X-Plex-Language": LANGUAGE,
        "X-Plex-Client-Identifier": CLIENT_ID,
        "X-Plex-Token": PLEX_TOKEN,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
    }
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Descobrindo a nova chave de Grid da sua conta...")
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            dados = response.json()
            # Tenta capturar o ID dentro do MediaContainer
            lineups = dados.get("MediaContainer", {}).get("Lineup", [])
            if lineups:
                chave_encontrada = lineups[0].get("id")
                print(f"[+] Nova chave encontrada com sucesso: '{chave_encontrada}'")
                return chave_encontrada
            
            # Fallback caso a estrutura seja uma lista direta
            if isinstance(dados, list) and len(dados) > 0:
                chave_encontrada = dados[0].get("id") or dados[0].get("key")
                print(f"[+] Nova chave encontrada (fallback): '{chave_encontrada}'")
                return chave_encontrada
                
        print("[!] Não foi possível mapear uma chave no endpoint /lineups. Usando 'plex' como plano B.")
        return "plex"
    except Exception as e:
        print(f"[!] Erro ao varrer chave dinâmica: {e}")
        return "plex"

def buscar_epg_grid_correto(grid_key):
    """Busca a grade de 12h usando a chave dinâmica detectada para evitar Erro 400."""
    agora = datetime.now(timezone.utc)
    hora_arredondada = agora.replace(minute=0, second=0, microsecond=0)
    
    begins_at = int(hora_arredondada.timestamp())
    ends_at = int((hora_arredondada + timedelta(hours=12)).timestamp())

    url = "https://epg.provider.plex.tv/grid"
    
    # CORREÇÃO: Substituímos o 'default' inválido pela chave real retornada pelo Plex
    params = {
        "channelGridKey": str(grid_key),
        "beginsAt": str(begins_at),
        "endsAt": str(ends_at),
        "vhs": "1"
    }

    headers = {
        "Host": "epg.provider.plex.tv",
        "Connection": "keep-alive",
        "Accept": "application/json",
        "X-Plex-Language": LANGUAGE,
        "X-Plex-Client-Identifier": CLIENT_ID,
        "X-Plex-Token": PLEX_TOKEN,
        "X-Plex-Device": "Windows",
        "X-Plex-Platform": "Chrome",
        "X-Plex-Product": "Plex Mediaverse",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
        "Origin": "https://watch.plex.tv",
        "Referer": "https://watch.plex.tv/"
    }

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Baixando a grade do /grid com a chave atualizada...")
    try:
        response = requests.get(url, params=params, headers=headers, timeout=20)
        if response.status_code == 200:
            print("[+] Sucesso! Grade de programação baixada sem bloqueios.")
            return response.json()
        else:
            print(f"[!] Erro na requisição final. Status: {response.status_code}")
            print(f"[*] Resposta detalhada: {response.text[:300]}")
            return None
    except Exception as e:
        print(f"[!] Erro de comunicação com o Grid: {e}")
        return None

def converter_para_xmltv(dados_json, nome_arquivo_xml):
    """Mapeia os dados descarregados e monta o arquivo XMLTV padrão."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Gerando árvore estruturada XMLTV...")
    root = ET.Element("tv", generator_info_name="Plex Dynamic Grid Extractor")
    canais_salvos = {}
    programas_xml = []

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
    print(f"[+] Concluído! O arquivo '{nome_arquivo_xml}' foi atualizado com {len(programas_xml)} programas.")

if __name__ == "__main__":
    # Passo 1: Descobre dinamicamente a chave certa que substitui o "default"
    chave_grid = descobrir_channel_grid_key()
    
    # Passo 2: Faz a requisição da grade usando a chave detectada
    dados_grade = buscar_epg_grid_correto(chave_grid)
    
    # Passo 3: Converte o resultado para XMLTV
    if dados_grade:
        converter_para_xmltv(dados_grade, ARQUIVO_XML)
