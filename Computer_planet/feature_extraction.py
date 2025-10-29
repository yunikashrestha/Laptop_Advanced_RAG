import asyncio
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from link_extraction import internal_links_extraction
async def scrape_multiple_urls():
    brows_config = BrowserConfig(headless=False, verbose=True)

    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        markdown_generator=DefaultMarkdownGenerator(),
        word_count_threshold=20,
        only_text=False,# div.woocommerce-product-details__short-description>p:nth-child(1) section[data-id='7c5ae2c']>div>div>div>div:nth-child(2) a[href='#tab-specification'],
        css_selector="h1.product_title.entry-title, div.woocommerce-product-details__short-description, p.price>span>ins,div#tab-specification ",
        excluded_tags=["header","nav","footer","form","style","script"],
        scan_full_page=True,
        js_code="""
            window.scrollTo(0,document.body.scrollHeight);
            document.querySelector('a[href="#tab-specification"]').click()
            return true;

            
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
    internal_links=await internal_links_extraction()

    async with AsyncWebCrawler(config=brows_config) as crawler:

        for url in internal_links:
            result = await crawler.arun(url=url, config=run_config)

            if result.success:
                print("*******Crawled Successfully*******")

                # Save each product description in a single Markdown file (appending)
                with open("all_laptop_feature_computerplanet.md", "a", encoding="utf-8") as f:
                    f.write(f'{result.markdown} \n\n url:{url} \n\n -----END OF PRODUCT-----\n\n')
                    
                    
                
            else:
                print(f"*******Failed to fetch URL {url}*******")

async def main():
    await scrape_multiple_urls()

if __name__ == "__main__":
    asyncio.run(main())