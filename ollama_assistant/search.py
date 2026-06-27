from ddgs import DDGS


def search_web(query, max_results=5):
    try:
        results = DDGS().text(query, max_results=max_results)
        if not results:
            return "No results found."

        formatted = []
        for r in results:
            formatted.append(
                f"Title: {r.get('title')}\nURL: {r.get('href')}\nSnippet: {r.get('body')}"
            )
        return "\n\n".join(formatted)
    except Exception as e:
        return f"Search failed: {e}"
