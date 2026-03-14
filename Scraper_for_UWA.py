import os, time, csv, random, re, math
from playwright.sync_api import sync_playwright
from fake_useragent import UserAgent
from urllib.parse import urlparse, parse_qs, unquote
# ================= 配置区域 =================
# 自动识别环境：如果是 GitHub Actions 环境，就不设置特殊的浏览器路径
if os.environ.get("GITHUB_ACTIONS") == "true":
    print("🤖 检测到 GitHub Actions 环境，使用系统默认浏览器路径")
    SAVE_PATH = "uwa_for_ai_analysis.csv"  # 云端直接保存在根目录
else:
    # 本地开发环境配置
    print("💻 检测到本地环境")
    BROWSER_FOLDER = r"E:\pythonProject\For_fun\Scholarships_scraper\pw-browsers"
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = BROWSER_FOLDER
    SAVE_PATH = r"E:\pythonProject\For_fun\Scholarships_scraper\uwa_for_ai_analysis.csv"
# --- 灵活控制变量 ---
# None: 自动抓取全部 | 数字: 手动限制抓取页数
USER_LIMIT = 2


# ===========================================

def get_total_pages(page):
    """精准获取总页数"""
    try:
        page.wait_for_selector('#search-total-matching', timeout=5000)
        total_text = page.inner_text('#search-total-matching').replace(',', '').strip()
        total_results = int(total_text)
        pages = math.ceil(total_results / 10)
        print(f"📊 检测到总结果数: {total_results}，自动计算总页数为: {pages}")
        return pages
    except Exception as e:
        print(f"⚠️ 无法通过 ID 解析页数: {e}")
        return 1


def get_ai_ready_content(detail_page):
    """
    基于 UWA 官网结构提取详情，若结构不符则安全退出
    """
    try:
        # 针对 UWA 标准页面，最多等 5 秒，找不到说明结构不对
        detail_page.wait_for_selector('h1._title', timeout=5000)
        title = detail_page.inner_text('h1._title').strip()

        # 1. 提取 Info Bar
        info_items = []
        for li in detail_page.query_selector_all('ul.bsp_scholarship-info li'):
            h = li.query_selector('.bsp_scholarship-info-heading')
            a = li.query_selector('.bsp_scholarship-info-actual')
            if h and a:
                info_items.append(f"{h.inner_text().strip()}: {a.inner_text().strip()}")

        # 2. 提取正文 Section
        sections = []
        for block in detail_page.query_selector_all('.module-container'):
            h2 = block.query_selector('h2')
            content = block.query_selector('.columns')
            if h2 and content:
                sections.append(f"[{h2.inner_text().strip()}]\n{content.inner_text().strip()}")

        combined = f"TITLE: {title}\nINFO: {' | '.join(info_items)}\n\n" + "\n\n".join(sections)
        return re.sub(r'[ \t]+', ' ', combined).strip()
    except:
        # 这里的异常通常意味着进入了 UWA 的非标准页面或重定向页
        return "SPECIAL_STRUCTURE | 页面结构非标准，请通过链接查看"


def scrape_uwa_for_ai():
    with sync_playwright() as p:
        print("🚀 启动无头浏览器 (后台运行中...)")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=UserAgent().random,
            viewport={'width': 1280, 'height': 800}
        )
        page = context.new_page()

        # # 禁止加载图片和字体，极致提速
        # page.route("**/*.{png,jpg,jpeg,svg,webp,gif,css,font}", lambda route: route.abort())

        target_url = "https://www.search.uwa.edu.au/s/search.html?query=&collection=uowa~sp-scholarship&profile=scholarship"
        print(f"🌐 正在打开列表页...")

        try:
            page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
        except:
            print("❌ 列表页加载超时，请检查网络")
            browser.close()
            return

        total_pages = get_total_pages(page)
        final_pages = min(USER_LIMIT, total_pages) if USER_LIMIT else total_pages
        print(f"✅ 准备抓取 {final_pages} 页内容...")

        # --- 阶段 1：采集链接 ---
        items_to_process = []
        for current_p in range(1, final_pages + 1):
            print(f"📖 扫描列表页 {current_p}/{final_pages}...")
            page.wait_for_selector('h4 a', timeout=10000)

            for link_el in page.query_selector_all('h4 a'):
                href = link_el.get_attribute('href')
                if href:
                    # 清洗重定向链接，获取真实地址
                    real_l = unquote(href.split('url=')[-1].split('&')[0]) if 'url=' in href else href
                    items_to_process.append({
                        'Title': link_el.inner_text().strip(),
                        'Link': real_l
                    })

            if current_p < final_pages:
                next_btn = page.query_selector('a[rel="next"]')
                if next_btn:
                    next_btn.click()
                    page.wait_for_load_state("domcontentloaded")
                    time.sleep(1)
                else:
                    break

        # --- 阶段 2：解析内容 (核心改进区) ---
        print(f"🔗 链接采集完成 (共 {len(items_to_process)} 条)，开始解析...")
        results = []
        for i, item in enumerate(items_to_process, 1):
            link = item['Link'].lower()

            # 【策略 A】域名预判：非 UWA 域名直接打标签，不打开网页
            if "uwa.edu.au" not in link:
                print(f"   ⏩ [{i}/{len(items_to_process)}] 跳过外部页面: {item['Title']}")
                item['Content_For_AI'] = f"EXTERNAL_LINK | 非UWA官网，请手动核对: {link}"
                results.append(item)
                continue

            # 【策略 B】针对 UWA 内部链接的抓取
            dp = context.new_page()
            try:
                print(f"   🔍 [{i}/{len(items_to_process)}] 解析详情: {item['Title']}")
                # 缩短超时时间到 8 秒，打不开就放弃
                dp.goto(item['Link'], wait_until="domcontentloaded", timeout=8000)

                # 检查跳转后是否变成了站外
                current_url = dp.url.lower()
                if "uwa.edu.au" not in current_url:
                    item['Content_For_AI'] = f"EXTERNAL_REDIRECT | 已重定向至站外: {current_url}"
                else:
                    item['Content_For_AI'] = get_ai_ready_content(dp)

                results.append(item)
            except:
                item['Content_For_AI'] = "LOAD_FAILED | 页面加载超时或为附件文件"
                results.append(item)
            finally:
                dp.close()

            # 内部页面抓取后的小缓冲
            time.sleep(random.uniform(0.2, 0.4))

        # --- 阶段 3：保存 ---
        if results:
            with open(SAVE_PATH, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=['Title', 'Link', 'Content_For_AI'])
                writer.writeheader()
                writer.writerows(results)
            print(f"✨ 任务结束！数据已保存至: {SAVE_PATH}")

        browser.close()


if __name__ == "__main__":
    scrape_uwa_for_ai()
