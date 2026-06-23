import os
import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

# ==============================================================================
# CONFIGURAÇÕES TÉCNICAS - FIXAÇÃO BRASIL
# ==============================================================================
ARQUIVO_XML = "epg_brasil.xml"
URL_CATEGORIA = "https://watch.plex.tv/pt-BR/live-tv/category/featured"
# ==============================================================================

def processar_epg_regex():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Iniciando requisição simulada via GitHub Actions...")
    
    # Injeção de cabeçalhos geográficos para forçar o catálogo brasileiro (BR)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        # Força os servidores de CDN (Edge) a tratarem o IP como vindo do Brasil
        "X-Forwarded-For": "177.42.128.1",  # IP válido de operadora brasileira (Claro/Embratel BR)
        "X-Real-IP": "177.42.128.1",
        "CF-IPCountry": "BR",
        "X-Country-Code": "BR",
        "Origin": "https://watch.plex.tv",
        "Referer": "https://watch.plex.tv/pt-BR/live-tv"
    }
    
    try:
        response = requests.get(URL_CATEGORIA, headers=headers, timeout=20)
        if response.status_code != 200:
            print(f"[!] Falha na requisição. Código: {response.status_code}")
            return
            
        html_puro = response.text
        
        # Validação rápida de idioma no HTML capturado
        if 'masterchef-brasil' in html_puro or 'jovem-pan' in html_puro:
            print("[+] Sucesso! O servidor Plex respondeu com o catálogo nativo do Brasil.")
        else:
            print("[!] Alerta: O Plex ainda pode estar aplicando restrições geográficas baseadas no IP do GitHub.")

        print("[*] Extraindo canais e referências de transmissão...")

        # Captura de slugs e metadados de identificação
        padrao_canal = r'href="/pt-BR/live-tv/channel/([^"]+)"[^>]*>.*?<img\s+alt="([^"]+)"[^*]*?src="([^"]+)"'
        canais_encontrados = re.findall(padrao_canal, html_puro, re.DOTALL)
        
        if not canais_encontrados:
            padrao_canal_fallback = r'href="/pt-BR/live-tv/channel/([^"]+)"'
            slugs_simples = re.findall(padrao_canal_fallback, html_puro)
            canais_encontrados = [(slug, slug.replace('-', ' ').title(), '') for slug in slugs_simples]

        # Captura os blocos de spans sequenciais (Programa + Grade Temporal Horária)
        padrao_programa = r'<span[^>]+title="([^"]+)"[^>]*>.*?<\/span>.*?<span[^>]+title="([^"]+)"[^>]*>'
        programas_encontrados = re.findall(padrao_programa, html_puro, re.DOTALL)

        print(f"[+] Total indexado no Servidor: {len(canais_encontrados)} canais e {len(programas_encontrados)} programas.")

        # Construção da árvore estruturada do guia XMLTV
        root = ET.Element("tv", generator_info_name="Plex Regional Actions Engine")
        agora = datetime.now(timezone.utc)
        
        start_default = agora.strftime('%Y%m%d%H%M%S +0000')
        end_default = (agora + timedelta(hours=4)).strftime('%Y%m%d%H%M%S +0000')

        canais_mapeados = {}
        for slug, nome, logo in canais_encontrados:
            slug_limpo = slug.strip()
            if slug_limpo not in canais_mapeados:
                channel_tag = ET.SubElement(root, "channel", id=slug_limpo)
                ET.SubElement(channel_tag, "display-name").text = nome.strip()
                if logo:
                    ET.SubElement(channel_tag, "icon", src=logo.strip())
                canais_mapeados[slug_limpo] = []

        lista_slugs = list(canais_mapeados.keys())
        
        if lista_slugs:
            for idx, (titulo_p, tempo_p) in enumerate(programas_encontrados):
                slug_alvo = lista_slugs[idx % len(lista_slugs)]
                start, end = start_default, end_default
                
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

        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ", level=0)
        tree.write(ARQUIVO_XML, encoding="utf-8", xml_declaration=True)
        print(f"[+] Sincronização concluída com sucesso. Arquivo '{ARQUIVO_XML}' atualizado no repositório.")

    except Exception as e:
        print(f"[!] Erro crítico na execução da Action: {e}")

if __name__ == "__main__":
    processar_epg_regex()
