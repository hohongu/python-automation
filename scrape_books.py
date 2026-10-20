"""books.toscrape.com から書籍のタイトル・価格・在庫状況を収集し、Markdownで保存する。"""
import logging
import random
import sys
import time
from datetime import date
from urllib import robotparser
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://books.toscrape.com/"
USER_AGENT = "python-automation-scraper/1.0"
TIMEOUT = 10
WAIT_RANGE = (1, 3)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


def load_robots(session: requests.Session) -> robotparser.RobotFileParser:
    """robots.txt を取得して解析する。"""
    url = urljoin(BASE_URL, "robots.txt")
    parser = robotparser.RobotFileParser(url)
    response = session.get(url, timeout=TIMEOUT)
    if response.status_code == 200:
        parser.parse(response.text.splitlines())
    elif response.status_code in (404, 410):
        parser.parse([])  # robots.txt なし = 制限なし
    else:
        parser.disallow_all = True  # 取得できない場合は安全側に倒す
    return parser


def fetch(session: requests.Session, robots: robotparser.RobotFileParser, url: str):
    """robots.txt で許可されたURLのみ取得する。禁止なら None を返す。"""
    if not robots.can_fetch(USER_AGENT, url):
        log.warning("robots.txt により禁止されているためスキップ: %s", url)
        return None
    response = session.get(url, timeout=TIMEOUT)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    response.encoding = "utf-8"
    return BeautifulSoup(response.text, "html.parser")


def parse_books(soup: BeautifulSoup) -> list[dict]:
    books = []
    for article in soup.select("article.product_pod"):
        books.append(
            {
                "title": article.h3.a["title"],
                "price": article.select_one("p.price_color").get_text(strip=True),
                "stock": article.select_one("p.availability").get_text(strip=True),
            }
        )
    return books


def to_markdown(books: list[dict], today: date) -> str:
    lines = [
        f"# 書籍一覧 ({today.isoformat()})",
        "",
        f"取得元: {BASE_URL} / 取得件数: {len(books)}",
        "",
        "| タイトル | 価格 | 在庫状況 |",
        "| --- | --- | --- |",
    ]
    for b in books:
        title = b["title"].replace("|", "\\|")
        lines.append(f"| {title} | {b['price']} | {b['stock']} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    books: list[dict] = []
    try:
        robots = load_robots(session)
        page = 1
        while True:
            url = urljoin(BASE_URL, f"catalogue/page-{page}.html")
            log.info("取得中: %s", url)
            soup = fetch(session, robots, url)
            if soup is None:
                break
            books.extend(parse_books(soup))
            if soup.select_one("li.next") is None:
                break
            page += 1
            time.sleep(random.uniform(*WAIT_RANGE))
    except requests.exceptions.RequestException as e:
        log.error("接続エラーが発生したため終了します: %s", e)
        return 1

    if not books:
        log.error("書籍を取得できませんでした")
        return 1

    today = date.today()
    out = f"books_{today.strftime('%Y%m%d')}.md"
    with open(out, "w", encoding="utf-8") as f:
        f.write(to_markdown(books, today))
    log.info("%d 件を %s に保存しました", len(books), out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
