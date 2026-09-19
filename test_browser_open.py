import asyncio
import os
import psutil
from playwright.async_api import async_playwright

def cleanup_stale_profile(profile_dir: str):
    abs_prof = os.path.abspath(profile_dir)
    norm_prof = os.path.normpath(abs_prof).lower()
    
    # 1. Kill stale playwright processes on this profile
    for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline']):
        try:
            exe = proc.info.get('exe') or ''
            cmdline = proc.info.get('cmdline') or []
            cmd_str = " ".join(cmdline).lower()
            if ('ms-playwright' in exe.lower() or 'chromium' in exe.lower()) and norm_prof in cmd_str:
                proc.kill()
        except Exception:
            pass

    # 2. Remove lock files
    if os.path.exists(abs_prof):
        for fname in ["SingletonLock", "SingletonSocket", "SingletonCookie", "lockfile"]:
            fpath = os.path.join(abs_prof, fname)
            if os.path.exists(fpath):
                try:
                    os.remove(fpath)
                except Exception:
                    pass

async def test_open():
    profile = os.path.abspath(os.path.join("..", "ShopeeVideoAutoPoster", "profile_nuocgiatparisgiasi"))
    cleanup_stale_profile(profile)
    
    p = await async_playwright().start()
    ctx = await p.chromium.launch_persistent_context(
        user_data_dir=profile,
        headless=False,
        args=["--start-maximized", "--disable-blink-features=AutomationControlled"],
        ignore_default_args=["--enable-automation"]
    )
    page = await ctx.new_page()
    await page.goto("https://banhang.shopee.vn/", wait_until="domcontentloaded")
    print(f"Browser successfully opened! Title: {await page.title()}, URL: {page.url}")
    await asyncio.sleep(4)
    await ctx.close()
    await p.stop()
    print("Browser successfully closed!")

if __name__ == "__main__":
    asyncio.run(test_open())
