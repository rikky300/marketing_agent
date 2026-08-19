"""添付ソース（PDF / テキスト / URL）からプレーンテキストを取り出す。

ここで取り出したテキストは rag 側で「短ければ全文／長ければ in-memory 検索」に回す。
ベクトルは保存しない。ファイルとURLが両方あればファイルを優先する。
"""
import config


def read_pdf(file) -> str:
    """アップロードされたPDF(file-like)からテキストを抽出する。"""
    from pypdf import PdfReader
    reader = PdfReader(file)
    return "\n".join((page.extract_text() or "") for page in reader.pages).strip()


def read_text(file) -> str:
    """アップロードされたテキストファイル(.txt/.md)を文字列にする。"""
    data = file.getvalue() if hasattr(file, "getvalue") else file.read()
    if isinstance(data, bytes):
        return data.decode("utf-8", errors="replace")
    return str(data)


def read_url(url: str) -> str:
    """URLのHTMLを取得し、本文テキストを抽出する。"""
    import requests
    from bs4 import BeautifulSoup

    if not url.lower().startswith(("http://", "https://")):
        raise ValueError("http/https のURLを指定してください")
    resp = requests.get(url, timeout=config.URL_TIMEOUT,
                        headers={"User-Agent": "Mozilla/5.0 (AgentMark)"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    lines = [ln.strip() for ln in soup.get_text(separator="\n").splitlines()]
    return "\n".join(ln for ln in lines if ln)


def extract_source(uploaded_file, url, pasted_text=""):
    """指定ソースから (テキスト, ラベル) を返す。何も無ければ (None, None)。
    優先順: ファイル → URL → 手入力テキスト。"""
    if uploaded_file is not None:
        name = uploaded_file.name
        if name.lower().endswith(".pdf"):
            return read_pdf(uploaded_file), name
        return read_text(uploaded_file), name
    if url and url.strip():
        u = url.strip()
        return read_url(u), u
    if pasted_text and pasted_text.strip():
        return pasted_text.strip(), "手入力テキスト"
    return None, None
