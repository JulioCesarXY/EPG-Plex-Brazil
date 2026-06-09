import os
import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

# ==============================================================================
# CONFIGURAÇÕES PRONTAS PARA O PYDROID 3
# ==============================================================================
ARQUIVO_XML = "plex_epg_brasil.xml"
URL_CATEGORIA = "https://watch.plex.tv/pt-BR/live-tv/category/featured"
# ==============================================================================

def processar_epg_regex():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Baixando dados brutos do Plex...")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9"
    }
    
    try:
        response = requests.get(URL_CATEGORIA, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"[!] Falha na requisição. Código: {response.status_code}")
            return
            
        html_puro = response.text
        print("[*] Iniciando extração cirúrgica por Expressões Regulares...")

        # 1. Captura todos os canais, seus slugs e logos
        # Procura por: href="/pt-BR/live-tv/channel/slug" e a imagem logo em seguida
        padrao_canal = r'href="/pt-BR/live-tv/channel/([^"]+)"[^>]*>.*?<img\s+alt="([^"]+)"[^*]*?src="([^"]+)"'
        canais_encontrados = re.findall(padrao_canal, html_puro, re.DOTALL)
        
        if not canais_encontrados:
            # Fallback caso a tag img mude de ordem interna
            padrao_canal_fallback = r'href="/pt-BR/live-tv/channel/([^"]+)"'
            slugs_simples = re.findall(padrao_canal_fallback, html_puro)
            print(f"[*] Mapeamento alternativo: Encontrados {len(slugs_simples)} slugs de canais.")
            # Converte para o formato esperado (slug, nome, logo)
            canais_encontrados = [(slug, slug.replace('-', ' ').title(), '') for slug in slugs_simples]

        # 2. Captura os blocos de programas exatamente como nos prints do DevTools
        # Procura por spans sequenciais contendo title="Nome do Programa" e title="Horário"
        padrao_programa = r'<span[^>]+title="([^"]+)"[^>]*>.*?<\/span>.*?<span[^>]+title="([^"]+)"[^>]*>'
        programas_encontrados = re.findall(padrao_programa, html_puro, re.DOTALL)

        print(f"[+] Varredura concluída: {len(canais_encontrados)} canais e {len(programas_encontrados)} programas localizados.")

        # Montagem do XMLTV
        root = ET.Element("tv", generator_info_name="Plex Regex Engine")
        agora = datetime.now(timezone.utc)
        
        start_default = agora.strftime('%Y%m%d%H%M%S +0000')
        end_default = (agora + timedelta(hours=4)).strftime('%Y%m%d%H%M%S +0000')

        # Dicionário para garantir canais únicos
        canais_mapeados = {}
        
        # Injeta os canais na árvore XML
        for slug, nome, logo in canais_encontrados:
            slug_limpo = slug.strip()
            if slug_limpo not in canais_mapeados:
                channel_tag = ET.SubElement(root, "channel", id=slug_limpo)
                ET.SubElement(channel_tag, "display-name").text = nome.strip()
                if logo:
                    ET.SubElement(channel_tag, "icon", src=logo.strip())
                canais_mapeados[slug_limpo] = []

        # Distribui os programas encontrados entre os canais mapeados
        lista_slugs = list(canais_mapeados.keys())
        
        if lista_slugs:
            for idx, (titulo_p, tempo_p) in enumerate(programas_encontrados):
                # Vincula sequencialmente ao canal correspondente da lista
                slug_alvo = lista_slugs[idx % len(lista_slugs)]
                
                start, end = start_default, end_default
                # Tenta ajustar o horário se o Plex fornecer a string de intervalo (ex: "22:41 - 23:05")
                horarios = re.findall(r'(\d{2}):(\d{2})', tempo_p)
                if len(horarios) == 2:
                    try:
                        h1, m1 = map(int, horarios[0])
                        h2, m2 = map(int, horarios[1])
                        t1 = agora.replace(hour=h1, minute=m1, second=0, microsecond=0)
                        t2 = agora.replace(hour=h2, minute=m2, second=0, microsecond=0)
                        if t2 < t1: 
                            t2 += timedelta(days=1)
                        start = t1.strftime('%Y%m%d%H%M%S +0000')
                        end = t2.strftime('%Y%m%d%H%M%S +0000')
                    except:
                        pass

                prog_tag = ET.Element("programme", start=start, stop=end, channel=slug_alvo)
                ET.SubElement(prog_tag, "title", lang="pt").text = titulo_p.strip()
                if tempo_p:
                    ET.SubElement(prog_tag, "desc", lang="pt").text = f"Horário/Status: {tempo_p.strip()}"
                
                root.append(prog_tag)

        # Gravação física do arquivo XML
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ", level=0)
        tree.write(ARQUIVO_XML, encoding="utf-8", xml_declaration=True)
        
        print(f"[+] Sucesso! Arquivo '{ARQUIVO_XML}' atualizado com canais e programações vinculadas.")

    except Exception as e:
        print(f"[!] Erro de processamento no Pydroid: {e}")

if __name__ == "__main__":
    processar_epg_regex()
