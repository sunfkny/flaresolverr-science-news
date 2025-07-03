import datetime
import io
from typing import TypedDict
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from bs4.element import AttributeValueList
from markdownify import markdownify

import flaresolverr
from flaresolverr import FlareSolverr

client = FlareSolverr()

SCIENCE_BASE_URL = "https://www.science.org/"


def must_get_one(tag: Tag, key: str):
    value = tag.get(key)
    if value is None:
        raise Exception(f"Tag {tag} has no {key}")
    if isinstance(value, AttributeValueList):
        raise Exception(f"Tag {tag} has multiple {key}")
    return value


def must_get_one_or_none(tag: Tag, key: str):
    value = tag.get(key)
    if value is None:
        return None
    if isinstance(value, AttributeValueList):
        raise Exception(f"Tag {tag} has multiple {key}")
    return value


def must_select_one(tag: Tag | None):
    if tag is None:
        raise Exception("Tag is None")
    return tag


def to_absolute_url(text: str):
    return text.replace(
        'src="/',
        f'src="{SCIENCE_BASE_URL}',
    ).replace(
        'href="/',
        f'src="{SCIENCE_BASE_URL}',
    )


class NewsListItem(TypedDict):
    title: str
    url: str
    date: datetime.date


def get_news_list(
    start_page: int, page_size: int = 20, proxy: flaresolverr.Proxy | None = None
) -> list[NewsListItem]:
    """
    Params:
        start_page: zero based page
        page_size: number of items per page
    """
    r = client.request.get(
        url=f"https://www.science.org/news/all-news?pageSize={page_size}&startPage={start_page}",
        maxTimeout=30 * 1000,
        proxy=proxy,
    ).unwrap_response_ok()

    html_content = r.solution.response

    soup = BeautifulSoup(html_content, "html.parser")

    results: list[NewsListItem] = []
    for article in soup.select(".titles-results article"):
        a = must_select_one(article.select_one(".card__title a"))
        date_str = must_select_one(article.select_one("time")).get_text()
        results.append(
            {
                "title": must_get_one(a, "title"),
                "url": urljoin(SCIENCE_BASE_URL, must_get_one(a, "href")),
                "date": datetime.datetime.strptime(date_str, "%d %b %Y").date(),
            }
        )
    return results


class NewsDetail(TypedDict):
    title: str
    subtitle: str
    article_content: str
    figure: str


def news_detail_to_markdown(news: NewsDetail) -> str:
    buf = io.StringIO()

    buf.write("# ")
    buf.write(news["title"])
    buf.write("\n")
    buf.write("## ")
    buf.write(news["subtitle"])
    buf.write("\n")

    buf.write(markdownify(news["figure"]))
    buf.write("\n")
    buf.write("---")
    buf.write("\n")
    buf.write(markdownify(news["article_content"]))

    return buf.getvalue()


def get_news_detail(url: str, proxy: flaresolverr.Proxy | None = None) -> NewsDetail:
    assert url.startswith(SCIENCE_BASE_URL)

    r = client.request.get(
        url=url,
        maxTimeout=30 * 1000,
        proxy=proxy,
    ).unwrap_response_ok()

    html_content = r.solution.response

    soup = BeautifulSoup(html_content, "html.parser")

    # Remove useless elements
    for selector in [
        "script",
        "form",
        "style",
        ".audio-player",
        ".adplaceholder",
        "#div-gpt-ad-leader-inline",
    ]:
        for s in soup.select(selector):
            s.extract()

    return {
        "title": must_select_one(
            soup.select_one(".news-article__hero__title")
        ).get_text(),
        "subtitle": must_select_one(
            soup.select_one(".news-article__hero__subtitle")
        ).get_text(),
        "article_content": to_absolute_url(
            must_select_one(soup.select_one("article.news-article-content")).decode()
        ),
        "figure": to_absolute_url(must_select_one(soup.select_one("figure")).decode()),
    }


if __name__ == "__main__":
    proxy: flaresolverr.Proxy = {
        # Note: in docker, use host.docker.internal instead of localhost to access host
        "url": "http://host.docker.internal:7890",
    }

    news_list = get_news_list(start_page=0)
    for i in news_list:
        print(i)

    print("=" * 80)
    res = get_news_detail(
        url=news_list[0]["url"],
        proxy=proxy,
    )
    print(news_detail_to_markdown(res))
