"""Websites the user can open by name. os.startfile() opens a URL like a program, so a line here
is all a new site needs."""

from .app import App


def site(name, url, *aliases, title=None):
    """One website. Its title is how `focus` and `close` find the tab, since browsers put the
    page's title in the window's; pass title= when the page names itself differently."""
    return App(name, url, title=title or name, aliases=aliases, kind="web")


SITES = [
    site("youtube", "https://www.youtube.com", "you tube"),
    site("google", "https://www.google.com"),
    site("github", "https://github.com", "git hub"),
    site("gmail", "https://mail.google.com", "email", "e-mail"),
    site("reddit", "https://www.reddit.com"),
    site("wikipedia", "https://www.wikipedia.org"),
    site("maps", "https://maps.google.com", "google maps"),
    site("translate", "https://translate.google.com", "google translate"),
    site("chatgpt", "https://chat.openai.com", "chat gpt"),
    site("claude", "https://claude.ai"),
    site("twitch", "https://www.twitch.tv"),
    site("spotify web", "https://open.spotify.com", title="spotify"),
]
