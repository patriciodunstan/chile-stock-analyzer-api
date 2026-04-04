"""Diagnóstico de conexión a ir.sqm.com.

Prueba múltiples estrategias de conexión para identificar el problema:
1. httpx directo
2. httpx con headers diferentes
3. httpx sin verificación SSL
4. requests como alternativa

Ejecutar: python scripts/diagnose_ir_connection.py
"""
import asyncio
import sys

async def main():
    import httpx

    url = "https://ir.sqm.com/financials/quarterly-results"

    print("=" * 60)
    print("DIAGNÓSTICO DE CONEXIÓN - ir.sqm.com")
    print("=" * 60)

    # Test 1: httpx básico
    print("\n[Test 1] httpx con config estándar...")
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(url)
            print(f"  Status: {resp.status_code}")
            print(f"  Content-Type: {resp.headers.get('content-type', 'N/A')}")
            print(f"  Content length: {len(resp.text)} chars")
            if len(resp.text) < 500:
                print(f"  Body: {resp.text[:500]}")
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")

    # Test 2: httpx con headers de browser
    print("\n[Test 2] httpx con headers de browser completo...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }
    try:
        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers=headers,
            http2=False,
        ) as client:
            resp = await client.get(url)
            print(f"  Status: {resp.status_code}")
            print(f"  Content-Type: {resp.headers.get('content-type', 'N/A')}")
            print(f"  Content length: {len(resp.text)} chars")
            # Buscar links relevantes
            if resp.status_code == 200:
                text = resp.text.lower()
                pdf_count = text.count('.pdf')
                xlsx_count = text.count('.xlsx')
                print(f"  Links .pdf encontrados: {pdf_count}")
                print(f"  Links .xlsx encontrados: {xlsx_count}")

                # Mostrar primeros links de descarga
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, "html.parser")
                links = soup.find_all("a", href=True)
                download_links = [
                    (l.get_text(strip=True)[:80], l["href"])
                    for l in links
                    if any(ext in l["href"].lower() for ext in ['.pdf', '.xlsx', '.xls'])
                ]
                print(f"  Links de descarga: {len(download_links)}")
                for text, href in download_links[:10]:
                    print(f"    - [{text}] → {href[:100]}")
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")

    # Test 3: DNS check
    print("\n[Test 3] DNS resolution...")
    try:
        import socket
        ip = socket.gethostbyname("ir.sqm.com")
        print(f"  ir.sqm.com → {ip}")
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")

    # Test 4: Probar URL alternativa (SQM a veces usa subdominios diferentes)
    alt_urls = [
        "https://www.sqm.com/en/investors/",
        "https://ir.sqm.com/",
        "https://ir.sqm.com/financials/quarterly-results",
    ]
    print("\n[Test 4] URLs alternativas...")
    for alt_url in alt_urls:
        try:
            async with httpx.AsyncClient(
                timeout=15.0,
                follow_redirects=True,
                headers=headers,
            ) as client:
                resp = await client.get(alt_url)
                print(f"  {alt_url}")
                print(f"    Status: {resp.status_code}, Size: {len(resp.text)} chars")
                if resp.status_code == 200 and len(resp.text) > 1000:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(resp.text, "html.parser")
                    title = soup.title.string if soup.title else "N/A"
                    print(f"    Title: {title}")
        except Exception as e:
            print(f"  {alt_url}")
            print(f"    ERROR: {type(e).__name__}: {e}")

    # Test 5: Comprobar si la página usa JavaScript rendering
    print("\n[Test 5] Análisis de contenido...")
    try:
        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers=headers,
        ) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                text = resp.text
                # Indicadores de SPA/JS rendering
                has_react = "react" in text.lower() or "__NEXT" in text
                has_angular = "ng-app" in text or "angular" in text.lower()
                has_noscript = "<noscript" in text.lower()
                has_js_required = "javascript" in text.lower() and "enable" in text.lower()

                print(f"  React/Next.js: {has_react}")
                print(f"  Angular: {has_angular}")
                print(f"  <noscript> tag: {has_noscript}")
                print(f"  JS required msg: {has_js_required}")

                # Ver si hay un div vacío (señal de SPA)
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(text, "html.parser")
                main = soup.find("main") or soup.find("div", id="root") or soup.find("div", id="app")
                if main:
                    inner_text = main.get_text(strip=True)
                    print(f"  Main content chars: {len(inner_text)}")
                    if len(inner_text) < 100:
                        print("  ⚠️  CONTENIDO VACÍO - Probable SPA con JS rendering")
                        print("     El scraper necesita un browser headless (Playwright/Selenium)")
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
