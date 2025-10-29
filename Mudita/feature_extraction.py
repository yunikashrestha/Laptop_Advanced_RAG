# import asyncio
# from crawl4ai import AsyncWebCrawler,BrowserConfig,CrawlerRunConfig,CacheMode
# from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

# async def scrape_urls():
#     brows_config=BrowserConfig(headless=True,verbose=True)

#     run_config=CrawlerRunConfig(
#         cache_mode=CacheMode.BYPASS,
#         markdown_generator=DefaultMarkdownGenerator(),
#         word_count_threshold=20,
#         only_text=False,
#         css_selector="img.no-sirv-lazy-load, span.base, span.price:nth-of-type(1), div.specifications-content ",
#         excluded_tags=["header","nav","footer","style","script"],
#         scan_full_page=True,
#         js_code="""
#             window.scrollTo(0,document.body.scrollHeight);
#             return True;
#         """,
#         scroll_delay=1.5,
#         delay_before_return_html=10.0,
#         max_scroll_steps=5,
#         remove_overlay_elements=True,
#         capture_console_messages=False,
#         capture_network_requests=False,
#     )
#     with open("all_links.txt","r",encoding="utf-8") as f:
#         urls=[line.strip() for line in f if line.strip()]

#     async with AsyncWebCrawler(config=brows_config) as crawler:
#         result= await crawler.arun(url="https://mudita.com.np/asus-vivobook-15-i5-12th-gen-price-in-nepal.html",config=run_config)

#         if result.success:
#             print("Crawled Sucessfully")
#             print(result.markdown)

#         with open("single_product.txt","a",encoding="utf-8") as f:
#             f.write(result.markdown)
#         print("Saved Successfully")

# if __name__=="__main__" :       
#     asyncio.run(scrape_urls())
# import asyncio
# from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
# from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

# async def scrape_urls():
#     brows_config = BrowserConfig(headless=True, verbose=True)

#     run_config = CrawlerRunConfig(
#         cache_mode=CacheMode.BYPASS,
#         markdown_generator=DefaultMarkdownGenerator(),
#         word_count_threshold=20,
#         only_text=False,
#         css_selector="img.no-sirv-lazy-load, span.base, span#product-price-1590 span.price:nth-child(1), div.specifications-content",
#         excluded_tags=["header", "nav", "footer", "style", "script"],
#         scan_full_page=True,
#         js_code="""
#             window.scrollTo(0, document.body.scrollHeight);
#             return true;
#         """,
#         scroll_delay=1.5,
#         delay_before_return_html=20.0,
#         max_scroll_steps=5,
#         remove_overlay_elements=True,
#         capture_console_messages=False,
#         capture_network_requests=False,
#         simulate_user=True
#     )

#     with open("all_links.txt", "r", encoding="utf-8") as f:
#         urls = [line.strip() for line in f if line.strip()]

#     async with AsyncWebCrawler(config=brows_config) as crawler:
#         # Example: testing one URL
#         result = await crawler.arun(
#             url="https://mudita.com.np/lenovo-ideapad-slim-1-intel-celeron-price-in-nepal.html",
#             config=run_config
#         )

#         if result.success:
#             print("Crawled Successfully")

#             if result.markdown:
#                 print(result.markdown)
#                 with open("single_product.txt", "a", encoding="utf-8") as f:
#                     f.write(result.markdown)
#                     f.write("\n" + "="*80 + "\n")
#                 print("Saved Successfully")
#             else:
#                 print("No markdown content extracted (possibly empty selector).")
#         else:
#             print(f" Failed to crawl. Error: {result.error_message}")

# if __name__ == "__main__":
#     asyncio.run(scrape_urls())


import asyncio
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

async def scrape_multiple_urls():
    brows_config = BrowserConfig(headless=False, verbose=True)

    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        markdown_generator=DefaultMarkdownGenerator(),
        word_count_threshold=20,
        only_text=False,
        css_selector="h1.page-title, span#product-price-1590 span.price:nth-child(1), div.specifications-content",
        excluded_tags=["header","nav","footer","form","style","script"],
        scan_full_page=True,
        js_code="""
            window.scrollTo(0,document.body.scrollHeight);
            return True;
        """,
        scroll_delay=1.5,
        delay_before_return_html=10.0,
        max_scroll_steps=3,
        process_iframes=True,
        remove_overlay_elements=True,
        capture_console_messages=False,
        capture_network_requests=False,
    )

    # List of URLs obtained previously
    with open("mudita_all_laptop_links.txt", "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip()]

    async with AsyncWebCrawler(config=brows_config) as crawler:
        for idx, url in enumerate(urls, start=1):
            print(f"\nScraping URL {idx}/{len(urls)}: {url}")
            result = await crawler.arun(url=url, config=run_config)

            if result.success:
                print("*******Crawled Successfully*******")
                print(result.markdown)

                # Save each product description in a single Markdown file (appending)
                with open("all_laptop_feature.md", "a", encoding="utf-8") as f:
                    f.write(result.markdown + "\n")
                    f.write(f"URL: {url}\n\n")
                    f.write("="*80 + "\n")  # separator
                print(f"******Saved product {idx} description******")
            else:
                print(f"*******Failed to fetch URL {url}*******")

async def main():
    await scrape_multiple_urls()

if __name__ == "__main__":
    asyncio.run(main())
