import asyncio
import os
import pandas as pd
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

async def scrape_and_save_features():
    txt_filename = "bearing_nuts_urls.txt"
    if not os.path.exists(txt_filename):
        print(f"Error: {txt_filename} not found.")
        return

    with open(txt_filename, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip()]

    print(f"Loaded {len(urls)} URLs from {txt_filename}")

    browser_config = BrowserConfig(headless=True, verbose=False)
    
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        css_selector="td.list-attr-product", 
        excluded_tags=["header", "footer", "script", "form", "style", "nav", "aside"],
        scan_full_page=True,
        process_iframes=True,
        delay_before_return_html=2.0,
    )

    all_products_data = []

    async with AsyncWebCrawler(config=browser_config) as crawler:
        for i, url in enumerate(urls):
            print(f"[{i+1}/{len(urls)}] Crawling: {url}")
            
            try:
                result = await crawler.arun(url=url, config=run_config)
                
                if result.success:
                    soup = BeautifulSoup(result.cleaned_html, 'html.parser')
                    
                    product_name = url.split('/')[-1].replace('.html', '').upper()
                    
                    product_record = {
                        "Product Name": product_name,
                        "URL": url
                    }
                    
                    rows = soup.find_all('tr')
                    
                    skipping_associated_section = False
                    
                    for row in rows:
                        cells = row.find_all(['td', 'th'])
                        row_text = [cell.get_text(strip=True) for cell in cells]
                        
                        full_row_string = " ".join(row_text)

                        if "Associated products" in full_row_string:
                            skipping_associated_section = True
                            continue

                        if skipping_associated_section:
                            if "Shaft diameter" in full_row_string or \
                               "Basic Dimensions" in full_row_string or \
                               "Mass" in full_row_string or \
                               "Abutment dimensions" in full_row_string or \
                               "Bolts" in full_row_string:
                                skipping_associated_section = False
                            else:
                                continue

                        if len(row_text) >= 2: 
                            code_col = row_text[0]       
                            value_col = row_text[1]      
                            unit_col = row_text[2] if len(row_text) > 2 else ""       
                            desc_col = row_text[3] if len(row_text) > 3 else ""       

                            if value_col == product_name:
                                continue

                            if "PDF DOWNLOAD" in code_col:
                                continue

                            if value_col == "" and unit_col == "":
                                continue

                            if desc_col:
                                excel_header = f"{desc_col} ({code_col})"
                            else:
                                excel_header = code_col

                            final_value = f"{value_col} {unit_col}".strip()
                            
                            product_record[excel_header] = final_value
                    
                    if product_record:
                        all_products_data.append(product_record)
                
                else:
                    print(f"Failed to fetch {url}")

            except Exception as e:
                print(f"Error processing {url}: {e}")

    if all_products_data:
        print("Converting all data to Excel...")
        try:
            df = pd.DataFrame(all_products_data)
            
            cols = list(df.columns)
            
            if "URL" in cols:
                cols.insert(0, cols.pop(cols.index("URL")))
            if "Product Name" in cols:
                cols.insert(0, cols.pop(cols.index("Product Name")))
            
            df = df[cols]

            excel_filename = "nsk_bulk_data.xlsx"
            df.to_excel(excel_filename, index=False)
            print(f"Successfully saved {len(all_products_data)} products to {excel_filename}")
            
        except Exception as e:
            print(f"Error converting to Excel: {e}")
    else:
        print("No data extracted from any URLs.")

if __name__ == "__main__":
    asyncio.run(scrape_and_save_features())