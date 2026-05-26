"""Server-rendered HTML pages used during auth and credential flows.

These pages are built from f-strings (not Jinja templates) and are served by
the daemon before there is a session, e.g. hosted login/register, identity
claim, OAuth/device-code interstitials, and error pages. The Jinja-rendered
dashboard lives in ``authsome.ui``.
"""
