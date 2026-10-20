"""quotes.toscrape.com/js から名言と著者を収集し、Markdownとスクリーンショットで保存する。"""
import logging
import random
import sys
import time
from datetime import date
from urllib import robotparser
from urllib.parse import urljoin

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

BASE_URL = "https://quotes.toscrape.com/"
START_PATH = "js/"
USER_AGENT = "python-automation-scraper/1.0"
TIMEOUT_MS = 15000
WAIT_RANGE = (1, 3)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


def load_robots(context) -> robotparser.RobotFileParser:
    """robots.txt を取得して解析する。"""
    url = urljoin(BASE_URL, "robots.txt")
    parser = robotparser.RobotFileParser(url)
    response = context.request.get(url, timeout=TIMEOUT_MS)
    if response.status == 200:
        parser.parse(response.text().splitlines())
    elif response.status in (404, 410):
        parser.parse([])  # robots.txt なし = 制限なし
    else:
        parser.disallow_all = True  # 取得できない場合は安全側に倒す
    return parser


def parse_quotes(page) -> list[dict]:
    return page.eval_on_selector_all(
        "div.quote",
        """els => els.map(e => ({
            text: e.querySelector('span.text').innerText.trim(),
            author: e.querySelector('small.author').innerText.trim(),
        }))""",
    )


def to_markdown(quotes: list[dict], today: date) -> str:
    lines = [
        f"# 名言一覧 ({today.isoformat()})",
        "",
        f"取得元: {urljoin(BASE_URL, START_PATH)} / 取得件数: {len(quotes)}",
        "",
    ]
    for q in quotes:
        lines.append(f"> {q['text']}")
        lines.append(f"> — **{q['author']}**")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    today = date.today()
    stamp = today.strftime("%Y%m%d")
    quotes: list[dict] = []
    first_page_shot = f"quotes_{stamp}.png"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(user_agent=USER_AGENT)
            page = context.new_page()
            page.set_default_timeout(TIMEOUT_MS)

            robots = load_robots(context)
            url = urljoin(BASE_URL, START_PATH)
            first = True
            while url:
                if not robots.can_fetch(USER_AGENT, url):
                    log.warning("robots.txt により禁止されているためスキップ: %s", url)
                    break
                log.info("取得中: %s", url)
                page.goto(url)
                page.wait_for_selector("div.quote")  # JS描画の完了を待つ
                quotes.extend(parse_quotes(page))
                if first:
                    page.screenshot(path=first_page_shot, full_page=True)
                    first = False
                next_link = page.query_selector("li.next > a")
                if next_link is None:
                    break
                url = urljoin(url, next_link.get_attribute("href"))
                time.sleep(random.uniform(*WAIT_RANGE))

            browser.close()
    except PlaywrightError as e:
        log.error("接続エラーが発生したため終了します: %s", e)
        return 1

    if not quotes:
        log.error("名言を取得できませんでした")
        return 1

    out = f"quotes_{stamp}.md"
    with open(out, "w", encoding="utf-8") as f:
        f.write(to_markdown(quotes, today))
    log.info("%d 件を %s に保存しました (スクリーンショット: %s)", len(quotes), out, first_page_shot)
    return 0


if __name__ == "__main__":
    sys.exit(main())
