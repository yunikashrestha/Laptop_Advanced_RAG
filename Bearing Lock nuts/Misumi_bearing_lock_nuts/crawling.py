import asyncio
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, LLMConfig
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy
from bs4 import BeautifulSoup
import pandas as pd
import json
import uuid
import re
import os
from dotenv import load_dotenv
import time


async def crawling_part_numbers():
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")  
    base_url = "https://vn.misumi-ec.com/vona2/detail/221005675716/?list=PageCategory"
    session_id = str(uuid.uuid4())

    browser_config = BrowserConfig(
        headless=False,
        verbose=True,
        enable_stealth=False,
        viewport_width=1400,
        viewport_height=1000,
    )

    # INITIAL JS FOR SCHEMA 
    schema_js = """
        return new Promise((resolve) => {

            setTimeout(() => {
                const lang = document.querySelector('a[lang="en"]');
                if (lang) lang.click();
            }, 1500);

            setTimeout(() => {
                const tab = document.querySelector('a#codeList');
                if (tab) tab.click();
            }, 6000);

            setTimeout(() => {
                const container = document.querySelector("div.PartNumberList_mainOuter__d74Qg");
                if (!container) { resolve(false); return; }

                const part = document.querySelectorAll("tr.PartNumberColumn_dataRow__43D6Y");
                const price = document.querySelectorAll("tr.PartNumberAsideColumns_dataRow__OUw8N");
                const spec = document.querySelectorAll("tr.PartNumberSpecColumns_dataRow__M4B4a");

                const count = Math.min(part.length, price.length, spec.length);

                for (let i = 0; i < count; i++) {
                    const row = document.createElement("div");
                    row.classList.add("mergedRow");
                    row.appendChild(part[i].cloneNode(true));
                    row.appendChild(price[i].cloneNode(true));
                    row.appendChild(spec[i].cloneNode(true));
                    container.appendChild(row);
                }
                resolve(true);
            }, 9000);

        });
    """

    schema_config = CrawlerRunConfig(
        word_count_threshold=10,
        cache_mode=CacheMode.DISABLED,
        delay_before_return_html=30.0,
        js_code=schema_js,
        session_id=session_id,
    )

    # START CRAWLING 
    all_rows = []


    async with AsyncWebCrawler(config=browser_config) as crawler:

        # 1) Load page for schema
        schema_result = await crawler.arun(url=base_url, config=schema_config)
        soup = BeautifulSoup(schema_result.html, "html.parser")
        container = soup.select_one("div.PartNumberList_mainOuter__d74Qg")
        css_html = str(container)
        # Product name
        title = soup.select_one("h1.PageHeading_wrap__K1c1n")
        subcat = title.get_text(strip=True) if title else "unknown"
        # 2) Generate Schema
        query = (
            "Generate a schema to extract product details. "
            "Column names MUST match exactly. "
            "Split 'Part Number' into two keys: Part Number Name & Part Number URL. "
            "Use CSS only, base selector must be 'div.mergedRow'."
        )
        
        schema = JsonCssExtractionStrategy.generate_schema(
            html=css_html,
            schema_type="css",
            query=query,
            llm_config=LLMConfig(provider="gemini/gemini-2.5-flash", api_token=api_key)
        )
      
        print(schema)
        print("\nSCHEMA GENERATED.\n")

        # PAGINATION JS
        pagination_js = """
            return new Promise((resolve) => {

                setTimeout(() => {
                    const tab = document.querySelector("a#codeList");
                    if (tab) tab.click();
                }, 800);

                setTimeout(() => {
                    const nextBtn = document.querySelector("a.Pagination_next__5fRp8");
                    if (!nextBtn) { resolve(false); return; }
                    nextBtn.click();
                }, 2000);

                setTimeout(() => {
                    const container = document.querySelector("div.PartNumberList_mainOuter__d74Qg");
                    if (!container) { resolve(false); return; }

                    container.querySelectorAll("div.mergedRow").forEach(n => n.remove());

                    const part = document.querySelectorAll("tr.PartNumberColumn_dataRow__43D6Y");
                    const price = document.querySelectorAll("tr.PartNumberAsideColumns_dataRow__OUw8N");
                    const spec = document.querySelectorAll("tr.PartNumberSpecColumns_dataRow__M4B4a");

                    const count = Math.min(part.length, price.length, spec.length);

                    for (let i = 0; i < count; i++) {
                        const row = document.createElement("div");
                        row.classList.add("mergedRow");
                        row.appendChild(part[i].cloneNode(true));
                        row.appendChild(price[i].cloneNode(true));
                        row.appendChild(spec[i].cloneNode(true));
                        container.appendChild(row);
                    }

                    resolve(true);
                }, 5000);

            });
        """

        # LOOP THROUGH PAGES 
        page = 1
        has_next = True
     
        while has_next:
            

            print(f"\nScraping Page {page} ...\n")

            extract_config = CrawlerRunConfig(
                session_id=session_id,
                js_only=True,
                delay_before_return_html=10.0,
                extraction_strategy=JsonCssExtractionStrategy(schema=schema),
                js_code=None if page == 1 else pagination_js
            )

            
            result = await crawler.arun(url=base_url, config=extract_config)
            # Store data  
            html = BeautifulSoup(result.html, "html.parser")
            rows = json.loads(result.extracted_content)
            all_rows.extend(rows)
            print(f" → Page {page} rows: {len(rows)}")
            

            # Check next button
            next_btn = html.select_one("a.Pagination_next__5fRp8")
            if next_btn is None:
                has_next = False
            else:
                page += 1

        df = pd.DataFrame(all_rows)
        subcat = re.sub(r"[ , / ( ) : -]+", "_", subcat).lower()
        filename = f"Bearing_lock_nuts_{subcat}.xlsx"
        df.to_excel(filename, index=False)

        print(f"\nSaved: {filename}")
        print(f"Total rows extracted: {len(all_rows)}")


if __name__ == "__main__":
    asyncio.run(crawling_part_numbers())
