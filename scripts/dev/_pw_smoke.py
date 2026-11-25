import asyncio


async def main() -> None:
    from playwright.async_api import async_playwright

    url = (
        "https://trakheesi.dubailand.gov.ae/rev/madmoun/listing/validation"
        "?khevJujtDig=qnzrseuxs57ltl64cp5jt82t2ip0cbe2o54hxgcqfpngnsxme"
    )
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="msedge", headless=False)
        page = await browser.new_page()
        await page.goto(url, wait_until="networkidle", timeout=120000)
        btn = page.locator("button").filter(has_text="View Details")
        print("buttons", await btn.count())
        if await btn.count():
            await btn.first.click(force=True, timeout=30000)
            await page.wait_for_timeout(10000)
        text = await page.evaluate("document.body.innerText")
        print("len", len(text))
        print(text[:2000])
        await browser.close()


asyncio.run(main())