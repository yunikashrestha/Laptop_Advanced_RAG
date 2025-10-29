import asyncio
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

async def scrape_laptop_urls():
    brow_config = BrowserConfig(headless=False)

    config_run = CrawlerRunConfig(
        word_count_threshold=50,
        markdown_generator=DefaultMarkdownGenerator(),
        excluded_tags=["header", "nav", "footer", "aside", "form", "script", "style"],
        only_text=False,
        remove_forms=True,
        parser_type="lxml",

        disable_cache=False,
        no_cache_read=False,
        no_cache_write=False,
        method="GET",
        check_robots_txt=False,
        delay_before_return_html=10.0,
        mean_delay=2.0,
        max_range=6.0,
        semaphore_count=5,
        js_code="""
        async function clickShowMore() {
            for (let i = 0; i < 50; i++) {  // Try up to 10 times
                let btn = document.querySelector('button.action.primary.mst-scroll__button._next');
                if (!btn) {
                    console.log("No more 'Show more' button found after " + i + " clicks.");
                    break;
                }
                btn.click();
                console.log("Clicked 'Show 20 more products' button #" + (i + 1));
                await new Promise(r => setTimeout(r, 4000));  // wait 4s for new products to load
            }
            window.scrollTo(0, document.body.scrollHeight);
            return true;
        }
        clickShowMore();
        """,
        scan_full_page=True,
        scroll_delay=1.5,
        max_scroll_steps=3,
        process_iframes=True,
        remove_overlay_elements=True,
        simulate_user=True,

        exclude_social_media_domains=[],
        exclude_external_links=True,
        exclude_social_media_links=True,
        exclude_domains=[],
        css_selector="li.item.product.product-item",
        target_elements=['li'], 
        verbose=True,
        capture_console_messages=False,
        capture_network_requests=False,
    )

    async with AsyncWebCrawler(config=brow_config) as crawler:
        # Crawl the page
        results = await crawler.arun(
            url="https://mudita.com.np/laptops-nepal.html",
            config=config_run
        )

        if results.success:
            #extracting all the internal links
            internal_links = []
            for result in results:
                for link in result.links["internal"]:
                    print(link)
                    url = link.get("href")
                    print(url)
                    internal_links.append(url+ "\n")
                    with open("mudita_all_laptop_links.txt",'a',encoding = "utf-8") as f:
                        f.write(url+"\n")

async def main():
    await scrape_laptop_urls()

if __name__ == "__main__":
    asyncio.run(main())

if __name__ == "__main__":
    asyncio.run(main())
