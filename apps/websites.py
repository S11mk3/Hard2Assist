"""Websites the user can open by name.

os.startfile() opens a URL exactly like a program, so websites need no
special command: "computer open youtube" goes through the same `open` as
everything else. Add a line here and it works.
"""

from .app import App


def site(name, url, *aliases, title=None):
    """One website, as an App.

    The title is what lets `focus` and `close` find the tab once it is open:
    browsers put the page title in the window title, so "youtube" is inside
    "YouTube - Google Chrome". Pass title= when the page names itself
    differently from what the user says.
    """
    return App(name, url, title=title or name, aliases=tuple(aliases),
               kind="web")


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
