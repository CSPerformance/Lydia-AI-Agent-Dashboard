"""Parse real search results, excluding navigation and provider challenge pages."""
from html.parser import HTMLParser
import urllib.parse


class SearchResults(HTMLParser):
    def __init__(self, engine):
        super().__init__(convert_charrefs=True)
        self.engine = engine
        self.anchor = None
        self.results = []
        self.heading = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {'h2', 'h3'}:
            self.heading += 1
            if self.anchor is not None:
                self.anchor['heading'] = True
        if tag == 'a':
            classes = set(attrs.get('class', '').split())
            self.anchor = {'href': attrs.get('href', ''), 'text': [],
                           'heading': bool(self.heading),
                           'result': bool(classes & {'result__a', 'result-link'})}

    def handle_data(self, data):
        if self.anchor is not None:
            self.anchor['text'].append(data)

    def handle_endtag(self, tag):
        if tag in {'h2', 'h3'}:
            self.heading = max(0, self.heading - 1)
        if tag != 'a' or self.anchor is None:
            return
        anchor, self.anchor = self.anchor, None
        if not (anchor['result'] if self.engine.startswith('ddg') else anchor['heading']):
            return
        href = urllib.parse.urljoin('https://duckduckgo.com', anchor['href']) if self.engine.startswith('ddg') else anchor['href']
        parsed = urllib.parse.urlparse(href)
        query = urllib.parse.parse_qs(parsed.query)
        if self.engine.startswith('ddg'):
            href = query.get('uddg', [href])[0]
        elif href.startswith('/url?'):
            href = query.get('q', query.get('url', ['']))[0]
        parsed = urllib.parse.urlparse(href)
        host = parsed.hostname or ''
        if parsed.scheme not in {'http', 'https'} or parsed.username or any(
                host == domain or host.endswith('.' + domain)
                for domain in ('duckduckgo.com', 'bing.com', 'www.google.com')):
            return
        title = ' '.join(' '.join(anchor['text']).split())
        if title:
            self.results.append((title, href))


def search_results(html, engine):
    if engine == 'bing_rss':
        import xml.etree.ElementTree as ET
        try:
            root = ET.fromstring(html)
        except ET.ParseError:
            return []
        results = []
        for item in root.findall('./channel/item'):
            title, link = item.findtext('title'), item.findtext('link')
            parsed = urllib.parse.urlparse(link or '')
            if title and parsed.scheme in {'http', 'https'} and parsed.hostname and not parsed.username:
                results.append((title, link))
        return results
    parser = SearchResults(engine)
    parser.feed(html)
    return parser.results


def response_bytes(response, limit=1500000):
    """Honor compressed HTTP responses while bounding decompressed content."""
    import gzip
    import io
    import zlib
    raw=response.read(limit+1)
    if len(raw)>limit:
        raise ValueError('Web response exceeds size limit')
    encoding=str(response.headers.get('Content-Encoding','')).lower()
    if encoding=='gzip' or raw.startswith(b'\x1f\x8b'):
        raw=gzip.GzipFile(fileobj=io.BytesIO(raw)).read(limit+1)
    elif encoding=='deflate':
        decoder=zlib.decompressobj()
        raw=decoder.decompress(raw,limit+1)
    elif encoding not in {'','identity'}:
        raise ValueError('Unsupported web response encoding')
    if len(raw)>limit:
        raise ValueError('Decoded web response exceeds size limit')
    return raw


_QUERY_STOP = set('a an the to of and or in on at for from with without is are was be do does did how what which why when where who can could would should i me my you your our please lydia explain describe compare define difference between differs give show display tell using use clearly concise beginner answer commands command changing settings official documentation information plain language small example examples useful results latest main benefits errors clearly basic causes cause works differ'.split())


def query_terms(query):
    import re
    query = re.sub(r'\bsite:\S+', '', str(query), flags=re.I)
    return list(dict.fromkeys(word.lower() for word in re.findall(r'[A-Za-z0-9][A-Za-z0-9_.-]*',query)
                             if len(word.strip('.-'))>=2 and word.lower().strip('.-') not in _QUERY_STOP))


def focused_query(query):
    import re
    terms=query_terms(query)
    sites=re.findall(r'\bsite:[\w.-]+',query,re.I)
    return ' '.join(terms[:14]+sites) if terms else query


def relevant_result(query, title, url):
    """Reject parseable but unrelated engine results, including ignored site filters."""
    import re
    host=(urllib.parse.urlparse(url).hostname or '').lower()
    sites=re.findall(r'\bsite:([\w.-]+)',query,re.I)
    if sites and not any(host==site.lower() or host.endswith('.'+site.lower()) for site in sites):return False
    terms=re.findall(r'[a-z0-9]+',' '.join(query_terms(query)))
    if not terms:return True
    hay=(title+' '+urllib.parse.unquote(url)).lower()
    matches=sum(bool(re.search(r'(?<![a-z0-9])'+re.escape(t)+r'(?:s|ing)?(?![a-z0-9])',hay)) for t in terms)
    return matches >= 1
