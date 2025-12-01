import asyncio
import uuid
from crawl4ai import AsyncWebCrawler, CacheMode, BrowserConfig, CrawlerRunConfig
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator


async def internal_links_extraction():
    browser_config = BrowserConfig(headless=False, verbose=True)
    internal_links = []
    session_id = str(uuid.uuid4())

    async with AsyncWebCrawler(config=browser_config) as crawler:
        for i in range(1, 7):

            if i==1:
                url = "https://www.oss.nsk.com/products/bearing-accessories/nut.html"
            else :
                url=f"https://www.oss.nsk.com/products/bearing-accessories/nut.html?p={i}"
            

            run_config = CrawlerRunConfig(
                word_count_threshold=10,
                cache_mode=CacheMode.DISABLED,
                exclude_domains=[],
                exclude_social_media_domains=[],
                exclude_external_links=True,
                exclude_social_media_links=True,
                scroll_delay=1.5,
                delay_before_return_html=5.0,
                scan_full_page=True,
                simulate_user=True,
                process_iframes=True,
                only_text=False,
                check_robots_txt=False,
                markdown_generator=DefaultMarkdownGenerator(),
                exclude_all_images=True,
                session_id=session_id,
                css_selector="a.trigger-view-product"
            )

            result = await crawler.arun(url=url, config=run_config)

            if result.success:
                links = result.links.get("internal", [])
                print(f"Page {i} successful — found {len(links)} internal links")

                for link in links:
                    href = link.get("href")
                    if href and href not in internal_links:
                        internal_links.append(href)

            else:
                print(f"Crawling failed for page {i}")
                break

    with open("bearing_nuts_urls.txt", "w", encoding="utf-8") as f:
        for link in internal_links:
            f.write(link + "\n")

    print(f"Saved {len(internal_links)} unique product URLs to bearing_nuts_urls.txt")
    return internal_links



asyncio.run(internal_links_extraction())
